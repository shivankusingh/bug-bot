"""Connectome parser: turns the Cook et al. 2019 wiring spreadsheet into
bug-bot's `connections` and `pipes` lists, with + / - signs layered from
Fenyves et al. 2020, a touch rule, and the GABA rule.

Run from the repo folder:
    .venv/bin/python python/connectome_parser.py          # 14-neuron touch circuit
    .venv/bin/python python/connectome_parser.py --all    # all 300 neurons

Reads two files from data/raw/ (git ignores that folder):
    cook2019_SI5_corrected_July2020.xlsx
        Cook et al. 2019, Nature 571:63-71, SI 5 (corrected July 2020).
        Copy used: github.com/openworm/ConnectomeToolbox, cect/data/
    fenyves2020_S1_Data.xlsx
        Fenyves et al. 2020, PLOS Comput Biol 16(12):e1007974, S1 Data.
        journals.plos.org/ploscompbiol/article/file?type=supplementary&id=10.1371/journal.pcbi.1007974.s003

Writes python/touch_circuit.py (or python/connectome_all.py) and prints a
check report. It only builds lists; it does not touch the neuron model.
"""
import argparse
import math
import runpy
from pathlib import Path

import openpyxl

REPO = Path(__file__).resolve().parent.parent
COOK_FILE = REPO / "data" / "raw" / "cook2019_SI5_corrected_July2020.xlsx"
SIGN_FILE = REPO / "data" / "raw" / "fenyves2020_S1_Data.xlsx"

# ---- Your decisions ----
K = 10                                   # Q2: weight = size * K
SIGN_ORDER = ["team", "touch", "table", "gaba"]  # Q3: the first rule with an answer wins

# Q1: the touch circuit, grouped by role
HEAD_TOUCH = ["ALML", "ALMR", "AVM"]
TAIL_TOUCH = ["PLML", "PLMR", "PVM"]
BACKWARD = ["AVAL", "AVAR", "AVDL", "AVDR"]
FORWARD = ["AVBL", "AVBR", "PVCL", "PVCR"]
TOUCH_CIRCUIT = HEAD_TOUCH + TAIL_TOUCH + BACKWARD + FORWARD

INT16_MAX = 32767


# ---------------------------------------------------------------- reading

def read_cook_sheet(workbook, sheet_name):
    """Return (sender names in sheet order, {(sender, receiver): size}).

    SI 5 layout: row 3 holds receiver names from column D on; from row 4
    down, column C holds the sender name. Sizes are EM serial sections.
    """
    rows = list(workbook[sheet_name].iter_rows(values_only=True))
    receivers = {col: str(name).strip() for col, name in enumerate(rows[2]) if col >= 3 and name}
    senders = []
    sizes = {}
    for row in rows[3:]:
        if not row[2]:
            continue
        sender = str(row[2]).strip()
        senders.append(sender)
        for col, receiver in receivers.items():
            value = row[col] if col < len(row) else None
            if value not in (None, "") and float(value) > 0:
                sizes[(sender, receiver)] = int(float(value))
    return senders, sizes


def read_sign_table(workbook):
    """Return ({(sender, receiver): (sign, matched receptor types)}, GABA neurons).

    Sheet '5. Sign prediction', columns G-L are True when the receiver has a
    receptor that matches the sender's chemical:
        G Glu+   H Glu-   I ACh+   J ACh-   K GABA+   L GABA-
    Only + matches -> '+', only - -> '-', both -> 'complex', none -> 'none'.
    GABA neurons = dominant neurotransmitter is GABA (sheet '1. NT expr').
    """
    types = ["Glu+", "Glu-", "ACh+", "ACh-", "GABA+", "GABA-"]
    signs = {}
    for row in list(workbook["5. Sign prediction"].iter_rows(values_only=True))[2:]:
        if not row[0] or not row[3] or str(row[5]).strip().lower() != "chemical":
            continue
        matched = [t for t, flag in zip(types, row[6:12]) if flag is True]
        plus = any(t.endswith("+") for t in matched)
        minus = any(t.endswith("-") for t in matched)
        if plus and minus:
            sign = "complex"
        elif plus:
            sign = "+"
        elif minus:
            sign = "-"
        else:
            sign = "none"
        signs[(str(row[0]).strip(), str(row[3]).strip())] = (sign, matched)

    gaba = set()
    for row in list(workbook["1. NT expr"].iter_rows(values_only=True))[1:]:
        if row[0] and row[1] == "GABA":
            gaba.add(str(row[0]).strip())
    return signs, gaba


# ---------------------------------------------------------------- signs

def touch_rule(sender, receiver):
    """Chalfie et al. 1985: touch -> opposite-direction decision neuron is '-'."""
    if sender in HEAD_TOUCH and receiver in FORWARD:
        return "-"
    if sender in TAIL_TOUCH and receiver in BACKWARD:
        return "-"
    return None  # the rule has nothing to say about this connection

def team_rule(sender, receiver):
    """Team rule: if sender is in the same team as the receiver, return +, oposite team is -. else it is NONE."""
    if sender in BACKWARD and receiver in BACKWARD:
        return "+"
    if sender in FORWARD and receiver in FORWARD:
        return "+"
    if sender in BACKWARD and receiver in FORWARD:
        return "-"
    if sender in FORWARD and receiver in BACKWARD:
        return "-"
    return None  # the rule has nothing to say about this connection

def decide_sign(sender, receiver, sign_table, gaba):
    """Return (sign, rule that decided it, what the table said)."""
    table_says = sign_table.get((sender, receiver), ("missing", []))[0]
    for rule in SIGN_ORDER:
        if rule == "table" and table_says in ("+", "-"):
            return table_says, "table", table_says
        if rule == "table" and table_says == "complex":
            return "-", "table", table_says
        if rule == "touch" and touch_rule(sender, receiver):
            return touch_rule(sender, receiver), "touch", table_says
        if rule == "gaba":
            return ("-" if sender in gaba else "+"), "gaba", table_says
        if rule == "team" and team_rule(sender, receiver):
            return team_rule(sender, receiver), "team", table_says
    raise ValueError("SIGN_ORDER must include 'gaba' so every connection gets a sign")




# ---------------------------------------------------------------- building

def build(neurons, chem_sizes, gap_sizes, sign_table, gaba):
    """Return (connections, pipes, pipe_mismatches) for the chosen neurons.

    connections[i] = list of dicts, one per outgoing chemical connection.
    pipes = {(a, b): size}, each pair once, a before b in neuron order.
    """
    index = {name: i for i, name in enumerate(neurons)}
    connections = [[] for _ in neurons]
    for (sender, receiver), size in chem_sizes.items():
        if sender in index and receiver in index and sender != receiver:
            sign, rule, table_says = decide_sign(sender, receiver, sign_table, gaba)
            weight = size * K if sign == "+" else -size * K
            connections[index[sender]].append(dict(
                receiver=receiver, weight=weight, size=size,
                sign=sign, rule=rule, table_says=table_says))
    for outgoing in connections:
        outgoing.sort(key=lambda c: index[c["receiver"]])

    pipes = {}
    mismatches = []
    for (a, b), size in gap_sizes.items():
        if a in index and b in index and a != b:
            pair = tuple(sorted((a, b), key=index.get))
            if pair in pipes and pipes[pair] != size:
                mismatches.append((pair, pipes[pair], size))
            pipes[pair] = size  # the symmetric sheet lists each pair twice
    return connections, pipes, mismatches


# ---------------------------------------------------------------- output file

def write_module(path, neurons, connections, pipes):
    out = [
        "# GENERATED by python/connectome_parser.py. Don't edit by hand: rerun the parser.",
        "# Wiring: Cook et al. 2019 SI 5 (corrected July 2020).",
        "# Signs: Fenyves et al. 2020 S1 Data, touch rule (Chalfie et al. 1985), GABA rule.",
        f"# Settings: K = {K}, sign order = {' -> '.join(SIGN_ORDER)}",
        "",
        f"N = {len(neurons)}",
        "neurons = [" + ", ".join(f'"{n}"' for n in neurons) + "]",
        "",
        "# one name per index, like A, B, C, I = 0, 1, 2, 3",
    ]
    rows = [", ".join(neurons[i:i + 10]) for i in range(0, len(neurons), 10)]
    out.append("(" + ",\n ".join(rows) + ") = range(N)")
    out += [
        "",
        "# connections[sender] = list of (receiver, weight); weight = sign * size * K",
        "connections = [",
    ]
    for i, outgoing in enumerate(connections):
        if not outgoing:
            out.append(f"    [],  # {i} {neurons[i]} -> nobody inside this circuit")
            continue
        out.append(f"    [  # {i} {neurons[i]}")
        for c in outgoing:
            entry = f"({c['receiver']}, {c['weight']}),"
            source = "table" if c["rule"] == "table" else c["rule"] + " rule"
            out.append(f"        {entry:<16} # size {c['size']}, {c['sign']} from {source}")
        out.append("    ],")
    out += [
        "]",
        "",
        "# pipes = list of (a, b, size), each pair once (gap junctions)",
        "pipes = [",
    ]
    out += [f"    ({a}, {b}, {size})," for (a, b), size in pipes.items()]
    out += ["]", ""]
    path.write_text("\n".join(out))


def self_check(path, neurons, connections, pipes):
    """Load the written file back and make sure it says what we meant."""
    m = runpy.run_path(str(path))
    assert m["N"] == len(neurons) == len(m["neurons"]) == len(m["connections"])
    for i, name in enumerate(neurons):
        assert m[name] == i, f"{name} should be index {i}"
        written = m["connections"][i]
        meant = [(neurons.index(c["receiver"]), c["weight"]) for c in connections[i]]
        assert written == meant, f"connections for {name} don't match"
    for outgoing in m["connections"]:
        for _, weight in outgoing:
            assert isinstance(weight, int) and abs(weight) <= INT16_MAX
    seen = set()
    for a, b, size in m["pipes"]:
        assert a < b and (a, b) not in seen and size > 0
        seen.add((a, b))
    assert len(seen) == len(pipes)


# ---------------------------------------------------------------- report

def report(neurons, connections, pipes, mismatches, chem_sizes, sign_table):
    index = {name: i for i, name in enumerate(neurons)}
    flat = [(neurons[i], c) for i, outgoing in enumerate(connections) for c in outgoing]

    print("=" * 74)
    print(f"1. WHAT WAS BUILT  ({len(neurons)} neurons, K = {K}, "
          f"sign order {' -> '.join(SIGN_ORDER)})")
    print("=" * 74)
    print(f"  chemical connections : {len(flat)}")
    print(f"  pipes (gap junctions): {len(pipes)}   size mismatches between directions: {len(mismatches)}")
    selfs = sum(1 for (a, b) in chem_sizes if a == b and a in index)
    print(f"  self-connections dropped: {selfs}")

    print()
    print("=" * 74)
    print("2. WHO DECIDED EACH SIGN")
    print("=" * 74)
    for rule in SIGN_ORDER:
        for sign in "+-":
            n = sum(1 for _, c in flat if c["rule"] == rule and c["sign"] == sign)
            if n:
                print(f"  {rule:<6} {sign} : {n}")
    for said in ("complex", "none", "missing"):
        n = sum(1 for _, c in flat if c["table_says"] == said)
        print(f"  table had no clear sign ({said}): {n}")
    absent = sorted(n for n in neurons if not any(n in pair for pair in sign_table))
    if absent:
        print(f"  neurons the table leaves out entirely: {', '.join(absent)}")

    print()
    print("=" * 74)
    print("3. SAFETY NET: every touch -> decision-neuron chemical connection")
    print("=" * 74)
    print(f"  {'link':<12} {'size':>4}  {'table':<8} {'touch rule':<10} {'final':<5} {'decided by':<10} note")
    for sender, c in flat:
        if sender in HEAD_TOUCH + TAIL_TOUCH and c["receiver"] in BACKWARD + FORWARD:
            rule_says = touch_rule(sender, c["receiver"]) or "(none)"
            note = ""
            if rule_says == "-" and c["table_says"] == "+":
                note = "DISAGREE: table says +, Chalfie says -"
            elif rule_says == "-" and c["rule"] == "touch":
                note = f"table {c['table_says']}, so touch rule used"
            print(f"  {sender + '->' + c['receiver']:<12} {c['size']:>4}  {c['table_says']:<8} "
                  f"{rule_says:<10} {c['sign']:<5} {c['rule']:<10} {note}")

    print()
    print("  Rough first push (signed sizes of direct links, pipes counted as +).")
    print("  Not a simulation. Chalfie: head touch -> backward, tail touch -> forward.")
    for label, touch, right, wrong in (("head touch", HEAD_TOUCH, BACKWARD, FORWARD),
                                       ("tail touch", TAIL_TOUCH, FORWARD, BACKWARD)):
        def push(targets):
            chem = sum((1 if c["sign"] == "+" else -1) * c["size"]
                       for s, c in flat if s in touch and c["receiver"] in targets)
            gap = sum(size for (a, b), size in pipes.items()
                      if (a in touch and b in targets) or (b in touch and a in targets))
            return chem, gap
        rc, rg = push(right)
        wc, wg = push(wrong)
        verdict = "matches Chalfie" if rc + rg > wc + wg else "WRONG direction wins"
        right_name = "backward" if right is BACKWARD else "forward"
        wrong_name = "forward" if right is BACKWARD else "backward"
        print(f"    {label}: {right_name} {rc:+d} chem {rg:+d} pipe = {rc + rg:+d} | "
              f"{wrong_name} {wc:+d} chem {wg:+d} pipe = {wc + wg:+d}  -> {verdict}")

    print()
    print("=" * 74)
    print("4. 16-BIT CHECK: one step where every incoming connection fires at once")
    print("=" * 74)
    incoming_pos = [0] * len(neurons)
    incoming_neg = [0] * len(neurons)
    for _, c in flat:
        if c["weight"] > 0:
            incoming_pos[index[c["receiver"]]] += c["weight"]
        else:
            incoming_neg[index[c["receiver"]]] += c["weight"]
    hi = max(range(len(neurons)), key=lambda i: incoming_pos[i])
    lo = min(range(len(neurons)), key=lambda i: incoming_neg[i])
    for label, i, value in (("most +", hi, incoming_pos[hi]), ("most -", lo, incoming_neg[lo])):
        fits = "fits" if abs(value) <= INT16_MAX else "DOES NOT FIT"
        print(f"  {label}: {neurons[i]} {value:+d}  ({fits} in +/-{INT16_MAX}; pokes add on top)")

    print()
    print("=" * 74)
    print("5. PIPE STRENGTH: all of a neuron's pipes together should move <= 1/2")
    print("=" * 74)
    pipe_sum = [0] * len(neurons)
    for (a, b), size in pipes.items():
        pipe_sum[index[a]] += size
        pipe_sum[index[b]] += size
    busiest = max(range(len(neurons)), key=lambda i: pipe_sum[i])
    total = pipe_sum[busiest]
    if total:
        print(f"  busiest: {neurons[busiest]}, pipes total {total}")
        for shift in (6, 7, 8, 9, 10):
            share = total / 2 ** shift
            print(f"    pipe_shift {shift:>2}: moves {total}/{2 ** shift} = {share:.2f}  "
                  f"{'ok' if share <= 0.5 else 'too strong'}")
        print(f"  smallest safe pipe_shift: {math.ceil(math.log2(2 * total))}")

    print()
    print("=" * 74)
    print("6. CHECK BY HAND: open the spreadsheets and compare")
    print("=" * 74)
    picks = []
    for rule in SIGN_ORDER:
        options = [(s, c) for s, c in flat if c["rule"] == rule]
        if options:
            picks.append(max(options, key=lambda sc: sc[1]["size"]))
    for sender, c in picks:
        matched = sign_table.get((sender, c["receiver"]), (None, []))[1]
        print(f"  {sender} -> {c['receiver']}: Cook sheet 'hermaphrodite chemical', row {sender}, "
              f"column {c['receiver']} = {c['size']}")
        print(f"      sign {c['sign']} from {c['rule']} (table: {c['table_says']}"
              f"{', matched ' + ' '.join(matched) if matched else ''}); "
              f"weight = {'-' if c['sign'] == '-' else ''}{c['size']} x {K} = {c['weight']}")
    if pipes:
        (a, b), size = max(pipes.items(), key=lambda kv: kv[1])
        print(f"  pipe {a} <-> {b}: Cook sheet 'hermaphrodite gap jn symmetric', row {a}, "
              f"column {b} = {size}")


# ---------------------------------------------------------------- main

def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--all", action="store_true", help="all neurons instead of the touch circuit")
    args = parser.parse_args()

    cook = openpyxl.load_workbook(COOK_FILE, read_only=True, data_only=True)
    all_neurons, chem_sizes = read_cook_sheet(cook, "hermaphrodite chemical")
    _, gap_sizes = read_cook_sheet(cook, "hermaphrodite gap jn symmetric")
    sign_table, gaba = read_sign_table(openpyxl.load_workbook(SIGN_FILE, read_only=True, data_only=True))

    neurons = all_neurons if args.all else TOUCH_CIRCUIT
    missing = [n for n in neurons if n not in all_neurons]
    assert not missing, f"not in the Cook sheet: {missing}"

    connections, pipes, mismatches = build(neurons, chem_sizes, gap_sizes, sign_table, gaba)
    out_path = REPO / "python" / ("connectome_all.py" if args.all else "touch_circuit.py")
    write_module(out_path, neurons, connections, pipes)
    self_check(out_path, neurons, connections, pipes)

    report(neurons, connections, pipes, mismatches, chem_sizes, sign_table)
    print()
    print(f"Wrote {out_path.relative_to(REPO)} and read it back: self-check passed.")


if __name__ == "__main__":
    main()
