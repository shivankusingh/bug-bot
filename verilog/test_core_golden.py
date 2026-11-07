"""cocotb test: the core against the golden files written by the Python notebooks.

Run from the repo root (make the .mem files first with python/make_mem.py):

    .venv/bin/python verilog/test_core_golden.py          # chain: 4 neurons, 10 steps
    .venv/bin/python verilog/test_core_golden.py full     # full worm: 300 neurons, 80 steps

Unlike the other core tests, this one has no Python model inside: it only replays the poke
inputs from data/<network>_inputs.txt and compares every step's spikes and voltages with the
expected files, starting from all zeros like the notebooks do.
    chain   chain_inputs.txt, chain_expected_spikes.txt, chain_expected_va/vb/vc/vi.txt
    full    full_inputs.txt, full_expected_spikes.txt, full_expected_v.txt
The full worm's golden files include pipes, so it can only match once the core has a PIPES job.
"""
import sys
from pathlib import Path

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import FallingEdge, RisingEdge

HERE = Path(__file__).resolve().parent
DATA = HERE.parent / "data"
sys.path.insert(0, str(HERE.parent / "python"))
from make_mem import chain_network, chain_pipes, full_network, full_pipes  # noqa: E402

NETWORKS = {"chain": chain_network, "full": full_network}
PIPE_LISTS = {"chain": chain_pipes, "full": full_pipes}


def hex_lines(name):
    return [int(line, 16) for line in (DATA / name).read_text().split()]


def signed16(word):
    return word - (1 << 16) if word & 0x8000 else word


def load_golden(network, n, n_pokes):
    """-> (poke rows, spike rows, voltage rows), one row per step, row[i] = neuron i."""
    # inputs: poke 0 is the top bit (chain: A*2 + I, full: head*2 + tail)
    pokes = [[(x >> (n_pokes - 1 - p)) & 1 for p in range(n_pokes)] for x in hex_lines(f"{network}_inputs.txt")]
    if network == "chain":
        # spikes: A*8 + B*4 + C*2 + I, so neuron i is bit 3 - i; one voltage file per neuron
        spikes = [[(x >> (n - 1 - i)) & 1 for i in range(n)] for x in hex_lines("chain_expected_spikes.txt")]
        columns = [hex_lines(f"chain_expected_v{name}.txt") for name in "abci"]
        voltages = [[signed16(col[step]) for col in columns] for step in range(len(pokes))]
    else:
        # spikes: bit i = neuron i; voltages: line = step * n + neuron
        spikes = [[(x >> i) & 1 for i in range(n)] for x in hex_lines("full_expected_spikes.txt")]
        flat = [signed16(x) for x in hex_lines("full_expected_v.txt")]
        voltages = [flat[step * n:(step + 1) * n] for step in range(len(pokes))]
    return pokes, spikes, voltages


def neuron_names(network, n):
    if network == "chain":
        return list("ABCI")
    import connectome_all as net
    names = {getattr(net, k): k for k in dir(net)
             if k.isupper() and k.isalnum() and isinstance(getattr(net, k), int)}
    return [names.get(i, str(i)) for i in range(n)]


def read(memory, slot):
    value = memory[slot].value
    if str(value).lower().strip("01"):  # any x or z bit
        return str(value)
    return value.to_signed() if hasattr(value, "to_signed") else int(value)


@cocotb.test()
async def matches_golden_files(dut):
    network = cocotb.plusargs["network"]
    connections, poke_connections = NETWORKS[network]()
    n, n_pokes = len(connections), len(poke_connections)
    pokes, want_spikes, want_voltages = load_golden(network, n, n_pokes)
    names = neuron_names(network, n)
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())

    dut.reset.value = 1
    dut.start_step.value = 0
    dut.pokes.value = 0
    for _ in range(3):
        await RisingEdge(dut.clk)
    await FallingEdge(dut.clk)  # change inputs halfway between rising edges
    dut.reset.value = 0

    limit = 20 * n + 4 * sum(len(out) for out in connections) + 200
    for step, row in enumerate(pokes):
        dut.pokes.value = sum(bit << p for p, bit in enumerate(row))  # bit p = poke p
        await FallingEdge(dut.clk)
        dut.start_step.value = 1          # "do a step", for one tick
        await FallingEdge(dut.clk)
        dut.start_step.value = 0

        ticks = 0
        while int(dut.busy.value) == 1:
            await FallingEdge(dut.clk)
            ticks += 1
            assert ticks <= limit, f"step {step}: busy still 1 after {ticks} ticks"
        assert ticks > 0, f"step {step}: busy never went to 1 after start_step"

        wrong = []
        for i in range(n):
            got = (read(dut.voltages, i), read(dut.spikes, i))
            want = (want_voltages[step][i], want_spikes[step][i])
            if got != want:
                wrong.append(f"{names[i]} (#{i}): chip v={got[0]} spike={got[1]}, "
                             f"golden v={want[0]} spike={want[1]}")
        assert not wrong, (
            f"step {step} (pokes {row}): {len(wrong)} neuron(s) differ from the golden files. "
            f"First ones:\n  " + "\n  ".join(wrong[:8]))
        fired = [names[i] for i in range(n) if want_spikes[step][i]]
        shown = ", ".join(fired[:6]) + (" ..." if len(fired) > 6 else "")
        dut._log.info(f"  step {step:2d}, pokes {row}: all {n} match, {len(fired)} fired"
                      f"{' (' + shown + ')' if fired else ''}, took {ticks} ticks")
    dut._log.info(f"PASS: the core matches the {network} golden files for all {len(pokes)} steps")


if __name__ == "__main__":
    from cocotb_tools.runner import get_runner

    network = sys.argv[1] if len(sys.argv) > 1 else "chain"
    if network not in NETWORKS:
        sys.exit(f"unknown network {network!r}, pick one of: {', '.join(NETWORKS)}")
    connections, poke_connections = NETWORKS[network]()
    parameters = {
        "N": len(connections),
        "N_LINKS": sum(len(out) for out in connections),
        "N_POKES": len(poke_connections),
        "N_POKE_LINKS": sum(len(out) for out in poke_connections),
        "N_PIPES": max(1, len(PIPE_LISTS[network]())),
        "MEM_DIR": f'"../data/mem/{network}"',  # relative to verilog/, where the test runs
    }
    runner = get_runner("icarus")
    runner.build(sources=[HERE / "core.v", HERE / "lif_math.v", *HERE.glob("muscle_readout.v")], hdl_toplevel="core",
                 parameters=parameters, build_dir=HERE / "sim_build" / network,
                 timescale=("1ns", "1ps"), always=True)
    runner.test(hdl_toplevel="core", test_module="test_core_golden", test_dir=HERE,
                plusargs=[f"+network={network}"])
