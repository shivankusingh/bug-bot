"""cocotb test: phase 2 of the core (update every neuron through lif_math, one per tick).

Run from the repo root (make the .mem files first with python/make_mem.py):

    .venv/bin/python verilog/test_core_phase2.py

For each network (4-neuron, then 300-neuron) it runs 3 steps. Before each step it fills
every totals[i] with a random number (standing in for phase 1, which doesn't exist yet),
pulses start_step, waits for busy to go back to 0, then checks every voltages[i] and
spikes[i] against the Python neuron_model. Voltages carry over from step to step.

What core.v needs, on top of test_core_memories.py:
    ports   input start_step   (1 for one tick = "do a step")
            output reg busy    (1 while the step is running, back to 0 when every neuron is done)
    reset   while reset is 1, busy must be 0
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
async def phase2_updates_every_neuron(dut):
    network = cocotb.plusargs["network"]
    n = len(NETWORKS[network]()[0])
    rng = random.Random(7)
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())

    dut.reset.value = 1
    dut.start_step.value = 0
    for _ in range(3):
        await RisingEdge(dut.clk)
    await FallingEdge(dut.clk)  # change inputs halfway between rising edges
    assert int(dut.busy.value) == 0, "busy should be 0 during reset"
    dut.reset.value = 0

    voltages = [0] * n
    for step in range(3):
        # stand-in for phase 1: put a random total in every neuron's slot
        totals = [rng.randint(-600, 600) for _ in range(n)]
        for i, t in enumerate(totals):
            dut.totals[i].value = t
        await FallingEdge(dut.clk)

        dut.start_step.value = 1          # "do a step", for one tick
        await FallingEdge(dut.clk)
        dut.start_step.value = 0

        ticks = 0
        while int(dut.busy.value) == 1:
            await FallingEdge(dut.clk)
            ticks += 1
            assert ticks <= n + 5, f"step {step}: busy still 1 after {ticks} ticks (only {n} neurons)"
        assert ticks > 0, f"step {step}: busy never went to 1 after start_step"

        want = [neuron_model(totals[i], voltages[i]) for i in range(n)]
        for i in range(n):
            got_v, got_spike = read(dut.voltages, i), read(dut.spikes, i)
            assert (got_v, got_spike) == want[i], (
                f"step {step}, neuron {i}: chip has v={got_v} spike={got_spike}, Python says "
                f"v={want[i][0]} spike={want[i][1]} (old v={voltages[i]}, total={totals[i]})")
        voltages = [v for v, _ in want]
        fired = sum(s for _, s in want)
        dut._log.info(f"  step {step}: all {n} neurons match ({fired} fired), took {ticks} ticks")
    dut._log.info(f"PASS: phase 2 matches Python for the {network} network ({n} neurons)")


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
        runner.test(hdl_toplevel="core", test_module="test_core_phase2", test_dir=HERE,
                    plusargs=[f"+network={network}"])
