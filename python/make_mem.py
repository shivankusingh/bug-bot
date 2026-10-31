"""Turn a network into .mem files the Verilog core loads with $readmemh.

Run from the repo root:

    .venv/bin/python python/make_mem.py

Writes two sets, one folder each:
    data/mem/chain/   the 4-neuron test network (A, B, C, I)
    data/mem/full/    the 300-neuron worm (connectome_all.py + the head/tail touch pokes)

Each folder holds the wiring in CSR form (flat lists glued sender by sender, plus a START
list where neuron i's links are slots START[i] .. START[i+1]-1):
    link_receiver.mem   one line per link: who gets the mail (neuron number)
    link_weight.mem     one line per link: how strong, WEIGHT_BITS-bit two's complement
                        (11 bits: -400 -> 670)
    start.mem           one line per neuron, plus one "end" line: first slot of each sender
    poke_receiver.mem   same three lists for the pokes
    poke_weight.mem
    poke_start.mem
All numbers are hex, one per line, line k = slot k.
"""
from pathlib import Path

MEM = Path(__file__).resolve().parent.parent / "data" / "mem"
WEIGHT_BITS = 11  # must match the width of link_weight and poke_weight in verilog/core.v


def to_csr(lists):
    """[[(receiver, weight), ...] per sender] -> (receivers, weights, start)."""
    receivers, weights, start = [], [], []
    for outgoing in lists:
        start.append(len(receivers))          # this sender's links begin here
        for receiver, weight in outgoing:
            receivers.append(receiver)
            weights.append(weight)
    start.append(len(receivers))              # the extra "end" slot
    return receivers, weights, start


def _write(path, numbers, width=None):
    """width=None: plain hex. width=11: 11-bit two's complement, in 3 hex digits."""
    if width:
        lines = [f"{n & ((1 << width) - 1):0{(width + 3) // 4}x}" for n in numbers]
    else:
        lines = [f"{n:x}" for n in numbers]
    path.write_text("".join(line + "\n" for line in lines))


def write_mem(connections, poke_connections, folder):
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    for prefix, lists in (("link", connections), ("poke", poke_connections)):
        receivers, weights, start = to_csr(lists)
        low, high = -(1 << (WEIGHT_BITS - 1)), (1 << (WEIGHT_BITS - 1)) - 1
        for w in weights:
            if not low <= w <= high:
                raise ValueError(f"weight {w} doesn't fit in {WEIGHT_BITS} signed bits ({low} to {high})")
        _write(folder / f"{prefix}_receiver.mem", receivers)
        _write(folder / f"{prefix}_weight.mem", weights, width=WEIGHT_BITS)
        _write(folder / ("start.mem" if prefix == "link" else "poke_start.mem"), start)
        print(f"  {prefix}s: {len(receivers)} slots, weights {min(weights)} to {max(weights)}, "
              f"start has {len(start)} slots (biggest {start[-1]})")
    # print only the folder name, so nothing personal ends up in notebook outputs
    print(f"Wrote {folder.parent.name}/{folder.name}/ for {len(connections)} neurons")


def chain_network():
    """The 4-neuron test network (same as python/bug_bot.ipynb)."""
    A, B, C, I = 0, 1, 2, 3
    connections = [[(B, 300)], [(C, 300)], [], [(B, -400)]]
    poke_connections = [[(A, 300)], [(I, 300)]]
    return connections, poke_connections


def full_network():
    """The 300-neuron worm with the touch pokes (same as python/touch_test.ipynb)."""
    import connectome_all as net
    poke_connections = [
        [(net.ALML, 300), (net.ALMR, 300), (net.AVM, 300)],   # head touch
        [(net.PLML, 300), (net.PLMR, 300), (net.PVM, 300)],   # tail touch
    ]
    return net.connections, poke_connections


if __name__ == "__main__":
    write_mem(*chain_network(), MEM / "chain")
    write_mem(*full_network(), MEM / "full")
