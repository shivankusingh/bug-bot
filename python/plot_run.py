"""Plot one simulation run: who fired, which direction is winning, and every voltage.

Use from a notebook in python/, after your loop has filled all_voltages and all_spikes:

    from plot_run import plot_run
    plot_run(all_voltages, all_spikes, neurons, pokes)

Panels share the same step axis:
    1. Raster: one row per neuron, a mark on every step it fired.
    2. Decision: how many backward vs forward command neurons fired each step.
    3. Motors (only if the network has motor neurons): how many backward (VA/DA)
       vs forward (VB/DB) motor neurons fired each step.
    4. Voltage map: every neuron's voltage each step (blue = pushed up, red = held down).
Shaded columns are the steps a poke was on.
"""
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap, Normalize

# Touch-circuit roles (same groups as the parser). Neurons not listed here are drawn as "other".
GROUPS = {
    "head touch": ["ALML", "ALMR", "AVM"],
    "tail touch": ["PLML", "PLMR", "PVM"],
    "backward": ["AVAL", "AVAR", "AVDL", "AVDR"],
    "forward": ["AVBL", "AVBR", "PVCL", "PVCR"],
}
POKE_NAMES = ["head poked", "tail poked"]

# Motor neurons, matched by name prefix: VA/DA drive backward, VB/DB drive forward.
MOTOR_PREFIXES = {"backward": ("VA", "DA"), "forward": ("VB", "DB")}

# Colors (validated categorical pair + neutral ink; light surface)
SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_2 = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
BACKWARD_COLOR = "#2a78d6"  # blue
FORWARD_COLOR = "#eb6834"   # orange
POKE_SHADE = "#efeee9"
VOLTAGE_CMAP = LinearSegmentedColormap.from_list(
    "held_down_to_pushed_up", ["#c0392f", "#e34948", "#f0efec", "#2a78d6", "#184f95"])
VOLTAGE_LIMIT = 300  # map clips at +/-300 so values near the 256 threshold stay visible


def _group_of(name):
    for group, members in GROUPS.items():
        if name in members:
            return group
    return "other"


def _color_of(group):
    return {"backward": BACKWARD_COLOR, "forward": FORWARD_COLOR}.get(group, INK_2)


def _shade_pokes(ax, pokes):
    """Shade every run of steps where a poke was on, and name it once at the top."""
    for p in range(len(pokes[0])):
        step = 0
        while step < len(pokes):
            if pokes[step][p] == 1:
                start = step
                while step < len(pokes) and pokes[step][p] == 1:
                    step += 1
                ax.axvspan(start - 0.5, step - 0.5, color=POKE_SHADE, zorder=0, lw=0)
                if ax.get_label() == "raster":
                    name = POKE_NAMES[p] if p < len(POKE_NAMES) else f"poke {p}"
                    ax.text((start + step - 1) / 2, -0.9, name, ha="center", va="bottom",
                            fontsize=9, color=INK_2)
            else:
                step += 1


def _style(ax):
    ax.set_facecolor(SURFACE)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color("#c3c2b7")
    ax.tick_params(colors=MUTED, labelcolor=INK_2, labelsize=9)


def plot_run(all_voltages, all_spikes, neurons, pokes, title="Touch test", save_as=None, only=None):
    """only = list of neuron names to draw. With more than 40 neurons and no
    `only`, it draws just the 14 touch-circuit neurons."""
    if any(row is all_voltages[0] for row in all_voltages[1:]):
        raise ValueError("all_voltages rows are the same list: append voltages.copy() in your loop")
    # Motor counts come from the full network, before `only` narrows the rows.
    motor_counts = {}
    for group, prefixes in MOTOR_PREFIXES.items():
        idx = [i for i, name in enumerate(neurons) if name[:2] in prefixes]
        if idx:
            motor_counts[group] = (len(idx), [sum(row[i] for i in idx) for row in all_spikes])
    if only is None and len(neurons) > 40:
        only = [name for members in GROUPS.values() for name in members]
    if only is not None:
        keep = [neurons.index(name) for name in only if name in neurons]
        all_voltages = [[row[i] for i in keep] for row in all_voltages]
        all_spikes = [[row[i] for i in keep] for row in all_spikes]
        neurons = [neurons[i] for i in keep]

    steps = len(all_voltages)
    n = len(neurons)

    if motor_counts:
        fig, (ax_r, ax_d, ax_m, ax_v) = plt.subplots(
            4, 1, figsize=(11, 12.5), sharex=True, facecolor=SURFACE,
            gridspec_kw={"height_ratios": [n, 5, 5, n], "hspace": 0.35})
    else:
        fig, (ax_r, ax_d, ax_v) = plt.subplots(
            3, 1, figsize=(11, 10), sharex=True, facecolor=SURFACE,
            gridspec_kw={"height_ratios": [n, 5, n], "hspace": 0.35})
    fig.suptitle(title, x=0.06, y=0.95, ha="left", fontsize=14, color=INK, fontweight="bold")

    # 1. Raster ---------------------------------------------------------------
    ax_r.set_label("raster")
    _style(ax_r)
    _shade_pokes(ax_r, pokes)
    for i, name in enumerate(neurons):
        color = _color_of(_group_of(name))
        fired = [s for s in range(steps) if all_spikes[s][i] == 1]
        ax_r.scatter(fired, [i] * len(fired), marker="s", s=34, color=color,
                     edgecolors=SURFACE, linewidths=1, zorder=3)
    previous = None
    for i, name in enumerate(neurons):  # hairline + label at each group boundary
        group = _group_of(name)
        if group != previous:
            if i > 0:
                ax_r.axhline(i - 0.5, color=GRID, lw=1, zorder=1)
            size = sum(1 for m in neurons if _group_of(m) == group)
            ax_r.text(steps - 0.3, i + (size - 1) / 2, f" {group}", va="center", ha="left",
                      fontsize=9, color=_color_of(group) if group in ("backward", "forward") else INK_2,
                      fontweight="bold")
            previous = group
    ax_r.set_yticks(range(n), neurons, fontsize=8.5)
    ax_r.set_ylim(n - 0.5, -1.2)
    ax_r.set_title("1. Who fired (one square = one spike)", loc="left", fontsize=11, color=INK)

    # 2. Decision ---------------------------------------------------------------
    _style(ax_d)
    _shade_pokes(ax_d, pokes)
    x = range(steps)
    for group, color in (("backward", BACKWARD_COLOR), ("forward", FORWARD_COLOR)):
        idx = [i for i, name in enumerate(neurons) if _group_of(name) == group]
        if idx:
            counts = [sum(all_spikes[s][i] for i in idx) for s in x]
            ax_d.step(x, counts, where="mid", color=color, lw=2, label=f"{group} ({len(idx)} neurons)")
    ax_d.set_ylim(-0.3, 4.5)
    ax_d.set_yticks(range(5))
    ax_d.set_ylabel("neurons firing", fontsize=9, color=INK_2)
    ax_d.grid(axis="y", color=GRID, lw=0.8)
    ax_d.legend(loc="upper left", bbox_to_anchor=(1.0, 1.0), fontsize=8.5, frameon=False, labelcolor=INK_2)
    ax_d.set_title("2. Which way is winning (command neurons)", loc="left", fontsize=11, color=INK)

    # 3. Motors (only when the network has motor neurons) ------------------------
    if motor_counts:
        _style(ax_m)
        _shade_pokes(ax_m, pokes)
        for group, color in (("backward", BACKWARD_COLOR), ("forward", FORWARD_COLOR)):
            if group in motor_counts:
                size, counts = motor_counts[group]
                prefixes = "/".join(MOTOR_PREFIXES[group])
                ax_m.step(x, counts, where="mid", color=color, lw=2,
                          label=f"{group} motors, {prefixes} ({size} neurons)")
        top = max(max(counts) for _, counts in motor_counts.values())
        ax_m.set_ylim(-0.3, max(4, top) + 0.5)
        ax_m.set_ylabel("neurons firing", fontsize=9, color=INK_2)
        ax_m.grid(axis="y", color=GRID, lw=0.8)
        ax_m.legend(loc="upper left", bbox_to_anchor=(1.0, 1.0), fontsize=8.5, frameon=False, labelcolor=INK_2)
        ax_m.set_title("3. Do the motors follow?", loc="left", fontsize=11, color=INK)

    # Voltage map -----------------------------------------------------------------
    _style(ax_v)
    columns = [[all_voltages[s][i] for s in range(steps)] for i in range(n)]
    image = ax_v.imshow(columns, aspect="auto", cmap=VOLTAGE_CMAP, interpolation="nearest",
                        norm=Normalize(-VOLTAGE_LIMIT, VOLTAGE_LIMIT),
                        extent=(-0.5, steps - 0.5, n - 0.5, -0.5))
    ax_v.set_yticks(range(n), neurons, fontsize=8.5)
    ax_v.set_xlabel("step (one tick of your loop)", fontsize=9, color=INK_2)
    ax_v.set_title(f"{4 if motor_counts else 3}. Voltage after each step (squares are 0 right after a spike resets)",
                   loc="left", fontsize=11, color=INK)
    axes = [ax_r, ax_d, ax_m, ax_v] if motor_counts else [ax_r, ax_d, ax_v]
    bar = fig.colorbar(image, ax=axes, location="bottom", shrink=0.45,
                       pad=0.07, aspect=40)
    bar.set_ticks([-VOLTAGE_LIMIT, -128, 0, 128, 256])
    bar.set_ticklabels([f"≤ −{VOLTAGE_LIMIT}  held down", "−128", "0", "128", "256 threshold"])
    bar.ax.tick_params(labelsize=8.5, colors=MUTED, labelcolor=INK_2)
    bar.outline.set_visible(False)

    if save_as:
        fig.savefig(save_as, dpi=150, facecolor=SURFACE, bbox_inches="tight")
    return fig
