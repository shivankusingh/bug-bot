"""cocotb test: the board's top file (buttons, step timer, core, LEDs) for the full 80-step worm run.

Run from the repo root:

    .venv/bin/python verilog/test_top.py

It drives top.v like a person at the board: hold btnC to reset, then hold btnU (head) or btnD
(tail) during the steps where data/full_inputs.txt has that poke. The step timer is shrunk to
STEP_TICKS = 10,000 ticks (the board uses 5,000,000), so the 80 steps take about 8 seconds to
simulate instead of hours.

After each step it reads the LEDs and checks them against the Python rules (the same expected
answers as test_core_muscles.py):
    led[15] = backward, led[14] = forward, led[6:0] = wheel speed,
    led[12] / led[11] = the head / tail button after the sync flip-flops.
It also fails if start_step ever arrives while the core is still busy (that step would be
skipped without any error on the board).

Waveform: saved as verilog/sim_build/top/top.fst; open it with
    surfer verilog/sim_build/top/top.fst
"""
import sys
from pathlib import Path

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import FallingEdge

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "python"))
from make_mem import full_motors  # noqa: E402
from test_core_muscles import DIRECTIONS, expected_run, hex_lines  # noqa: E402

STEP_TICKS = 10_000   # > the longest possible step (~8,200 ticks if every neuron fired)


async def watch_for_skipped_steps(dut, skipped):
    """Record every tick where start_step is 1 but the core is still busy."""
    tick = 0
    while True:
        await FallingEdge(dut.clk)
        tick += 1
        if int(dut.start_step.value) == 1 and int(dut.worm.busy.value) == 1:
            skipped.append(tick)


async def wait_for(dut, signal, value, limit, what):
    ticks = 0
    while int(signal.value) != value:
        await FallingEdge(dut.clk)
        ticks += 1
        assert ticks <= limit, f"waited {limit} ticks for {what}"


@cocotb.test()
async def board_run_matches_python(dut):
    back_motors, forward_motors = full_motors()
    inputs = hex_lines("full_inputs.txt")
    want = expected_run(hex_lines("full_expected_spikes.txt"), back_motors, forward_motors)
    cocotb.start_soon(Clock(dut.clk, 20, unit="ns").start())   # 50 MHz, like the board

    # hold reset for a few ticks, like pressing btnC
    dut.btnC.value = 1
    dut.btnU.value = 0
    dut.btnD.value = 0
    for _ in range(5):
        await FallingEdge(dut.clk)
    dut.btnC.value = 0

    skipped = []
    cocotb.start_soon(watch_for_skipped_steps(dut, skipped))

    for step, x in enumerate(inputs):
        head, tail = (x >> 1) & 1, x & 1
        dut.btnU.value = head          # "hold" the buttons for this step
        dut.btnD.value = tail
        await wait_for(dut, dut.worm.busy, 1, 2 * STEP_TICKS, f"step {step} to start")
        await wait_for(dut, dut.worm.busy, 0, STEP_TICKS, f"step {step} to finish")

        led = int(dut.led.value)
        got = {"backward": (led >> 15) & 1, "forward": (led >> 14) & 1, "speed": led & 0x7F,
               "head": (led >> 12) & 1, "tail": (led >> 11) & 1}
        back, forward, direction, speed = want[step]
        expect = {"backward": int(direction == 1), "forward": int(direction == 2), "speed": speed,
                  "head": head, "tail": tail}
        assert got == expect, f"step {step}: LEDs {got}, expected {expect} (back={back}, forward={forward})"
        dut._log.info(f"  step {step:2d}, head {head} tail {tail}: "
                      f"{'●' if got['backward'] else '○'} back  {'●' if got['forward'] else '○'} fwd  "
                      f"speed {speed:2d}  ({DIRECTIONS[direction]})")

    assert not skipped, f"start_step arrived while busy (a skipped step) at ticks {skipped[:5]}"
    dut._log.info(f"PASS: the LEDs match Python for all {len(inputs)} steps, no skipped steps")


if __name__ == "__main__":
    from cocotb_tools.runner import get_runner

    runner = get_runner("icarus")
    runner.build(sources=[HERE / "top.v", HERE / "core.v", HERE / "lif_math.v"],
                 hdl_toplevel="top", parameters={"STEP_TICKS": STEP_TICKS},
                 build_dir=HERE / "sim_build" / "top", timescale=("1ns", "1ps"),
                 always=True, waves=True)
    runner.test(hdl_toplevel="top", test_module="test_top", test_dir=HERE, waves=True)
