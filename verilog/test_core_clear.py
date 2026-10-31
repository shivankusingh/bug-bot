"""cocotb test: phase 1a of the core (clear totals, then update every neuron).

Run from the repo root (make the .mem files first with python/make_mem.py):

    .venv/bin/python verilog/test_core_clear.py

For each network (4-neuron, then 300-neuron) it runs 3 steps. Before each step it fills
voltages[i] and totals[i] with random numbers ("junk left over"), pulses start_step and
waits for busy to go back to 0. Because the core clears totals before updating, every
neuron should end up as if its total was 0 (just the leak), and every totals[i] should be 0.

What core.v needs: the same ports as test_core_phase2.py (start_step in, busy out), and a
CLEAR job that sets every totals[i] to 0 before the UPDATE job runs.
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
async def clear_then_update(dut):
    network = cocotb.plusargs["network"]
    n = len(NETWORKS[network]()[0])
    rng = random.Random(11)
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())

    dut.reset.value = 1
    dut.start_step.value = 0
    for _ in range(3):
        await RisingEdge(dut.clk)
    await FallingEdge(dut.clk)  # change inputs halfway between rising edges
    assert int(dut.busy.value) == 0, "busy should be 0 during reset"
    dut.reset.value = 0

    for step in range(3):
        # junk the core should ignore (totals) or carry on from (voltages)
        voltages = [rng.randint(FLOOR, THRESHOLD - 1) for _ in range(n)]
        for i in range(n):
            dut.voltages[i].value = voltages[i]
            dut.totals[i].value = rng.randint(-600, 600)
        await FallingEdge(dut.clk)

        dut.start_step.value = 1          # "do a step", for one tick
        await FallingEdge(dut.clk)
        dut.start_step.value = 0

        ticks = 0
        while int(dut.busy.value) == 1:
            await FallingEdge(dut.clk)
            ticks += 1
            assert ticks <= 2 * n + 5, f"step {step}: busy still 1 after {ticks} ticks ({n} neurons)"
        assert ticks > 0, f"step {step}: busy never went to 1 after start_step"

        for i in range(n):
            got = read(dut.totals, i)
            assert got == 0, f"step {step}: totals[{i}] is {got} after the step, should be 0 (cleared)"
        for i in range(n):
            want = neuron_model(0, voltages[i])
            got = (read(dut.voltages, i), read(dut.spikes, i))
            assert got == want, (
                f"step {step}, neuron {i}: chip has v={got[0]} spike={got[1]}, Python says "
                f"v={want[0]} spike={want[1]} (old v={voltages[i]}, total should be 0 after clearing)")
        dut._log.info(f"  step {step}: totals cleared, all {n} neurons match, took {ticks} ticks")
    dut._log.info(f"PASS: clear + update matches Python for the {network} network ({n} neurons)")


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
        runner.test(hdl_toplevel="core", test_module="test_core_clear", test_dir=HERE,
                    plusargs=[f"+network={network}"])
