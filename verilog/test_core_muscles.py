"""cocotb test: the muscle readout against the Python rules, for the full 80-step worm run.

Run from the repo root (make the .mem files first with python/make_mem.py):

    .venv/bin/python verilog/test_core_muscles.py

It replays the head + tail pokes from data/full_inputs.txt. The expected answers come from
data/full_expected_spikes.txt, run through the same rules as python/touch_test.ipynb:
    1. leak both buckets:  bucket = bucket - (bucket >> 2)
    2. add 1 for each motor in that group that fired this step
    3. both buckets below 8                -> stop, speed 0
       otherwise, back > forward           -> backward, speed = back - forward
       otherwise (a tie goes to forward)   -> forward,  speed = forward - back
After busy goes back to 0, it checks the buckets first, then the direction and speed.

What core.v needs, on top of test_core_pipes.py:
    these outputs, which must hold this step's answer once busy goes back to 0:
        back_muscle, forward_muscle   the two buckets (7 bits is enough, see below)
        wheel_direction               2 bits: 0 = stop, 1 = backward, 2 = forward
        wheel_speed                   same width as the buckets
    a memory loaded from motor_role.mem, one line per neuron:
        0 = not a motor, 1 = backward motor (DA/VA), 2 = forward motor (DB/VB)
    both buckets start at 0 on reset

The logic can go in core.v or in a new verilog/muscle_readout.v. All the core tests pick that
file up by itself, but Vivado needs it added by hand. The tick count isn't checked here.

This run never has a tie at 8 or above, so a wrong tie rule still passes. Check that rule by eye.

A bucket can't pass 87: with all 21 backward motors firing, it settles where the leak (1/4)
equals what's added (21).
"""
import sys
from pathlib import Path

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import FallingEdge, RisingEdge

HERE = Path(__file__).resolve().parent
DATA = HERE.parent / "data"
sys.path.insert(0, str(HERE.parent / "python"))
from make_mem import full_motors, full_network, full_pipes  # noqa: E402

MUSCLE_LEAK = 2   # must match python/touch_test.ipynb
STOP_BELOW = 8
OUTPUTS = ("back_muscle", "forward_muscle", "wheel_direction", "wheel_speed")
DIRECTIONS = {0: "stop", 1: "backward", 2: "forward"}


def hex_lines(name):
    return [int(line, 16) for line in (DATA / name).read_text().split()]


def decide(back, forward):
    """-> (direction code, speed), the Wheels part of the notebook."""
    if back < STOP_BELOW and forward < STOP_BELOW:
        return 0, 0
    if back > forward:
        return 1, back - forward
    return 2, forward - back


def expected_run(steps_of_spikes, back_motors, forward_motors):
    """One row per step: (back, forward, direction code, speed)."""
    back, forward, rows = 0, 0, []
    for fired in steps_of_spikes:
        back -= back >> MUSCLE_LEAK
        forward -= forward >> MUSCLE_LEAK
        back += sum((fired >> m) & 1 for m in back_motors)
        forward += sum((fired >> m) & 1 for m in forward_motors)
        rows.append((back, forward, *decide(back, forward)))
    return rows


def read(signal):
    """The signal as a number, or as its raw bits if any of them are x or z."""
    value = signal.value
    return int(value) if value.is_resolvable else str(value)


@cocotb.test()
async def muscles_match_python(dut):
    missing = [name for name in OUTPUTS if not hasattr(dut, name)]
    assert not missing, (f"core.v has no output called: {', '.join(missing)} "
                         f"(the top of this file lists what's needed)")

    back_motors, forward_motors = full_motors()
    inputs = hex_lines("full_inputs.txt")
    spikes = hex_lines("full_expected_spikes.txt")
    want = expected_run(spikes, back_motors, forward_motors)
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())

    dut.reset.value = 1
    dut.start_step.value = 0
    dut.pokes.value = 0
    for _ in range(3):
        await RisingEdge(dut.clk)
    await FallingEdge(dut.clk)  # change inputs halfway between rising edges
    dut.reset.value = 0

    for step, x in enumerate(inputs):
        head, tail = (x >> 1) & 1, x & 1
        dut.pokes.value = head | (tail << 1)   # bit p = poke p
        await FallingEdge(dut.clk)
        dut.start_step.value = 1               # "do a step", for one tick
        await FallingEdge(dut.clk)
        dut.start_step.value = 0

        ticks = 0
        while int(dut.busy.value) == 1:
            await FallingEdge(dut.clk)
            ticks += 1
            assert ticks <= 20000, f"step {step}: busy still 1 after {ticks} ticks"

        back, forward, direction, speed = want[step]
        got_buckets = (read(dut.back_muscle), read(dut.forward_muscle))
        assert got_buckets == (back, forward), (
            f"step {step}: chip buckets back={got_buckets[0]} forward={got_buckets[1]}, "
            f"Python back={back} forward={forward}. Motors that fired this step: "
            f"{sum((spikes[step] >> m) & 1 for m in back_motors)} backward, "
            f"{sum((spikes[step] >> m) & 1 for m in forward_motors)} forward")
        got_wheels = (read(dut.wheel_direction), read(dut.wheel_speed))
        assert got_wheels == (direction, speed), (
            f"step {step} (back={back}, forward={forward}): chip direction={got_wheels[0]} "
            f"speed={got_wheels[1]}, Python {direction} ({DIRECTIONS[direction]}) speed={speed}")
        dut._log.info(f"  step {step:2d}, head {head} tail {tail}: back {back:2d}, "
                      f"forward {forward:2d} -> {DIRECTIONS[direction]} {speed}")
    dut._log.info(f"PASS: the muscle readout matches Python for all {len(inputs)} steps")


if __name__ == "__main__":
    from cocotb_tools.runner import get_runner

    connections, poke_connections = full_network()
    parameters = {
        "N": len(connections),
        "N_LINKS": sum(len(out) for out in connections),
        "N_POKES": len(poke_connections),
        "N_POKE_LINKS": sum(len(out) for out in poke_connections),
        "N_PIPES": len(full_pipes()),
        "MEM_DIR": '"../data/mem/full"',  # relative to verilog/, where the test runs
    }
    runner = get_runner("icarus")
    runner.build(sources=[HERE / "core.v", HERE / "lif_math.v", *HERE.glob("muscle_readout.v")],
                 hdl_toplevel="core", parameters=parameters, build_dir=HERE / "sim_build" / "muscles",
                 timescale=("1ns", "1ps"), always=True)
    runner.test(hdl_toplevel="core", test_module="test_core_muscles", test_dir=HERE)
