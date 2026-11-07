"""cocotb test: the PIPES job of the core (flow + spike packages), on top of everything else.

Run from the repo root (make the .mem files first with python/make_mem.py):

    .venv/bin/python verilog/test_core_pipes.py

For each network it runs many steps from all zeros, with a mix of poke patterns. Each step
it sets the pokes input, pulses start_step, waits for busy to go back to 0, then checks:
    1. totals: every neuron got exactly spike mail + poke mail + pipe mail, where pipe mail =
       spike packages (from pipe partners that fired LAST step) + flow (from start-of-step
       voltages). A wrong total lists the pipes touching that neuron and what each should give.
    2. voltages and spikes: match the Python model
Networks:
    chain   the 4-neuron network with its one pipe slot turned into a real pipe A-B, size 100
            (the test writes pipe_size[0] = 100 after reset; the .mem file has 0)
    full    the 300-neuron worm with all 1,087 pipes

What core.v needs, on top of test_core_spikes.py:
    parameter N_PIPES, memories pipe_a, pipe_b (9 bits) and pipe_size (8 bits, unsigned)
    loaded from pipe_a.mem, pipe_b.mem, pipe_size.mem, and a PIPES job before UPDATE
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
PIPE_SHIFT, PIPE_K = 10, 1          # same as python/touch_test.ipynb
CHAIN_TEST_PIPE = (0, 1, 100)       # A-B, size 100, written into the chain's do-nothing pipe slot


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
        return [[int(rng.random() < 0.4) for _ in range(n_pokes)] for _ in range(40)]
    head, tail, quiet = [1, 0], [0, 1], [0, 0]
    rows = [head] * 4 + [quiet] * 21 + [tail] * 4 + [quiet] * 21   # like the touch test
    return rows + [[int(rng.random() < 0.3) for _ in range(n_pokes)] for _ in range(20)]


def pipe_mail(pipes, voltages, last_spikes, n):
    """-> (mail per neuron, notes per neuron) for every pipe, the Python way."""
    mail, notes = [0] * n, [[] for _ in range(n)]
    for k, (a, b, size) in enumerate(pipes):
        flow = ((voltages[a] - voltages[b]) * size) >> PIPE_SHIFT
        to_a = -flow + (size * PIPE_K if last_spikes[b] else 0)
        to_b = flow + (size * PIPE_K if last_spikes[a] else 0)
        mail[a] += to_a
        mail[b] += to_b
        why = (f"pipe {k} ({a}-{b}, size {size}): v[{a}]={voltages[a]}, v[{b}]={voltages[b]}, "
               f"flow={flow}, spiked last step: {a}={last_spikes[a]} {b}={last_spikes[b]}")
        notes[a].append(f"{why} -> gives {a}: {to_a}")
        notes[b].append(f"{why} -> gives {b}: {to_b}")
    return mail, notes


@cocotb.test()
async def pipes_reach_totals(dut):
    network = cocotb.plusargs["network"]
    connections, poke_connections = NETWORKS[network]()
    pipes = PIPE_LISTS[network]() or [CHAIN_TEST_PIPE]
    n, n_pokes = len(connections), len(poke_connections)
    rng = random.Random(3)
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())

    dut.reset.value = 1
    dut.start_step.value = 0
    dut.pokes.value = 0
    for _ in range(3):
        await RisingEdge(dut.clk)
    await FallingEdge(dut.clk)  # change inputs halfway between rising edges
    dut.reset.value = 0
    if network == "chain":
        dut.pipe_size[0].value = CHAIN_TEST_PIPE[2]   # make the do-nothing pipe a real one

    limit = 4 * n + 2 * sum(len(out) for out in connections) + 4 * len(pipes) + 100
    voltages, last_spikes = [0] * n, [0] * n
    for step, row in enumerate(poke_patterns(network, n_pokes, rng)):
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

        # the Python way: clear, spike mail, poke mail, pipe mail
        spike_mail, poke_mail = [0] * n, [0] * n
        for sender in range(n):
            if last_spikes[sender]:
                for receiver, weight in connections[sender]:
                    spike_mail[receiver] += weight
        for p, on in enumerate(row):
            if on:
                for receiver, weight in poke_connections[p]:
                    poke_mail[receiver] += weight
        pipe, notes = pipe_mail(pipes, voltages, last_spikes, n)
        totals = [spike_mail[i] + poke_mail[i] + pipe[i] for i in range(n)]

        for i in range(n):
            got = read(dut.totals, i)
            if got != totals[i]:
                raise AssertionError(
                    f"step {step} (pokes {row}): totals[{i}] is {got}, should be {totals[i]} = "
                    f"spike mail {spike_mail[i]} + poke mail {poke_mail[i]} + pipe mail {pipe[i]}.\n"
                    f"  Pipes touching neuron {i} ({len(notes[i])}, first 6):\n    "
                    + "\n    ".join(notes[i][:6]))
        want = [neuron_model(totals[i], voltages[i]) for i in range(n)]
        for i in range(n):
            got = (read(dut.voltages, i), read(dut.spikes, i))
            assert got == want[i], (
                f"step {step} (pokes {row}), neuron {i}: chip has v={got[0]} spike={got[1]}, "
                f"Python says v={want[i][0]} spike={want[i][1]} (old v={voltages[i]}, total={totals[i]})")

        voltages = [v for v, _ in want]
        last_spikes = [s for _, s in want]
        dut._log.info(f"  step {step:2d}, pokes {row}: all {n} match, {sum(last_spikes)} fired, "
                      f"took {ticks} ticks")
    dut._log.info(f"PASS: clear + spikes + pokes + pipes + update matches Python for the "
                  f"{network} network ({n} neurons, {len(pipes)} pipes)")


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
        runner.build(sources=[HERE / "core.v", HERE / "lif_math.v", *HERE.glob("muscle_readout.v")], hdl_toplevel="core",
                     parameters=parameters, build_dir=HERE / "sim_build" / network,
                     timescale=("1ns", "1ps"), always=True)
        runner.test(hdl_toplevel="core", test_module="test_core_pipes", test_dir=HERE,
                    plusargs=[f"+network={network}"])
