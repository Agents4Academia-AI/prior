#!/usr/bin/env python3
"""Generate the poster's figures as SVG + 2x PNG.

    python figsrc/make_figures.py            # all of them
    python figsrc/make_figures.py p6 p10     # just these

POSTER SCALE, not report scale. Every figure is drawn on a 1200 px canvas and is
meant to be placed at 368 mm wide (one column of a two-column A0). That makes the
conversion:

    pt on the sheet = px * (368 / 1200) * 2.8346 = px * 0.869

so body text at 26 px lands at 22.6 pt and a class name at 30 px lands at 26 pt.
Anything below 22 px is illegal here. That constraint is the point: it forces each
figure down to one idea and a handful of words.

Every number is copied from a report on this branch; the source is named in the
docstring of each figure. Zero cost, no model calls.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from svgkit import (ARM_GRAPH, ARM_NULL, ARM_WEB, BG, CC, DIM, FAINT, GOOD,  # noqa: E402
                    INK, PANEL, R_BUILDS, R_CONTRA, R_REFINES, R_SUPPORTS, RULE,
                    UE, WARN,
                    WHITE, Fig, to_png)

OUT = Path(__file__).resolve().parent.parent / "figures"
OUT.mkdir(exist_ok=True)

# ── the type scale, in canvas px (multiply by 0.869 for pt at 368 mm) ────────
HUGE = 112     # 97 pt   one headline number
BIG = 64       # 56 pt   secondary numbers
LEAD = 30      # 26 pt   bold lead-ins, class names
BODY = 26      # 23 pt   the smallest text allowed in a figure
KICK = 22      # 19 pt   all-caps panel labels only

W = 1200       # canvas width for every figure that sits in ONE column
WIDE = 2400    # ... and for the full-width strip, placed at 761 mm

# how wide each figure is placed on the sheet, in mm. Everything is one column
# unless it says otherwise, and that is what the mm heights are reported against.
PLACED: dict[str, int] = {"p0_pipeline_strip": 761}

FIGS: dict[str, tuple[str, callable]] = {}


def fig(slug: str):
    def deco(fn):
        FIGS[slug] = (fn.__doc__.strip().splitlines()[0], fn)
        return fn
    return deco


def cpl(avail_px: float, size: int = BODY) -> int:
    """Characters per line for Arial at `size`, inside `avail_px`."""
    return max(8, int(avail_px / (size * 0.53)))


# ─────────────────────────────────────────────────────────────────────────────
@fig("p0_pipeline_strip")
def p0():
    """p0_pipeline_strip - the whole project in one line, corpus to evaluation.

    FULL WIDTH. Drawn on a 2400 px canvas and placed at 761 mm, the content width
    of the sheet. One line per stage, so the boxes are set to the width of their
    own label rather than a fixed grid, and the type is the largest that still
    leaves room for the chevrons. Every stage is drawn the same: the strip
    orients the reader, it does not argue.
    """
    labels = ["152 papers", "Semantic graph", "Mine citations",
              "Classify citation intent", "Enrich graph", "Graph QA agent",
              "Evaluate answers"]
    n = len(labels)

    for size in range(34, 21, -1):          # largest type that still fits
        pad = round(size * 0.62)
        ws = [len(t) * size * 0.60 + 2 * pad for t in labels]
        gap = (WIDE - sum(ws)) / (n - 1)
        if gap >= 48:                       # 30 px chevron plus clearance
            break

    bh, by = round(size * 2.6), 12
    f = Fig(WIDE, bh + 2 * by)
    cy = by + bh / 2

    x = 0.0
    for i, (t, bw) in enumerate(zip(labels, ws)):
        f.rect(x, by, bw, bh, fill=PANEL, stroke=RULE, sw=2, rx=12)
        f.text(x + bw / 2, cy + size * 0.36, t, size=size, anchor="middle",
               weight="bold", fill=INK)
        if i < n - 1:                       # a solid chevron, not a line and a
            ax = x + bw + gap / 2           # marker: at this size the arrowhead
            f.path(f"M {ax - 15} {cy - 15} L {ax + 15} {cy} L {ax - 15} {cy + 15} z",
                   stroke=DIM, sw=1, fill=DIM)
        x += bw + gap
    return f


# ─────────────────────────────────────────────────────────────────────────────
@fig("p2_two_layers")
def p2():
    """p2_two_layers - the model asserts, a citation records.

    Source: out/graph_overlap.md header table; GRAPH_STATE_AND_NEXT_TASK.md 1-2.
    Arrowheads follow the same convention as the trace figures: they are drawn only
    on the relations the graph actually records a direction for. `supports` is
    symmetric on all 203 edges and `contradicts` on all 27; `builds_on` and
    `refines` carry a direction.
    """
    f = Fig(W, 494)
    f.marker_defs({"m_ue": UE, "m_cc": CC, "m_bg": BG,
                   "m_b": R_BUILDS, "m_r": R_REFINES})

    f.rect(0, 0, 578, 494, fill=PANEL, rx=14)
    f.rect(622, 0, 578, 494, fill=PANEL, rx=14)

    # ── left: the semantic layer ────────────────────────────────────────────
    f.kicker(36, 50, "the model asserts", size=KICK)
    pts = [(148, 148), (330, 120), (424, 236), (200, 282), (286, 196)]
    for a, b, col, mk in ((0, 4, R_SUPPORTS, None), (4, 1, R_BUILDS, "m_b"),
                          (4, 3, R_SUPPORTS, None), (1, 2, R_CONTRA, None),
                          (2, 4, R_BUILDS, "m_b")):
        x1, y1 = pts[a]
        x2, y2 = pts[b]
        if mk:  # stop short of the node so the arrowhead is not hidden by it
            dx, dy = x2 - x1, y2 - y1
            L = (dx * dx + dy * dy) ** 0.5
            x2, y2 = x2 - dx / L * 26, y2 - dy / L * 26
        f.line(x1, y1, x2, y2, stroke=col, sw=7, marker=mk)
    for x, y in pts:
        f.circle(x, y, 20, fill=WHITE, stroke=INK, sw=4)
        f.circle(x, y, 7, fill=INK)

    key = ((R_SUPPORTS, "supports 695", None), (R_BUILDS, "builds on 212", "m_b"),
           (R_CONTRA, "contradicts 73", None), (R_REFINES, "refines 9", "m_r"))
    for i, (col, lab, mk) in enumerate(key):
        kx = 36 + (i % 2) * 276
        ky = 344 + (i // 2) * 40
        f.line(kx, ky, kx + 58, ky, stroke=col, sw=7, marker=mk)
        f.text(kx + 74, ky + 9, lab, size=BODY, fill=INK)
    f.text(36, 442, "arrows only where a direction is recorded", size=KICK, fill=DIM)
    f.text(36, 478, "989 claim pairs, typed by a model.", size=BODY, fill=INK)

    # ── right: the citation layer ───────────────────────────────────────────
    # Labels sit clear of the lines, on the left, because converging arrows and
    # centred labels always end up crossing.
    f.kicker(658, 50, "a citation records", size=KICK)
    tgt = (1148, 236)
    for y, lab, col, mk in ((146, "uses_extends", UE, "m_ue"),
                            (236, "compares_contrasts", CC, "m_cc"),
                            (326, "background", BG, "m_bg")):
        f.text(658, y + 10, lab, size=BODY, fill=col, weight="bold")
        f.circle(962, y, 15, fill=INK)
        f.line(986, y, tgt[0] - 42, tgt[1], stroke=col, sw=6, marker=mk)
    f.rect(tgt[0] - 26, tgt[1] - 26, 52, 52, fill=INK, rx=8)
    f.text(658, 442, "every one carries a direction", size=KICK, fill=DIM)
    f.text(658, 478, "1,103 citing passages, labelled.", size=BODY, fill=INK)
    return f


# ─────────────────────────────────────────────────────────────────────────────
@fig("p3_taxonomy_comparison")
def p3():
    """p3_taxonomy_comparison - three classes, chosen by what the graph does next.

    Source: MILESTONE_2_QUICKSTART.md section 7 (taxonomy decision record).
    """
    f = Fig(W, 552)

    f.kicker(0, 32, "other schemes classify for their own purposes", size=KICK)
    for i, (name, cls) in enumerate((("ACL-ARC", "6 classes, built for linguistics"),
                                     ("SciCite", "3 classes, built for scale"),
                                     ("RefWarden", "asks whether a citation is warranted"))):
        y = 84 + i * 42
        f.text(0, y, name, size=BODY, weight="bold", fill=FAINT)
        f.text(230, y, cls, size=BODY, fill=FAINT)

    f.line(0, 226, W, 226, stroke=RULE, sw=2)
    f.text(0, 272, "Ours: a class earns its place only if the graph acts on it.",
           size=LEAD, weight="bold")

    cw = 376
    for i, (col, name, share, what) in enumerate((
            (BG, "background", "82%", "no relation implied"),
            (UE, "uses_extends", "7%", "evidence for builds_on, plus the arrow"),
            (CC, "compares_contrasts", "11%", "evidence for contradicts"))):
        x = 4 + i * (cw + 32)
        f.rect(x, 302, cw, 244, fill=WHITE, stroke=col, sw=5, rx=12)
        f.text(x + 26, 366, name, size=LEAD, weight="bold", fill=col)
        f.text(x + 26, 434, share, size=BIG, weight="bold", fill=INK)
        f.wrap(x + 26, 478, what, size=BODY, width=cpl(cw - 52), lh=1.3, fill=INK)
    return f


# ─────────────────────────────────────────────────────────────────────────────
@fig("p4_judge_pipeline")
def p4():
    """p4_judge_pipeline - SPARE. From LaTeX source to one labelled passage.

    Source: MILESTONE_2_QUICKSTART.md; REFERENCE_RESOLUTION.md.
    """
    f = Fig(W, 300)
    f.marker_defs({"m_ink": INK})
    steps = ["arXiv\nLaTeX", "resolve the\nreference", "cut the\npassage",
             "abstract +\npassage", "judge"]
    bw, gap = 196, 55
    for i, s in enumerate(steps):
        x = i * (bw + gap)
        last = i == len(steps) - 1
        f.rect(x, 50, bw, 150, fill="#eef7f7" if last else WHITE,
               stroke=UE if last else INK, sw=4, rx=12)
        lines = s.split("\n")
        for j, ln in enumerate(lines):
            f.text(x + bw / 2, 118 + j * 38 - 19 * (len(lines) - 1), ln,
                   size=BODY, weight="bold", anchor="middle")
        if not last:
            f.line(x + bw + 10, 125, x + bw + gap - 14, 125, stroke=INK, sw=4,
                   marker="m_ink")
    f.text(0, 262, "One verdict per citing passage, not per paper pair.",
           size=BODY, fill=INK)
    f.text(0, 294, "809 passages across 525 edges.", size=BODY, fill=DIM)
    return f


# ─────────────────────────────────────────────────────────────────────────────
@fig("p6_evaluation_panel")
def p6():
    """p6_evaluation_panel - the two blind checks, four numbers.

    Source: out/gold_eval.md, out/second_judge_intent.md.
    """
    f = Fig(W, 510)

    f.rect(0, 0, 578, 240, fill=PANEL, stroke=RULE, sw=2, rx=14)
    f.kicker(32, 46, "blind gold set", size=KICK)
    f.text(32, 158, "95.0%", size=HUGE, weight="bold", fill=UE)
    f.text(32, 200, "76 of 80 sites I labelled by hand", size=BODY, fill=INK)
    f.text(32, 230, "95% CI  87.8 to 98.0", size=BODY, fill=DIM)

    f.rect(622, 0, 578, 240, fill=PANEL, stroke=RULE, sw=2, rx=14)
    f.kicker(654, 46, "blind second judge", size=KICK)
    f.text(654, 158, "0.79", size=HUGE, weight="bold", fill=UE)
    f.text(654, 200, "Cohen's kappa against Opus 5", size=BODY, fill=INK)
    f.text(654, 230, "100 sites, clean-room rubric", size=BODY, fill=DIM)

    f.text(0, 316, "macro-F1", size=BODY, fill=DIM)
    f.text(0, 366, "0.892", size=BIG, weight="bold")
    f.text(360, 316, "F1 by class", size=BODY, fill=DIM)
    for i, (name, v, col) in enumerate((("background", 0.97, BG),
                                        ("uses_extends", 0.87, UE),
                                        ("compares_contrasts", 0.84, CC))):
        y = 340 + i * 58
        f.text(360, y + 27, name, size=BODY)
        f.rect(740, y, 320, 34, fill=WHITE, stroke=RULE, sw=2, rx=17)
        f.rect(740, y, 320 * v, 34, fill=col, rx=17)
        f.text(1196, y + 27, f"{v:.2f}", size=BODY, weight="bold", anchor="end")
    return f


# ─────────────────────────────────────────────────────────────────────────────
@fig("p7_citation_semantic_venn")
def p7():
    """p7_citation_semantic_venn - the two layers barely overlap.

    Source: out/graph_overlap.md section 1. Circle areas are proportional.
    """
    f = Fig(W, 470)

    cy, r1, r2, d = 250, 158, 142, 205
    c1 = 400
    c2 = c1 + d
    # SEM is the semantic layer's own identity colour, not a relation colour:
    # the poster palette puts `supports` on the same teal as `uses_extends`, so
    # borrowing R_SUPPORTS here would collapse both circles into one hue.
    SEM = "#7b5fd1"
    f.circle(c1, cy, r1, fill=SEM, op=0.32)
    f.circle(c2, cy, r2, fill=UE, op=0.32)
    f.circle(c1, cy, r1, fill=None, stroke=SEM, sw=4)
    f.circle(c2, cy, r2, fill=None, stroke=UE, sw=4)

    f.text(150, 66, "the model's graph", size=LEAD, weight="bold", fill=SEM,
           anchor="middle")
    f.text(890, 66, "the citation graph", size=LEAD, weight="bold", fill=UE,
           anchor="middle")

    f.text(c1 - 66, cy + 6, "535", size=BIG, weight="bold", anchor="middle")
    f.text(c1 - 66, cy + 46, "its own", size=BODY, anchor="middle", fill=DIM)
    f.text(c2 + 64, cy + 6, "406", size=BIG, weight="bold", anchor="middle")
    f.text(c2 + 64, cy + 46, "its own", size=BODY, anchor="middle", fill=DIM)
    mid = (c1 + r1 + c2 - r2) / 2
    f.text(mid, cy - 2, "118", size=46, weight="bold", anchor="middle", halo=WHITE)
    f.text(mid, cy + 38, "both", size=BODY, anchor="middle", fill=DIM, halo=WHITE)

    f.text(0, 452, "406 pairs the model never proposed. 118 where the two can be checked.",
           size=BODY, fill=INK)
    return f


# ─────────────────────────────────────────────────────────────────────────────
@fig("p8_intent_relation_crosstab")
def p8():
    """p8_intent_relation_crosstab - SPARE. What the model says about the shared pairs.

    Source: out/graph_overlap.md section 2, the intent x relation presence table.
    Presence-based: a shared pair counts toward every relation it carries, so the
    rows do not sum to the pair count. `refines` is left off the figure because
    the whole column is 2 / 1 / 0 and a fourth column would cost the type size.
    """
    f = Fig(W, 500)
    f.kicker(0, 32, "the 118 shared pairs: what the model called them", size=KICK)

    cols = [("supports", R_SUPPORTS), ("builds_on", R_BUILDS),
            ("contradicts", R_CONTRA)]
    rows = [("background", BG, [57, 23, 8]), ("uses_extends", UE, [10, 9, 0]),
            ("compares_contrasts", CC, [19, 10, 4])]
    gx, cw, rh, gy = 340, 284, 104, 72
    for j, (lab, col) in enumerate(cols):
        cx = gx + j * cw + cw / 2
        f.line(cx - 40, gy - 2, cx + 40, gy - 2, stroke=col, sw=8)
        f.text(cx, gy + 34, lab, size=BODY, anchor="middle", weight="bold")
    for i, (rlab, rcol, cells) in enumerate(rows):
        y = gy + 56 + i * rh
        f.text(gx - 28, y + rh / 2 + 10, rlab, size=BODY, anchor="end",
               weight="bold", fill=rcol)
        for j, n in enumerate(cells):
            x = gx + j * cw
            hot = (i == 2 and j == 2)
            f.rect(x + 6, y + 6, cw - 12, rh - 12, fill="#fdece4" if hot else PANEL,
                   stroke=CC if hot else RULE, sw=4 if hot else 2, rx=10)
            f.text(x + cw / 2, y + rh / 2 + 16, str(n), size=BIG, anchor="middle",
                   weight="bold", fill=INK if n else FAINT)
    f.text(0, 478, "Only 4 of the 26 contrast pairs get a contradicts from the model.",
           size=BODY, fill=CC, weight="bold")
    return f


# ─────────────────────────────────────────────────────────────────────────────
@fig("p9_qa_three_arms")
def p9():
    """p9_qa_three_arms - three arms, one question, a blind judge.

    Source: experiments/question_answering/PLAN.md sections 1 and 4.
    """
    f = Fig(W, 232)
    f.marker_defs({"m_ink": FAINT})

    f.text(0, 66, "8 questions", size=LEAD, weight="bold")
    f.text(0, 106, "6 structural,", size=BODY, fill=DIM)
    f.text(0, 140, "2 controls", size=BODY, fill=DIM)
    f.line(240, 96, 292, 96, stroke=FAINT, sw=4, marker="m_ink")

    arms = ((ARM_GRAPH, "GRAPH", "Prior atlas"),
            (ARM_WEB, "WEB", "web search"),
            (ARM_NULL, "NULL", "no tools"))
    bw = 186
    for i, (col, tag, name) in enumerate(arms):
        x = 316 + i * (bw + 16)
        f.rect(x, 22, bw, 148, fill=WHITE, stroke=col, sw=5, rx=12)
        f.text(x + bw / 2, 74, tag, size=LEAD, weight="bold", fill=col, anchor="middle")
        f.text(x + bw / 2, 128, name, size=BODY, anchor="middle", fill=INK)
    f.line(938, 96, 990, 96, stroke=FAINT, sw=4, marker="m_ink")

    f.text(1200, 66, "blind judge", size=LEAD, weight="bold", anchor="end")
    f.text(1200, 106, "sees all three,", size=BODY, fill=DIM, anchor="end")
    f.text(1200, 140, "3 runs each", size=BODY, fill=DIM, anchor="end")

    f.text(0, 218, "Same model, same question. Only the environment differs.",
           size=BODY, fill=INK)
    return f


# ─────────────────────────────────────────────────────────────────────────────
@fig("p10_qa_scoreboard")
def p10():
    """p10_qa_scoreboard - judge scores on the six structural questions.

    Source: experiments/question_answering/RESULTS.md scoreboard.
    """
    f = Fig(W, 566)
    data = {"graph": [8.6, 7.6, 8.3], "web": [7.9, 7.6, 8.1], "null": [6.1, 7.2, 5.6]}
    axes = ["groundedness", "correctness", "usefulness"]

    base, tall, left = 330, 244, 92
    for v in (2, 4, 6, 8, 10):
        y = base - v / 10 * tall
        f.line(left, y, W, y, stroke=RULE, sw=2, dash="4 9" if v < 10 else None)
        f.text(left - 18, y + 9, str(v), size=BODY, fill=FAINT, anchor="end")
    f.kicker(0, 34, "the six structural questions  ·  mean of 3 order-swapped judge runs", size=KICK)

    gw = (W - left) / 3
    for j, ax in enumerate(axes):
        gx = left + j * gw
        for k, (arm, col) in enumerate((("graph", ARM_GRAPH), ("web", ARM_WEB),
                                        ("null", ARM_NULL))):
            v = data[arm][j]
            bh = v / 10 * tall
            bx = gx + 46 + k * 80
            f.rect(bx, base - bh, 62, bh, fill=col, rx=5)
            f.text(bx + 31, base - bh - 14, f"{v:.1f}", size=BODY, anchor="middle",
                   weight="bold", fill=col)
        f.text(gx + gw / 2, base + 46, ax, size=BODY, anchor="middle", weight="bold")
    f.line(left, base, W, base, stroke=INK, sw=3)

    for i, (arm, col) in enumerate((("GRAPH", ARM_GRAPH), ("WEB", ARM_WEB),
                                    ("NULL  closed book", ARM_NULL))):
        x = i * 300
        f.rect(x, 396, 34, 24, fill=col, rx=5)
        f.text(x + 48, 418, arm, size=BODY)

    f.line(0, 452, W, 452, stroke=RULE, sw=2)
    f.text(0, 508, "+2.5", size=BIG, weight="bold", fill=ARM_GRAPH)
    f.text(150, 498, "the atlas gains over the closed-book arm.", size=BODY)
    f.text(150, 532, "Web search gains +1.8.", size=BODY, fill=DIM)
    f.text(700, 508, "2 / 2", size=BIG, weight="bold", fill=ARM_WEB)
    f.text(852, 498, "controls lost to web,", size=BODY)
    f.text(852, 532, "as predicted.", size=BODY, fill=DIM)
    return f


# ─────────────────────────────────────────────────────────────────────────────
@fig("p13_qa_honesty")
def p13():
    """p13_qa_honesty - the three numbers the result rests on.

    Source: verify_named.py (0 of 57); JUDGING.md sections 6 and 8 (8 of 8
    unanimous over the three order-swapped runs); RESULTS.md efficiency table.
    """
    f = Fig(W, 344)
    rows = (("0 of 57", GOOD,
             "papers the atlas named that do not exist,",
             "resolved against the corpus, not by the judge"),
            ("8 of 8", ARM_GRAPH,
             "questions where all three order-swapped",
             "judge runs picked the same winner"),
            ("1.71x", WARN,
             "more text pulled in than web search.",
             "A prediction registered in advance, and it failed"))
    for i, (big, col, l1, l2) in enumerate(rows):
        y = i * 116
        f.rect(0, y, W, 104, fill=PANEL, stroke=RULE, sw=2, rx=12)
        f.text(28, y + 70, big, size=BIG, weight="bold", fill=col)
        f.text(310, y + 46, l1, size=BODY, fill=INK)
        f.text(310, y + 82, l2, size=BODY, fill=DIM)
    return f


# ─────────────────────────────────────────────────────────────────────────────
def main() -> None:
    want = [a for a in sys.argv[1:] if not a.startswith("-")]
    made: list[Path] = []
    for slug, (_desc, fn) in FIGS.items():
        if want and not any(w in slug for w in want):
            continue
        fg = fn()
        made.append(fg.save(OUT / f"{slug}.svg"))
        mm = PLACED.get(slug, 368)
        print(f"  {slug}.svg  {fg.w}x{fg.h}  ->  {mm * fg.h / fg.w:5.0f} mm tall "
              f"at {mm} mm wide")
    n = to_png(made, 2)
    print(f"\n{len(made)} SVG, {n} PNG at 2x -> {OUT}")


if __name__ == "__main__":
    main()
