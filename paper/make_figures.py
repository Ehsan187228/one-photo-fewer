#!/usr/bin/env python3
"""Rebuild the figures of "One Photo Fewer" from the supplement. Needs matplotlib.

    python3 make_figures.py
"""
import csv
import importlib.util
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap

ROOT = Path(__file__).resolve().parent
SUP = ROOT.parent / "supplement"
OUT = ROOT / "figures"
OUT.mkdir(exist_ok=True)

BLUE, ORANGE = "#2a78d6", "#eb6834"
NAVY = "#0d366b"
INK, SECONDARY, MUTED = "#0b0b0b", "#52514e", "#898781"
GRID, AXIS = "#e1e0d9", "#c3c2b7"
WASH = "#f1f5fb"

plt.rcParams.update({
    "font.family": ["Helvetica", "Arial", "DejaVu Sans"],
    "font.size": 8.5,
    "pdf.fonttype": 42,
    "axes.edgecolor": AXIS,
    "axes.linewidth": 0.7,
    "axes.labelcolor": SECONDARY,
    "axes.titlesize": 9,
    "axes.titleweight": "bold",
    "axes.titlecolor": INK,
    "axes.titlelocation": "left",
    "xtick.color": MUTED,
    "ytick.color": MUTED,
    "xtick.labelcolor": SECONDARY,
    "ytick.labelcolor": SECONDARY,
    "xtick.major.width": 0.6,
    "ytick.major.width": 0.6,
    "xtick.major.size": 2.5,
    "ytick.major.size": 2.5,
    "text.color": INK,
    "figure.dpi": 200,
})


def recess(ax, grid="y"):
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    if grid:
        ax.grid(axis=grid, color=GRID, linewidth=0.6)
        ax.set_axisbelow(True)


def save(fig, name):
    fig.savefig(OUT / (name + ".pdf"), bbox_inches="tight", pad_inches=0.03)
    fig.savefig(OUT / (name + ".png"), bbox_inches="tight", pad_inches=0.03, dpi=220)
    plt.close(fig)


def table(path):
    with open(path) as f:
        return list(csv.DictReader(f))


def fig_two_clocks():
    fig, axes = plt.subplots(2, 1, figsize=(6.5, 3.05), sharex=True, gridspec_kw={"hspace": 0.1})
    run1 = [(1.96, "web address\non screen", 1), (25.9, "future winners measured,\nthen passed over", -1),
            (50.8, "winning idea “refuted”\non a 3-second toy", 1), (87.47, "“the honest end state”", -1), (120.61, "budget stop,\nno record", 1)]
    run6 = [(0.75, "asks for\nthe page", 1), (12.41, "finds its\nown bug", -1), (18.75, "first\nrecord", 1), (27.9, "two more\nrecords", -1),
            (54.69, "arithmetic bug\nfound and fixed", 1), (77.6, "trap\nmeasured", -1), (120.32, "budget\nout", 1), (129.4, "verdict", -1)]
    for ax, title, events, end, color in ((axes[0], "Run 1, early Oris: no record", run1, 120.61, MUTED), (axes[1], "Run 6, later Oris: three records in 28 minutes", run6, 129.45, NAVY)):
        ax.set_ylim(-1.5, 1.5)
        ax.set_xlim(-1, 136)
        ax.axis("off")
        ax.plot([0, end], [0, 0], color=color, linewidth=2.2, solid_capstyle="round", zorder=2)
        for x, label, side in events:
            ax.plot([x, x], [0, 0.42 * side], color=MUTED, linewidth=0.6, zorder=1)
            ax.scatter([x], [0], s=17, color=color, edgecolors="#ffffff", linewidths=0.7, zorder=3)
            ha = "left" if x < 4 else "center"
            ax.text(x - (0.3 if ha == "left" else 0), 0.48 * side, label, ha=ha, va="bottom" if side > 0 else "top", fontsize=6.9, color=SECONDARY, linespacing=1.0)
        ax.text(-1, 1.48, title, fontsize=8.6, fontweight="bold", color=INK, va="top", ha="left")
    for x in range(0, 121, 20):
        axes[1].text(x, -1.42, str(x), ha="center", va="bottom", fontsize=7, color=MUTED)
    axes[1].text(136, -1.42, "minutes", ha="right", va="bottom", fontsize=7, color=MUTED)
    save(fig, "two_clocks")



def order_41():
    structure = json.loads((SUP / "data/structure.json").read_text())["41_9_3"]
    grid_a, grid_b = structure["A_grid_GF5"], structure["B_grid_GF4"]
    return grid_a, grid_b


def incidence(blocks, column_of):
    rows = {p: i for i, p in enumerate(column_of)}
    matrix = [[0] * len(blocks) for _ in column_of]
    for j, block in enumerate(blocks):
        for p in block:
            matrix[rows[p]][j] = 1
    return matrix


def split_41(blocks, spec):
    grid_a, grid_b = order_41()
    part_a, part_b = set(sum(grid_a, [])), set(sum(grid_b, []))
    lines_a, lines_b = spec.lines_ag25(grid_a), spec.lines_ag24(grid_b)
    core, rest = [], []
    for b in blocks:
        s = frozenset(b)
        if s & part_a in lines_a and s & part_b in lines_b:
            core.append(s)
        else:
            rest.append(s)
    key = lambda s: (lines_a.index(s & part_a), lines_b.index(s & part_b))
    core.sort(key=key)
    def side(s):
        na = len(s & part_a)
        line = s & part_a in lines_a
        return (0 if line else 1 if na >= 6 else 2, sorted(s))
    rest.sort(key=side)
    return core, rest


def load_module():
    spec = importlib.util.spec_from_file_location("check_structure", SUP / "check_structure.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def fig_inside_record():
    spec = load_module()
    grid_a, grid_b = order_41()
    columns = sum(grid_a, []) + sum(grid_b, [])
    seed = json.loads((SUP / "seeds/41_9_3.json").read_text())["blocks"]
    final = json.loads((SUP / "certificates/41_9_3.json").read_text())["blocks"]
    core_seed, rest_seed = split_41(seed, spec)
    core_final, rest_final = split_41(final, spec)
    assert core_seed == core_final and len(core_final) == 100

    def picture(ax, core, rest, title):
        ordered = core + rest
        matrix = incidence(ordered, columns)
        # 0 empty, 1 untouched skeleton, 2 the part that changes
        shown = [[(0 if not cell else 1 if j < len(core) else 2) for j, cell in enumerate(row)] for row in matrix]
        ax.imshow(shown, aspect="auto", interpolation="nearest", cmap=ListedColormap(["#ffffff", NAVY, ORANGE]), vmin=0, vmax=2)
        ax.set_xticks([])
        ax.set_yticks([])
        ax.axhline(24.5, color=AXIS, linewidth=0.6)
        for side in ax.spines.values():
            side.set_visible(False)
        ax.set_title(title, pad=4)
        ax.text(len(ordered) + 1.0, 12, "25 guests", fontsize=7, color=SECONDARY, va="center")
        ax.text(len(ordered) + 1.0, 33, "16 guests", fontsize=7, color=SECONDARY, va="center")

    fig, axes = plt.subplots(2, 1, figsize=(6.5, 3.35), gridspec_kw={"hspace": 0.28})
    picture(axes[0], core_seed, rest_seed, "The public album: 168 photos, the record to beat")
    picture(axes[1], core_final, rest_final, "The new album: 167 photos")
    axes[1].annotate("100 photos built from two grids. Identical in both albums.", xy=(50, 41.2), xytext=(50, 45.2), annotation_clip=False,
                     ha="center", va="top", fontsize=7.6, color=SECONDARY)
    axes[1].annotate("the rest, all rearranged but 9", xy=(133, 41.2), xytext=(133, 45.2), annotation_clip=False,
                     ha="center", va="top", fontsize=7.6, color=SECONDARY)
    save(fig, "inside_record")


def fig_one_seat_short():
    spec = load_module()
    found = spec.analyse_trap()
    labels, forms = found["labels"], found["forms"]
    hole = found["hole"]
    n = 15
    order_rows = sorted(range(n), key=lambda i: labels[i])
    order_cols = sorted(forms, key=lambda w: forms[w])
    fig, ax = plt.subplots(figsize=(2.35, 2.05))
    grid = []
    for i in order_rows:
        row = [1 if i in where else 0 for where in order_cols]
        row += [2 if i in {j for j, b in enumerate(found["blocks"]) if p in b} else 0 for p in hole]
        grid.append(row)
    ax.imshow(grid, aspect="equal", interpolation="nearest", cmap=ListedColormap(["#ffffff", NAVY, ORANGE]), vmin=0, vmax=2)
    ax.set_xticks([])
    ax.set_yticks([])
    for side in ax.spines.values():
        side.set_visible(False)
    for x in range(19):
        ax.axvline(x - 0.5, color=GRID, linewidth=0.35)
    for y in range(16):
        ax.axhline(y - 0.5, color=GRID, linewidth=0.35)
    ax.axvline(14.5, color=INK, linewidth=0.7)
    ax.text(7, -1.05, "15 sets of 3 guests", ha="center", fontsize=6.3, color=SECONDARY)
    ax.text(16, -1.05, "3 lone\nguests", ha="center", fontsize=6.3, color=SECONDARY, va="bottom", linespacing=1.0)
    ax.text(-1.0, 7, "15 photos", rotation=90, ha="center", va="center", fontsize=6.3, color=SECONDARY)
    save(fig, "one_seat_short")


def fig_traces():
    rows = table(SUP / "data/search_traces.csv")
    series = {}
    for r in rows:
        series.setdefault(r["series"], []).append(r)
    fig, (left, right) = plt.subplots(1, 2, figsize=(6.5, 2.45), gridspec_kw={"width_ratios": [1, 1.5], "wspace": 0.27})
    recess(left)
    frozen = [(float(r["seconds"]), int(r["accepted_moves"])) for r in series["C(66,20,3), before the fix"] if r["accepted_moves"]]
    for (x0, y0), (x1, y1) in zip(frozen, frozen[1:]):
        kept = x1 - x0 <= 20
        left.plot([x0, x1], [y0 / 1000, y1 / 1000], color=NAVY, linewidth=2 if kept else 1.1, linestyle="-" if kept else (0, (2, 2)), solid_capstyle="round")
    left.set_xlim(0, 240)
    left.set_ylim(0, 56)
    left.set_xticks([0, 60, 120, 180, 240])
    left.set_xlabel("Seconds into the search")
    left.set_title("The frozen counter", pad=5)
    left.set_ylabel("Moves accepted, thousands")
    left.text(236, 46.8, "stuck at 44,652", ha="right", fontsize=7.4, color=SECONDARY)
    recess(right)
    right.set_yscale("symlog", linthresh=1, linscale=0.55)
    styles = [("C(42,12,3), the regenerated record", NAVY, "42 guests, rerun: 57 s", "uncovered"),
              ("C(44,11,3), the record", BLUE, "44 guests: 16 s", "uncovered"),
              ("C(41,9,3), the record", ORANGE, "41 guests: 6 s", "uncovered")]
    for name, color, label, column in styles:
        data = [(float(r["seconds"]), int(r[column])) for r in series[name]]
        data = [d for d in data if d[0] <= 70]
        right.plot([d[0] for d in data], [d[1] for d in data], color=color, linewidth=1.6, marker="o" if column == "uncovered" else None, markersize=2.4,
                   solid_capstyle="round", solid_joinstyle="round", clip_on=False, zorder=3, label=label)
    right.text(6.2, 190, "146 missing, after starting from 7", fontsize=7.1, color=SECONDARY, va="center")
    right.legend(frameon=False, fontsize=7.1, loc="upper right", ncol=2, handlelength=1.4, borderaxespad=0.0, labelspacing=0.3, columnspacing=1.0)
    right.set_xlim(0, 70)
    right.set_ylim(0, 4200)
    right.set_yticks([0, 1, 10, 100])
    right.set_yticklabels(["0", "1", "10", "100"])
    right.minorticks_off()
    right.set_xlabel("Seconds into the search")
    right.set_title("Trios still missing", pad=5)
    save(fig, "traces")


if __name__ == "__main__":
    fig_two_clocks()
    fig_inside_record()
    fig_one_seat_short()
    fig_traces()
    print("figures written to", OUT)
