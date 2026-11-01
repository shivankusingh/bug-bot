"""cocotb test: phase 1b of the core (clear totals, deliver pokes, then update every neuron).

Run from the repo root (make the .mem files first with python/make_mem.py):

    .venv/bin/python verilog/test_core_pokes.py

For each network (4-neuron, then 300-neuron) it runs 12 steps with every poke pattern
(none, each one alone, all at once) plus random ones. Each step it sets the pokes input,
pulses start_step and waits for busy to go back to 0, then checks:
    1. totals: every neuron got exactly its poke mail (and nothing else)
    2. voltages and spikes: match the Python neuron_model, voltages carrying over
Neuron-to-neuron spikes are NOT delivered yet (phase 1c), so the Python side here only
uses the pokes.

What core.v needs, on top of test_core_clear.py:
    input [N_POKES-1:0] pokes    bit p = poke p (pokes[0] = head, pokes[1] = tail)
    a POKES job between CLEAR and UPDATE that adds each active poke's weights into totals
"""
import random
import sys
from pathlib import Path

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import FallingEdge, RisingEdge

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "python"))
from make_mem import chain_network, full_network  # noqa: E402

NETWORKS = {"chain": chain_network, "full": full_network}
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


@cocotb.test()
async def pokes_reach_totals(dut):
    network = cocotb.plusargs["network"]
    connections, poke_connections = NETWORKS[network]()
    n, n_pokes = len(connections), len(poke_connections)
    rng = random.Random(5)
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())

    dut.reset.value = 1
    dut.start_step.value = 0
    dut.pokes.value = 0
    for _ in range(3):
        await RisingEdge(dut.clk)
    await FallingEdge(dut.clk)  # change inputs halfway between rising edges
    dut.reset.value = 0

    patterns = [[0] * n_pokes] + [[int(p == q) for q in range(n_pokes)] for p in range(n_pokes)]
    patterns += [[1] * n_pokes] + [[rng.randint(0, 1) for _ in range(n_pokes)] for _ in range(8)]

    voltages = [0] * n
    for step, row in enumerate(patterns):
        dut.pokes.value = sum(bit << p for p, bit in enumerate(row))  # bit p = poke p
        await FallingEdge(dut.clk)
        dut.start_step.value = 1          # "do a step", for one tick
        await FallingEdge(dut.clk)
        dut.start_step.value = 0

        ticks = 0
        limit = 2 * n + 2 * len(sum(poke_connections, [])) + 2 * n_pokes + 10
        while int(dut.busy.value) == 1:
            await FallingEdge(dut.clk)
            ticks += 1
            assert ticks <= limit, f"step {step}: busy still 1 after {ticks} ticks"
        assert ticks > 0, f"step {step}: busy never went to 1 after start_step"

        totals = [0] * n                  # the Python way: clear, then pokes only
        for p, on in enumerate(row):
            if on:
                for target, weight in poke_connections[p]:
                    totals[target] += weight
        for i in range(n):
            got = read(dut.totals, i)
            assert got == totals[i], (
                f"step {step} (pokes {row}): totals[{i}] is {got}, should be {totals[i]}")
        want = [neuron_model(totals[i], voltages[i]) for i in range(n)]
        for i in range(n):
            got = (read(dut.voltages, i), read(dut.spikes, i))
            assert got == want[i], (
                f"step {step} (pokes {row}), neuron {i}: chip has v={got[0]} spike={got[1]}, "
                f"Python says v={want[i][0]} spike={want[i][1]} (old v={voltages[i]}, total={totals[i]})")
        voltages = [v for v, _ in want]
        dut._log.info(f"  step {step:2d}, pokes {row}: totals and all {n} neurons match, "
                      f"{sum(s for _, s in want)} fired, took {ticks} ticks")
    dut._log.info(f"PASS: clear + pokes + update matches Python for the {network} network ({n} neurons)")


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
            "MEM_DIR": f'"../data/mem/{network}"',  # relative to verilog/, where the test runs
        }
        runner.build(sources=[HERE / "core.v", HERE / "lif_math.v"], hdl_toplevel="core",
                     parameters=parameters, build_dir=HERE / "sim_build" / network,
                     timescale=("1ns", "1ps"), always=True)
        runner.test(hdl_toplevel="core", test_module="test_core_pokes", test_dir=HERE,
                    plusargs=[f"+network={network}"])
