"""cocotb test: checks lif_math.v against the Python neuron_model, one (voltage, total) pair at a time.

Run from the repo root:

    .venv/bin/python verilog/test_lif_math.py

It tries every voltage a neuron can hold (-512..255) against a set of totals picked to hit
every edge (just below / at / above the threshold and the floor), plus random totals.
"""
import random
from pathlib import Path

import cocotb
from cocotb.triggers import Timer

FLOOR = -512
THRESHOLD = 256


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


def totals_to_try(v, rng):
    """Totals that land the new voltage right around each edge, plus some random ones."""
    leaked = v - (v >> 3)
    edges = [THRESHOLD - 1, THRESHOLD, THRESHOLD + 1, FLOOR - 1, FLOOR, FLOOR + 1, 0]
    totals = [edge - leaked for edge in edges]                  # hits each edge exactly
    totals += [0, 1, -1, 300, -400, 3000, -3000, 30000, -30000]
    totals += [rng.randint(-2000, 2000) for _ in range(20)]
    return totals


@cocotb.test()
async def matches_python(dut):
    rng = random.Random(1)
    checked = 0
    for v in range(FLOOR, THRESHOLD):                          # every voltage a neuron can hold
        for total in totals_to_try(v, rng):
            dut.old_voltage.value = v
            dut.total.value = total
            await Timer(1, unit="ns")                          # let the wires settle
            want_v, want_spike = neuron_model(total, v)
            got_v = dut.new_voltage.value.to_signed()
            got_spike = int(dut.spike.value)
            assert (got_v, got_spike) == (want_v, want_spike), (
                f"old_voltage={v}, total={total}: chip gave v={got_v} spike={got_spike}, "
                f"Python gives v={want_v} spike={want_spike}")
            checked += 1
    dut._log.info(f"PASS: {checked} (voltage, total) pairs match Python")


if __name__ == "__main__":
    from cocotb_tools.runner import get_runner

    here = Path(__file__).resolve().parent
    runner = get_runner("icarus")
    runner.build(sources=[here / "lif_math.v"], hdl_toplevel="lif_math",
                 build_dir=here / "sim_build", timescale=("1ns", "1ps"))
    runner.test(hdl_toplevel="lif_math", test_module="test_lif_math", test_dir=here)
