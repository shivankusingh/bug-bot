"""cocotb test: phase 1c of the core (clear totals, deliver spikes, deliver pokes, update).

Run from the repo root (make the .mem files first with python/make_mem.py):

    .venv/bin/python verilog/test_core_spikes.py

For each network (4-neuron, then 300-neuron) it runs many steps with a mix of poke
patterns, starting from all zeros. Each step it sets the pokes input, pulses start_step,
waits for busy to go back to 0, then checks:
    1. totals: every neuron got exactly its mail = spike mail (from neurons that fired
       LAST step) + poke mail (this step)
    2. voltages and spikes: match the Python neuron_model
Pipes are NOT in the core yet, so the Python side here leaves them out too.

What core.v needs, on top of test_core_pokes.py:
    a SPIKES job, after CLEAR and before UPDATE, that walks every neuron that fired last
    step (spikes[i] == 1) and adds its links (start, link_receiver, link_weight) into totals
"""
import random
import sys
from pathlib import Path

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import FallingEdge, RisingEdge

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "python"))
from make_mem import chain_network, chain_pipes, full_network, full_pipes  # noqa: E402

NETWORKS = {"chain": chain_network, "full": full_network}
PIPE_LISTS = {"chain": chain_pipes, "full": full_pipes}
FLOOR, THRESHOLD = -512, 256


def neuron_model(total, v):
    """Same as neuron_model in python/touch_test.ipynb (keep the two in sync)."""
    spike = 0
    v = v - (v >> 3) + total
    if v >= THRESHOLD:
        v = 0
        spike = 1
    elif v < FLOOR:
        v = FLOOR
    return v, spike


def read(memory, slot):
    value = memory[slot].value
    if str(value).lower().strip("01"):  # any x or z bit
        return str(value)
    return value.to_signed() if hasattr(value, "to_signed") else int(value)


def poke_patterns(network, n_pokes, rng):
    """Which pokes are on, one row per step."""
    if network == "chain":
        rows = [[1, 0], [0, 0], [0, 1], [1, 0], [0, 0], [0, 0], [1, 1], [1, 0], [1, 0], [0, 0]]
        return rows + [[int(rng.random() < 0.4) for _ in range(n_pokes)] for _ in range(30)]
    head, tail, quiet = [1, 0], [0, 1], [0, 0]
    rows = [head] * 4 + [quiet] * 21 + [tail] * 4 + [quiet] * 21   # like the touch test
    return rows + [[int(rng.random() < 0.3) for _ in range(n_pokes)] for _ in range(20)]


@cocotb.test()
async def spikes_reach_totals(dut):
    network = cocotb.plusargs["network"]
    connections, poke_connections = NETWORKS[network]()
    n, n_pokes = len(connections), len(poke_connections)
    n_links = sum(len(out) for out in connections)
    rng = random.Random(7)
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())

    dut.reset.value = 1
    dut.start_step.value = 0
    dut.pokes.value = 0
    for _ in range(3):
        await RisingEdge(dut.clk)
    await FallingEdge(dut.clk)  # change inputs halfway between rising edges
    dut.reset.value = 0
    if hasattr(dut, "pipe_size"):           # turn every pipe off (size 0): this test leaves pipes out
        for k in range(len(dut.pipe_size)):
            dut.pipe_size[k].value = 0

    voltages, last_spikes = [0] * n, [0] * n
    for step, row in enumerate(poke_patterns(network, n_pokes, rng)):
        dut.pokes.value = sum(bit << p for p, bit in enumerate(row))  # bit p = poke p
        await FallingEdge(dut.clk)
        dut.start_step.value = 1          # "do a step", for one tick
        await FallingEdge(dut.clk)
        dut.start_step.value = 0

        ticks = 0
        limit = 4 * n + 2 * n_links + 2 * len(sum(poke_connections, [])) + 2 * n_pokes + 20
        while int(dut.busy.value) == 1:
            await FallingEdge(dut.clk)
            ticks += 1
            assert ticks <= limit, f"step {step}: busy still 1 after {ticks} ticks"
        assert ticks > 0, f"step {step}: busy never went to 1 after start_step"

        # the Python way: clear, spike mail from last step's spikes, then poke mail
        spike_mail, poke_mail = [0] * n, [0] * n
        for sender in range(n):
            if last_spikes[sender]:
                for receiver, weight in connections[sender]:
                    spike_mail[receiver] += weight
        for p, on in enumerate(row):
            if on:
                for receiver, weight in poke_connections[p]:
                    poke_mail[receiver] += weight
        totals = [spike_mail[i] + poke_mail[i] for i in range(n)]

        for i in range(n):
            got = read(dut.totals, i)
            if got != totals[i]:
                senders = [s for s in range(n) if last_spikes[s] and any(r == i for r, _ in connections[s])]
                raise AssertionError(
                    f"step {step} (pokes {row}): totals[{i}] is {got}, should be {totals[i]} "
                    f"= spike mail {spike_mail[i]} + poke mail {poke_mail[i]}. "
                    f"Neurons that fired last step and send to {i}: {senders or 'none'}")
        want = [neuron_model(totals[i], voltages[i]) for i in range(n)]
        for i in range(n):
            got = (read(dut.voltages, i), read(dut.spikes, i))
            assert got == want[i], (
                f"step {step} (pokes {row}), neuron {i}: chip has v={got[0]} spike={got[1]}, "
                f"Python says v={want[i][0]} spike={want[i][1]} (old v={voltages[i]}, total={totals[i]})")

        fired_before = sum(last_spikes)
        voltages = [v for v, _ in want]
        last_spikes = [s for _, s in want]
        dut._log.info(f"  step {step:2d}, pokes {row}: {fired_before} sent spike mail, "
                      f"{sum(last_spikes)} fired, took {ticks} ticks")
    dut._log.info(f"PASS: clear + spikes + pokes + update matches Python for the {network} network ({n} neurons)")


if __name__ == "__main__":
    from cocotb_tools.runner import get_runner

    runner = get_runner("icarus")
    for network, make in NETWORKS.items():
        connections, poke_connections = make()
        parameters = {
            "N": len(connections),
            "N_LINKS": sum(len(out) for out in connections),
            "N_POKES": len(poke_connections),
            "N_POKE_LINKS": sum(len(out) for out in poke_connections),
            "N_PIPES": max(1, len(PIPE_LISTS[network]())),
            "MEM_DIR": f'"../data/mem/{network}"',  # relative to verilog/, where the test runs
        }
        runner.build(sources=[HERE / "core.v", HERE / "lif_math.v"], hdl_toplevel="core",
                     parameters=parameters, build_dir=HERE / "sim_build" / network,
                     timescale=("1ns", "1ps"), always=True)
        runner.test(hdl_toplevel="core", test_module="test_core_spikes", test_dir=HERE,
                    plusargs=[f"+network={network}"])
