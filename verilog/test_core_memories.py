"""cocotb test: checks that core.v declares its memories and loads them from the .mem files.

Run from the repo root (make the .mem files first with python/make_mem.py):

    .venv/bin/python verilog/test_core_memories.py

It builds core.v twice, once per network, and after loading checks every slot:
    chain   the 4-neuron test network   (data/mem/chain)
    full    the 300-neuron worm         (data/mem/full)

What core.v needs (names must match):
    parameters  N, N_LINKS, N_POKES, N_POKE_LINKS, MEM_DIR (a string, the folder to load from)
    ports       clk, reset
    memories    link_receiver, link_weight, start, poke_receiver, poke_weight, poke_start
                (loaded from MEM_DIR), and voltages, totals, spikes (N slots each, all 0 at start)
"""
import sys
from pathlib import Path

import cocotb
from cocotb.triggers import Timer

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "python"))
from make_mem import chain_network, full_network, to_csr  # noqa: E402

NETWORKS = {"chain": chain_network, "full": full_network}


def read(memory, slot, signed=False):
    value = memory[slot].value
    if str(value).lower().strip("01"):  # any x or z bit: the slot was never given a value
        return str(value)
    if not hasattr(value, "to_signed"):  # a 1-bit slot comes back as a single bit
        return int(value)
    return value.to_signed() if signed else value.to_unsigned()


def check(dut, name, want, signed=False):
    try:
        memory = getattr(dut, name)
    except AttributeError:
        raise AssertionError(
            f"core.v has no memory called {name}. Check the spelling. If it is declared, "
            f"Icarus may have removed it because nothing ever gives it a value: "
            f"load it with $readmemh, or set every slot to 0 at the start") from None
    for slot, expected in enumerate(want):
        got = read(memory, slot, signed)
        assert got == expected, f"{name}[{slot}] is {got}, should be {expected}"
    dut._log.info(f"  {name}: all {len(want)} slots OK")


@cocotb.test()
async def memories_load(dut):
    network = cocotb.plusargs["network"]
    connections, poke_connections = NETWORKS[network]()
    n = len(connections)
    await Timer(1, unit="ns")  # let the initial blocks run

    receivers, weights, start = to_csr(connections)
    check(dut, "link_receiver", receivers)
    check(dut, "link_weight", weights, signed=True)
    check(dut, "start", start)
    receivers, weights, start = to_csr(poke_connections)
    check(dut, "poke_receiver", receivers)
    check(dut, "poke_weight", weights, signed=True)
    check(dut, "poke_start", start)
    for name in ("voltages", "totals", "spikes"):
        check(dut, name, [0] * n, signed=True)
    dut._log.info(f"PASS: every memory loaded correctly for the {network} network ({n} neurons)")


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
        runner.build(sources=[HERE / "core.v"], hdl_toplevel="core", parameters=parameters,
                     build_dir=HERE / "sim_build" / network, timescale=("1ns", "1ps"), always=True)
        runner.test(hdl_toplevel="core", test_module="test_core_memories", test_dir=HERE,
                    plusargs=[f"+network={network}"])
