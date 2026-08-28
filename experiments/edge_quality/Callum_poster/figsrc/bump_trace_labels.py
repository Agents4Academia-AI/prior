#!/usr/bin/env python3
"""Enlarge the paper labels on the two trace figures, in the SVG itself.

`trace.py --font-scale` scales *everything* together, which makes the figure
taller because the ring radii are driven by node counts and the whole thing
grows. What we actually want is only the three classes of paper label bigger,
with the geometry left exactly where it is. That is a post-process, so it lives
here rather than in `trace.py`.

The three classes, identified by their font-size in the generated file:

    26.4 px   outer ring, "listed only"      the faint ones, worst offenders
    32.8 px   middle ring, "read"
    39.2 px   inner ring, "focus"            bold

Everything else (title, question, call ribbon, keys, caption, step badges) is
left alone: those are already 13 pt or better on the sheet, and the ribbon in
particular has no spare width.

Multi-line labels are stacks of separate <text> elements at a fixed y step, so
each stack is re-spaced by the same factor about its own vertical centre.
Single-line labels get a small baseline nudge so they stay optically centred on
their node.

    python figsrc/bump_trace_labels.py                 # apply the defaults
    python figsrc/bump_trace_labels.py --outer 1.30    # push the faint ring more
    python figsrc/bump_trace_labels.py --revert        # back to the originals

Always re-reads from figsrc/_trace_orig/, so factors never compound.
"""
from __future__ import annotations

import argparse
import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from svgkit import flatten_group_transform  # noqa: E402

HERE = Path(__file__).resolve().parent
ORIG = HERE / "_trace_orig"
FIGS = HERE.parent / "figures"

TARGETS = {
    "p11_q01_trace_builds_on.svg": ORIG / "p11.svg",
    "p12_q03_trace_disagreement_nokey.svg": ORIG / "p12.svg",
}

CANVAS = 1900          # px, both files
PLACED_MM = 368        # one column of the two-column A0
PT = PLACED_MM / CANVAS * 2.8346

TEXT_RE = re.compile(
    r'<text x="(-?[\d.]+)" y="(-?[\d.]+)" font-size="([\d.]+)"'
    r' text-anchor="(\w+)"([^>]*)>(.*?)</text>')


def group_scale(svg: str) -> float:
    m = re.search(r"scale\((-?[\d.]+)\)", svg)
    return float(m.group(1)) if m else 1.0


def bump(src: Path, dst: Path, factors: dict[float, float]) -> dict[float, int]:
    svg = src.read_text(encoding="utf-8")
    items = [(m, float(m.group(1)), float(m.group(2)), float(m.group(3)),
              m.group(4)) for m in TEXT_RE.finditer(svg)]

    # Group consecutive elements that form one wrapped label: same x, same size,
    # same anchor, and a constant downward y step of less than 1.6x the size.
    blocks: list[list[int]] = []
    cur: list[int] = []
    for i, (_m, x, y, size, anc) in enumerate(items):
        if cur:
            _pm, px, py, psize, panc = items[cur[-1]]
            step = y - py
            same = (abs(x - px) < 0.6 and size == psize and anc == panc
                    and 0 < step < size * 1.6)
            if same and (len(cur) < 2 or abs(step - (py - items[cur[-2]][2])) < 0.6):
                cur.append(i)
                continue
            blocks.append(cur)
        cur = [i]
    if cur:
        blocks.append(cur)

    edits: dict[int, tuple[float, float]] = {}   # index -> (new size, new y)
    counts = {k: 0 for k in factors}
    for blk in blocks:
        size = items[blk[0]][3]
        k = factors.get(size)
        if not k:
            continue
        counts[size] += len(blk)
        ys = [items[i][2] for i in blk]
        new_size = round(size * k, 1)
        if len(blk) == 1:
            # keep the glyph optically centred on the node it labels
            edits[blk[0]] = (new_size, round(ys[0] + (new_size - size) * 0.34, 1))
        else:
            step = (ys[-1] - ys[0]) / (len(blk) - 1)
            centre = (ys[0] + ys[-1]) / 2
            new_step = step * k
            for j, i in enumerate(blk):
                y = centre + (j - (len(blk) - 1) / 2) * new_step
                edits[i] = (new_size, round(y, 1))

    out, at = [], 0
    for i, (m, x, y, size, anc) in enumerate(items):
        if i not in edits:
            continue
        new_size, new_y = edits[i]
        out.append(svg[at:m.start()])
        out.append(f'<text x="{x}" y="{new_y}" font-size="{new_size}"'
                   f' text-anchor="{anc}"{m.group(5)}>{m.group(6)}</text>')
        at = m.end()
    out.append(svg[at:])
    dst.write_text(flatten_group_transform("".join(out)), encoding="utf-8")
    return counts


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--outer", type=float, default=1.24, help="26.4 px, listed ring")
    ap.add_argument("--read", type=float, default=1.15, help="32.8 px, read ring")
    ap.add_argument("--focus", type=float, default=1.12, help="39.2 px, focus")
    ap.add_argument("--revert", action="store_true")
    a = ap.parse_args()

    if a.revert:
        for name, src in TARGETS.items():
            shutil.copy(src, FIGS / name)
            print(f"  reverted {name}")
        return

    factors = {26.4: a.outer, 32.8: a.read, 39.2: a.focus}
    rings = {26.4: "outer, listed", 32.8: "middle, read", 39.2: "inner, focus"}
    for name, src in TARGETS.items():
        g = group_scale(src.read_text(encoding="utf-8"))
        counts = bump(src, FIGS / name, factors)
        print(f"  {name}   (group scale {g}, now baked in)")
        for size, k in factors.items():
            print(f"      {rings[size]:14s} {size*g*PT:5.1f} -> {size*k*g*PT:5.1f} pt "
                  f"on the sheet   {counts[size]:3d} lines")


if __name__ == "__main__":
    main()
