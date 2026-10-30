"""Save one simulation run as golden files: the answer key a Verilog testbench checks against.

Use from a notebook in python/, after your loop has filled all_spikes and all_voltages:

    from golden import save_golden
    save_golden(all_spikes, all_voltages, pokes, prefix="full")

Writes three files into data/ (all hex, readable by Verilog's $readmemh):
    <prefix>_inputs.txt           one line per step: the pokes packed, poke 0 as the highest bit
                                  (2 pokes: head*2 + tail, same as chain_inputs.txt)
    <prefix>_expected_spikes.txt  one line per step: an N-bit number, bit i = neuron i fired
    <prefix>_expected_v.txt       one line per (step, neuron), in order step 0 neurons 0..N-1,
                                  then step 1, ...; each voltage as 16-bit two's complement
                                  (line number = step * N + neuron)
"""
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"


def save_golden(all_spikes, all_voltages, pokes, prefix="full", folder=DATA):
    steps, n = len(all_spikes), len(all_spikes[0])
    if len(all_voltages) != steps or len(pokes) != steps:
        raise ValueError(f"need one row per step: {steps} spike rows, "
                         f"{len(all_voltages)} voltage rows, {len(pokes)} poke rows")
    if any(row is all_voltages[0] for row in all_voltages[1:]):
        raise ValueError("all_voltages rows are the same list: append voltages.copy() in your loop")
    for row in all_voltages:
        for v in row:
            if not -32768 <= v <= 32767:
                raise ValueError(f"voltage {v} doesn't fit in 16 bits")

    folder = Path(folder)
    width = (n + 3) // 4  # hex digits for an n-bit spike vector
    inputs = [sum(bit << (len(row) - 1 - p) for p, bit in enumerate(row)) for row in pokes]
    spikes = [sum(bit << i for i, bit in enumerate(row)) for row in all_spikes]
    paths = {
        "inputs": folder / f"{prefix}_inputs.txt",
        "spikes": folder / f"{prefix}_expected_spikes.txt",
        "v": folder / f"{prefix}_expected_v.txt",
    }
    paths["inputs"].write_text("".join(f"{x:x}\n" for x in inputs))
    paths["spikes"].write_text("".join(f"{x:0{width}x}\n" for x in spikes))
    paths["v"].write_text("".join(f"{v & 0xFFFF:04x}\n" for row in all_voltages for v in row))

    _check(paths, all_spikes, all_voltages, inputs)
    # print only the folder name, so notebook outputs don't carry a personal path
    print(f"Wrote {steps} steps x {n} neurons to {folder.name}/:")
    for path in paths.values():
        print(f"  {path.name}: {len(path.read_text().splitlines())} lines")


def _check(paths, all_spikes, all_voltages, inputs):
    """Read the files back the way a testbench would and make sure they decode to the run."""
    n = len(all_spikes[0])
    assert [int(x, 16) for x in paths["inputs"].read_text().split()] == inputs
    for step, line in enumerate(paths["spikes"].read_text().split()):
        word = int(line, 16)
        assert [(word >> i) & 1 for i in range(n)] == list(all_spikes[step]), f"spikes, step {step}"
    words = [int(x, 16) for x in paths["v"].read_text().split()]
    for k, word in enumerate(words):
        v = word - 0x10000 if word & 0x8000 else word  # undo two's complement
        assert v == all_voltages[k // n][k % n], f"voltage, step {k // n}, neuron {k % n}"
