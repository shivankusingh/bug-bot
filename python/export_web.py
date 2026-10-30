"""Export one simulation run for the bug-bot website (the 3D brain visualizer).

Use from a notebook in python/, after your loop has filled all_spikes, all_voltages and wheels:

    from export_web import export_web
    export_web(all_spikes, all_voltages, pokes, wheels, "path/to/run.json")

The website only plays this file back; the model itself stays in the notebook.
Writes one JSON file with:
    neurons  name, team (0 other, 1 backward, 2 forward), kind (0 other, 1 sensor,
             2 command, 3 motor) and a 3D position from a force layout
    links    every chemical connection as [sender, receiver, +1 or -1]
    run      pokes, which neurons fired each step, every voltage, and the wheels
"""
import json
from pathlib import Path

import numpy as np

import connectome_all as net
from connectome_parser import CIRCUIT, SENSOR, COMMAND, MOTOR, K

TEAM = {"backward": 1, "forward": 2}
KIND = {SENSOR: 1, COMMAND: 2, MOTOR: 3}


def layout(n, edges, team, kind, steps=700, seed=7):
    """3D force layout: linked neurons attract, all neurons repel, and tagged neurons
    are gently pulled toward an anchor so the backward team gathers on the left (-x),
    the forward team on the right (+x), sensors higher and motors lower."""
    rng = np.random.default_rng(seed)
    pos = rng.normal(size=(n, 3))
    a = np.array([e[0] for e in edges])
    b = np.array([e[1] for e in edges])
    strength = np.array([e[2] for e in edges], dtype=float)
    side = np.where(team == 1, -1.0, np.where(team == 2, 1.0, 0.0))
    height = np.select([kind == 1, kind == 2, kind == 3], [0.6, 0.0, -0.6], 0.0)
    tagged = team > 0
    for step in range(steps):
        cool = 1.0 - step / steps
        delta = pos[:, None, :] - pos[None, :, :]
        dist2 = (delta ** 2).sum(-1) + 0.01
        force = 0.02 * (delta / dist2[..., None] ** 1.5).sum(1)            # repel
        pull = pos[b] - pos[a]
        length = np.linalg.norm(pull, axis=1, keepdims=True) + 1e-9
        spring = 0.004 * strength[:, None] * (length - 0.35) * pull / length
        np.add.at(force, a, spring)                                          # attract
        np.add.at(force, b, -spring)
        force -= 0.05 * pos                                                  # stay centered
        pos += np.clip(force, -0.1, 0.1) * (0.3 + cool)
        size = np.sqrt((pos ** 2).sum(1)).mean()
        anchor = np.stack([1.2 * size * side, size * height, np.zeros(n)], 1)
        pos[tagged] += 0.015 * (anchor[tagged] - pos[tagged])               # teams gather
    pos -= np.median(pos, 0)
    return pos / np.percentile(np.abs(pos), 98)


def export_web(all_spikes, all_voltages, pokes, wheels, path):
    neurons = list(net.neurons)
    n = len(neurons)
    if not (len(all_spikes) == len(all_voltages) == len(pokes) == len(wheels)):
        raise ValueError("all_spikes, all_voltages, pokes and wheels need one row per step")
    team = np.array([TEAM[CIRCUIT[name][0]] if name in CIRCUIT else 0 for name in neurons])
    kind = np.array([KIND[CIRCUIT[name][1]] if name in CIRCUIT else 0 for name in neurons])

    links = [[s, r, 1 if w > 0 else -1] for s, outgoing in enumerate(net.connections) for r, w in outgoing]
    strength = {}
    for s, outgoing in enumerate(net.connections):
        for r, w in outgoing:
            key = (min(s, r), max(s, r))
            strength[key] = strength.get(key, 0) + abs(w) / K   # back to synapse counts
    for a, b, size in net.pipes:
        key = (min(a, b), max(a, b))
        strength[key] = strength.get(key, 0) + size
    edges = [(a, b, float(np.log1p(s))) for (a, b), s in strength.items()]
    pos = layout(n, edges, team, kind)

    data = {
        "neurons": {
            "name": neurons,
            "team": team.tolist(),
            "kind": kind.tolist(),
            "pos": [[round(float(c), 3) for c in p] for p in pos],
        },
        "links": links,
        "run": {
            "pokes": [list(row) for row in pokes],
            "fired": [[i for i, s in enumerate(row) if s] for row in all_spikes],
            "v": [list(row) for row in all_voltages],
            "wheels": [list(w) for w in wheels],
        },
        "settings": {"neurons": n, "chemical_links": len(links), "pipes": len(net.pipes),
                     "threshold": 256, "floor": -512, "K": K},
    }
    path = Path(path)
    path.write_text(json.dumps(data, separators=(",", ":")))
    print(f"Wrote {path.name}: {n} neurons, {len(links)} links, {len(all_spikes)} steps, "
          f"{path.stat().st_size // 1024} KB")
