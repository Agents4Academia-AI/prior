#!/usr/bin/env python3
"""Replay a graph-arm answer's tool calls and draw what the agent explored.

ZERO COST. No model is called. The atlas is deterministic, so re-issuing the
logged tool arguments reproduces exactly what the agent was shown — this is a
replay, not a reconstruction, and that is what makes the figure evidence rather
than illustration.

WHAT THE PICTURE ENCODES
------------------------
The point of the figure is not "here is a subgraph". It is "here is how the
agent engaged with it", so engagement is the primary visual channel — the rings:

  focus  (inner, big, numbered)  the agent named this paper as an ARGUMENT to a
                                 call. It chose to go there. The number is the
                                 call it happened on.
  read   (middle)                the agent pulled this paper's EVIDENCE TEXT —
                                 an edge justification via `edge_reasons`, or
                                 citation-site prose via `citations_between`.
  listed (outer, small)          the paper merely appeared in a returned list.
                                 It was delivered, not read.

That split is not cosmetic: it is the same split the v3 tool surface was built
around (labels in `paper_neighbourhood`, justifications only on request in
`edge_reasons`), which is precisely why an honest exploration trace exists at
all. See PLAN.md 2a.

Edge colour is the poster relation palette (REL_COLOR below), a darker,
higher-contrast variant of the app's own. A gold halo marks papers that made it into
the final answer.

OUTPUTS (per question, into out/traces/)
  <qid>.svg    poster figure — white background, vector, drop straight into
               PowerPoint (Insert > Pictures; Office keeps SVG as vector shapes)
  <qid>.json   Prior GlobalGraph {nodes, edges} for the app's own viewer
               (frontend/src/components/ClaimGraph.tsx), with additive
               `trace_*` fields; contribution-level, as that type requires
  <qid>.md     the call-by-call narrative, for the supervisor conversation

USAGE
  python trace.py                        # every graph-arm answer
  python trace.py --questions q01,q03    # just these
  python trace.py --questions q01 --max-listed 10 --queries on
  python trace.py --questions q03 --drop "AI-Researcher,arxiv:2606"   # prune

SIZING FOR THE POSTER
Each figure is a landscape band (~1.2-1.4:1) meant to occupy about a quarter of
the height of an A0 sheet, with the call sequence and the two keys in a RIBBON
underneath. Height is what the type size competes with, so two things keep the
type large: the rings are squashed into ELLIPSES (`--aspect`), and ring radii are
driven by node counts and LABEL WIDTHS rather than by font size — so raising
`--font-scale` really does make the type bigger relative to the figure rather
than just scaling everything. At a quarter of A0 the defaults put body text near
11pt and paper titles near 15pt. `--layout side` moves the key into a right-hand
column, buying back ~25% of the height if you need type larger still.
The relation key always shows ALL FIVE relations, used or not, so two figures on
the same poster read with the same legend.

See visualisations_explained.md for how to read the output.

TUNING (the two poster figures are meant to be fiddled with)
  --max-listed N     cap the faint outer ring (ranked: answer-cited first, then
                     most-touched). Default 14; the ring is what hairballs.
  --queries on|off|auto   draw the search/topic queries as entry-point nodes.
                     auto = on when there are at most 3, OR when the agent never
                     committed to a paper (then the queries ARE the trace - c01).
                     A query the corpus refused is drawn red, "no match".
  --no-citations     drop the citation layer, leaving only typed semantic edges
  --drop "a,b"       remove nodes whose title or paper_id contains any of these
  --keep "a,b"       keep ONLY nodes matching these (plus focus nodes)
  --label-listed / --no-label-listed    force outer-ring labels on or off
  --width N          target width in px (default 1900)
  --layout below|side   below (default) = call sequence + keys in a ribbon
                     under the graph; side = right-hand column, ~25% shorter
  --spread F         multiply the ring radii (>1 = airier, 0.85 = tighter)
  --aspect F         squash the rings into ellipses (default 0.62). Height is
                     what the type size competes with, so a wide band prints
                     bigger text; 1.0 restores circular rings
  --font-scale F     everything textual, scaled together
  --font "..."       CSS font-family for every label (default Arial)
  --png [SCALE]      also write a PNG via headless Chrome/Edge, default 2x
  --no-title / --no-legend / --no-caption / --no-rings / --no-timeline / --no-md
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "graph_vs_web_ideation"))

from graph_tools import GraphAtlas, _pid, _tok            # noqa: E402

OUT = HERE / "out"
TRACES = OUT / "traces"

# The poster palette. This diverges from frontend/src/lib/colors.ts, which still
# carries the app's original pastels; the poster set is darker and higher
# contrast so the relations survive being printed at A0 and read from a metre
# away. `contrast` is unused by these figures and is left as the app has it.
REL_COLOR = {
    "builds_on": "#5b8fb0",
    "refines": "#ca6702",
    "contradicts": "#ae2012",
    "contrast": "#ffa94d",
    "supports": "#0a9396",
    "mentions": "#000000",
}
CITES = "mentions"                      # citation-layer edges are black

SYMMETRIC_NOTE = ("contradicts and supports are recorded symmetric — "
                  "no direction is claimed")


def relation_directedness(atlas: GraphAtlas) -> dict[str, bool]:
    """Which relations carry a direction? Taken from the canonical edges' own
    `direction` field, not asserted here: `supports` is `symmetric` on all 203
    edges and `contradicts` on all 27, while `builds_on` and `refines` carry
    a_to_b / b_to_a. Drawing an arrowhead on a symmetric relation would be
    claiming something the graph does not record.

    IMPORTANT, and counter-intuitive: `direction`'s a_to_b / b_to_a refers to the
    A/B roles the labeller saw, and those were NOT preserved in src/dst — checked
    against the citation layer, `src` is the citing (later) paper in 104 of 104
    directed edges that have a citation, whereas reading a_to_b as src->dst
    agrees only 39 of 104, i.e. a coin flip. **So the arrow follows src -> dst,
    and `direction` is only used to decide whether to draw one at all.** Do not
    'fix' this by orienting edges from `direction`.
    """
    seen: dict[str, set] = {}
    for e in atlas.edges:
        seen.setdefault(e["relation"], set()).add(e.get("direction"))
    out = {r: not (d <= {"symmetric", "none", None}) for r, d in seen.items()}
    out[CITES] = True                   # citing -> cited, by construction
    return out

INK = "#212529"
MID = "#495057"
FAINT = "#adb5bd"
PALE = "#dee2e6"
GOLD = "#f59f00"
# Arial throughout: the poster is set in it, and a figure in a different face
# reads as a pasted-in foreign object. Override with --font if that changes.
FONT = "Arial, Helvetica, sans-serif"

# Node geometry and label metrics live here because BOTH the layout and the
# renderer need them: a ring has to be far enough from the next one to clear the
# inner ring's labels, which the layout cannot know otherwise.
NODE_R = {"focus": 18.0, "read": 12.0, "listed": 7.0}
LAB_SIZE = {"focus": 24.5, "read": 20.5, "listed": 16.5}   # x --font-scale
LAB_WIDTH = {"focus": 21, "read": 21, "listed": 19}        # wrap, in characters

ENG = {"listed": 0, "read": 1, "focus": 2}
ENG_NAME = {2: "focus", 1: "read", 0: "listed"}


# ── replay ───────────────────────────────────────────────────────────────────
class Trace:
    def __init__(self, row: dict, atlas: GraphAtlas):
        self.row = row
        self.qid = row["question_id"]
        self.question = row["question"]
        self.family = row.get("family", "")
        self.atlas = atlas
        self.nodes: dict[str, dict] = {}
        self.edges: dict[tuple, dict] = {}
        self.queries: list[dict] = []
        self.steps: list[dict] = []
        self.directed = relation_directedness(atlas)

    # -- accumulation -------------------------------------------------------
    def node(self, pid: str, engagement: str, step: int, note: str = "") -> None:
        if not pid or pid not in self.atlas.papers:
            return
        p = self.atlas.papers[pid]
        n = self.nodes.setdefault(pid, {
            "paper_id": pid, "title": p.get("title") or pid, "year": p.get("year"),
            "engagement": "listed", "steps": [], "first_step": step,
            "in_answer": False, "notes": []})
        if ENG[engagement] > ENG[n["engagement"]]:
            n["engagement"] = engagement
            n["first_step"] = step          # the step it reached this level
        if step not in n["steps"]:
            n["steps"].append(step)
        if note and note not in n["notes"]:
            n["notes"].append(note)

    def edge(self, src: str, dst: str, relation: str, engagement: str, step: int,
             *, kind: str = "semantic", reason: str = "", src_cid: str = "",
             dst_cid: str = "", extra: dict | None = None) -> None:
        if src not in self.atlas.papers or dst not in self.atlas.papers or src == dst:
            return
        key = (src, dst, relation, kind)
        e = self.edges.setdefault(key, {
            "src": src, "dst": dst, "relation": relation, "kind": kind,
            "engagement": "listed", "reason": "", "steps": [],
            "src_cid": src_cid, "dst_cid": dst_cid, **(extra or {})})
        if ENG[engagement] > ENG[e["engagement"]]:
            e["engagement"] = engagement
            e["read_step"] = step       # NOT steps[0]: an edge is usually listed
                                        # before it is read, and the read is the story
        if reason and len(reason) > len(e["reason"]):
            e["reason"] = reason
        if src_cid:
            e["src_cid"] = src_cid
        if dst_cid:
            e["dst_cid"] = dst_cid
        if step not in e["steps"]:
            e["steps"].append(step)
        if extra:
            e.update({k: v for k, v in extra.items() if v})


def _cite_pid(line: str) -> str:
    """Last whitespace token of a `_fmt_cite` row is the paper_id."""
    return line.rsplit(" ", 1)[-1].strip()


def _rel_parts(line: str) -> tuple[str, str, str] | None:
    """`-> relation | Other Title | other::cid` -> (arrow, relation, other_cid)."""
    bits = [b.strip() for b in line.split(" | ")]
    if len(bits) < 3:
        return None
    head = bits[0].split(" ", 1)
    if len(head) != 2:
        return None
    return head[0], head[1], bits[-1]


def _find_cids(atlas: GraphAtlas, paper_id: str, other_cid: str,
               relation: str) -> tuple[str, str]:
    """Which contribution of `paper_id` carries this edge? The lean listing gives
    the neighbour's contribution but not ours, so look it up in the atlas."""
    mine = [c for c, v in atlas.contribs.items() if v["paper_id"] == paper_id]
    for cid in mine:
        for e in atlas.edges_by_contrib.get(cid, []):
            if e["relation"] != relation:
                continue
            if e["src"] == cid and e["dst"] == other_cid:
                return cid, other_cid
            if e["dst"] == cid and e["src"] == other_cid:
                return other_cid, cid
    return (mine[0] if mine else paper_id), other_cid


def replay(row: dict, atlas: GraphAtlas) -> Trace:
    """Re-issue the logged calls against the deterministic atlas."""
    T = Trace(row, atlas)

    for i, call in enumerate(row.get("tool_args") or [], 1):
        tool = call["tool"].split("__")[-1]
        args = call.get("args") or {}
        if tool == "submit_answer":
            continue
        rec = {"step": i, "tool": tool, "args": args, "surfaced": [], "note": ""}

        # ---- entry points -------------------------------------------------
        if tool == "find_paper":
            hits = atlas.find_paper(args.get("query", ""), k=args.get("k", 5))
            for h in hits:
                T.node(h["paper_id"], "listed", i, "surfaced by name lookup")
                rec["surfaced"].append(h["paper_id"])
            if not hits:
                # c01 lives here: the tool refuses below its coverage threshold
                # rather than returning the nearest thing in a 152-paper corpus.
                rec["note"] = "NO MATCH — below the coverage threshold (refused)"
            T.queries.append({"step": i, "kind": "find_paper",
                              "text": args.get("query", ""),
                              "hits": list(rec["surfaced"])})

        elif tool == "search_contributions":
            hits = atlas.search_contributions(args.get("query", ""), k=args.get("k", 8))
            for h in hits:
                T.node(h["paper_id"], "listed", i, "surfaced by keyword search")
                rec["surfaced"].append(h["paper_id"])
            T.queries.append({"step": i, "kind": "search",
                              "text": args.get("query", ""),
                              "hits": list(rec["surfaced"])})

        elif tool == "topic_structure":
            res = atlas.topic_structure(args.get("query", ""), k=args.get("k", 5))
            for h in res["hits"]:
                hp = _pid(h["contribution_id"])
                T.node(hp, "listed", i, "topic-search hit")
                rec["surfaced"].append(hp)
                for line in h["relations"]:
                    parts = _rel_parts(line)
                    if not parts:
                        continue
                    arrow, rel, ocid = parts
                    op = _pid(ocid)
                    T.node(op, "listed", i, "seen as a typed neighbour")
                    a, b = (hp, op) if arrow == "->" else (op, hp)
                    sc, dc = _find_cids(atlas, hp, ocid, rel)
                    T.edge(a, b, rel, "listed", i, src_cid=sc, dst_cid=dc)
            T.queries.append({"step": i, "kind": "topic_structure",
                              "text": args.get("query", ""),
                              "hits": list(rec["surfaced"])})

        # ---- the agent chooses a paper -------------------------------------
        elif tool == "paper_neighbourhood":
            pid = args.get("paper_id", "")
            filt = " ".join(f"{k}={args[k]}" for k in ("relation", "intent") if args.get(k))
            T.node(pid, "focus", i, f"neighbourhood{' ' + filt if filt else ''}")
            res = atlas.paper_neighbourhood(pid, max_items=args.get("max_items", 40),
                                            relation=args.get("relation"),
                                            intent=args.get("intent"))
            if not res:
                rec["note"] = "unknown paper_id"
            else:
                for line in res["typed_relations"]:
                    parts = _rel_parts(line)
                    if not parts:
                        continue
                    arrow, rel, ocid = parts
                    op = _pid(ocid)
                    T.node(op, "listed", i, "typed neighbour (label only)")
                    a, b = (pid, op) if arrow == "->" else (op, pid)
                    sc, dc = _find_cids(atlas, pid, ocid, rel)
                    T.edge(a, b, rel, "listed", i, src_cid=sc, dst_cid=dc)
                for line in res["cited_by"]:
                    op = _cite_pid(line)
                    T.node(op, "listed", i, "cites this paper")
                    T.edge(op, pid, CITES, "listed", i, kind="citation")
                for line in res["cites"]:
                    op = _cite_pid(line)
                    T.node(op, "listed", i, "cited by this paper")
                    T.edge(pid, op, CITES, "listed", i, kind="citation")
                rec["counts"] = res["counts"]
                rec["surfaced"] = [_cite_pid(x) for x in res["cited_by"] + res["cites"]]

        # ---- the agent reads the evidence ----------------------------------
        elif tool == "edge_reasons":
            pid = args.get("paper_id", "")
            T.node(pid, "focus", i, "pulled edge justifications")
            res = atlas.edge_reasons(pid, others=args.get("others"),
                                     relation=args.get("relation"),
                                     max_items=args.get("max_items", 6))
            if not res:
                rec["note"] = "unknown paper_id"
            else:
                for r in res["reasons"]:
                    op = r["other_paper_id"]
                    T.node(op, "read", i, "justification read in full")
                    a, b = ((pid, op) if r["this_paper_is"] == "src" else (op, pid))
                    sc, dc = _find_cids(atlas, pid, r["other_contribution_id"],
                                        r["relation"])
                    T.edge(a, b, r["relation"], "read", i, reason=r["reason"],
                           src_cid=sc, dst_cid=dc)
                    rec["surfaced"].append(op)
                if res["no_edge_to"]:
                    rec["note"] = ("asked about, no typed edge: "
                                   + ", ".join(res["no_edge_to"]))

        elif tool == "citations_between":
            a, b = args.get("paper_id_a", ""), args.get("paper_id_b", "")
            T.node(a, "focus", i, "citation detail requested")
            T.node(b, "read", i, "citation sites read in full")
            res = atlas.citations_between(a, b)
            if not res:
                rec["note"] = "no citation link between these two"
            else:
                intents = sorted({s.get("intent") for s in res["sites"] if s.get("intent")})
                T.edge(res["citing"], res["cited"], CITES, "read", i, kind="citation",
                       reason=" | ".join(str(s.get("justification") or "")
                                         for s in res["sites"])[:2000],
                       extra={"intents": intents, "n_sites": len(res["sites"])})
                rec["surfaced"] = [b]
                rec["note"] = f"{len(res['sites'])} site(s), intents={intents}"

        elif tool == "get_paper":
            pid = args.get("paper_id", "")
            T.node(pid, "focus", i, "abstract + contributions read")
        elif tool == "get_contribution":
            cid = args.get("contribution_id", "")
            T.node(_pid(cid), "focus", i, f"contribution {cid.split('::')[-1]} read")
        elif tool in ("get_edges", "get_neighbors"):
            cid = args.get("contribution_id", "")
            pid = _pid(cid)
            T.node(pid, "focus", i, "edges listed")
            for e in atlas.get_edges(cid):
                op = _pid(e["neighbor_id"])
                T.node(op, "listed", i, "typed neighbour (label only)")
                a, b = (pid, op) if e["this_is"] == "src" else (op, pid)
                T.edge(a, b, e["relation"], "listed", i,
                       src_cid=cid, dst_cid=e["neighbor_id"])
                rec["surfaced"].append(op)
        elif tool == "get_citations":
            pid = args.get("paper_id", "")
            T.node(pid, "focus", i, "citation list read")
            res = atlas.get_citations(pid) or {"cites": [], "cited_by": []}
            for r in res["cited_by"]:
                T.node(r["paper_id"], "listed", i, "cites this paper")
                T.edge(r["paper_id"], pid, CITES, "listed", i, kind="citation")
            for r in res["cites"]:
                T.node(r["paper_id"], "listed", i, "cited by this paper")
                T.edge(pid, r["paper_id"], CITES, "listed", i, kind="citation")
        elif tool == "overview":
            rec["note"] = "corpus-level overview"

        T.steps.append(rec)

    # which papers actually made it into the answer
    named = (row.get("answer") or {}).get("papers_named") or []
    by_norm = {" ".join(sorted(_tok(p.get("title") or ""))): pid
               for pid, p in atlas.papers.items()}
    for t in named:
        pid = by_norm.get(" ".join(sorted(_tok(t))))
        if pid and pid in T.nodes:
            T.nodes[pid]["in_answer"] = True
    T.named_titles = named
    return T


# ── pruning ──────────────────────────────────────────────────────────────────
def prune(T: Trace, *, max_listed: int, no_citations: bool,
          drop: list[str], keep: list[str]) -> None:
    if no_citations:
        for k in [k for k, e in T.edges.items() if e["kind"] == "citation"]:
            del T.edges[k]

    def matches(n: dict, pats: list[str]) -> bool:
        hay = (n["paper_id"] + " " + n["title"]).lower()
        return any(p.strip().lower() in hay for p in pats if p.strip())

    gone = set()
    for pid, n in T.nodes.items():
        if drop and matches(n, drop):
            gone.add(pid)
        if keep and n["engagement"] != "focus" and not matches(n, keep):
            gone.add(pid)

    # cap the outer ring: keep the ones that earned their place
    listed = [p for p, n in T.nodes.items()
              if n["engagement"] == "listed" and p not in gone]
    if max_listed is not None and len(listed) > max_listed:
        deg = {p: 0 for p in listed}
        for e in T.edges.values():
            for p in (e["src"], e["dst"]):
                if p in deg:
                    deg[p] += 2 if e["engagement"] != "listed" else 1
        listed.sort(key=lambda p: (not T.nodes[p]["in_answer"],
                                   -deg[p], -len(T.nodes[p]["steps"]),
                                   T.nodes[p]["first_step"]))
        gone |= set(listed[max_listed:])

    for p in gone:
        T.nodes.pop(p, None)
    for k in [k for k, e in T.edges.items()
              if e["src"] in gone or e["dst"] in gone]:
        del T.edges[k]
    for q in T.queries:
        q["hits"] = [h for h in q["hits"] if h in T.nodes]
    T.dropped = len(gone)


# ── layout ───────────────────────────────────────────────────────────────────
def label_metrics(T: Trace, fs: float) -> dict[str, dict[str, float]]:
    """Per tier: how far its widest label reaches sideways, and how tall a label
    block is. Both drive the layout — `reach` sets how far the NEXT ring out has
    to be, and `pitch` sets how big a ring must be to seat its own labels without
    them running into each other."""
    out = {k: {"reach": 0.0, "h": 0.0} for k in ENG}
    for n in T.nodes.values():
        e = n["engagement"]
        lines = wrap(short_title(n["title"]), LAB_WIDTH[e])[:3]
        w = max(len(l) for l in lines) * LAB_SIZE[e] * fs * 0.53 + NODE_R[e] + 16
        out[e]["reach"] = max(out[e]["reach"], w)
        out[e]["h"] = max(out[e]["h"], len(lines) * LAB_SIZE[e] * fs * 1.2 + 10)
    for e in out:
        # labels run sideways, so two neighbours on the flat top of the ellipse
        # need most of a label-width between them; on the steep sides it is the
        # block height that binds. Take whichever is larger.
        out[e]["pitch"] = max(out[e]["h"] * 1.05, out[e]["reach"] * 0.85)
    return out


def layout(T: Trace, *, spread: float = 1.0, aspect: float = 1.0,
           metrics: dict[str, dict[str, float]] | None = None
           ) -> dict[str, tuple[float, float]]:
    """Concentric rings by engagement, angles relaxed by a small force pass.

    Rings carry the meaning (how hard the agent engaged); the force pass only
    decides the ORDER around each ring, so connected papers end up near each
    other. Final positions are evenly spaced within a ring — a poster figure that
    is guaranteed not to overlap beats one that is 5% better packed.

    `aspect` < 1 squashes the whole thing vertically, turning the rings into
    concentric ELLIPSES. Nothing about the meaning changes — ring membership is
    still ring membership — but the figure becomes a landscape band, which is
    what a poster wants and what lets the type be set large: height is the axis
    the type size competes with, and labels stick out sideways anyway.
    """
    import numpy as np

    ids = sorted(T.nodes, key=lambda p: (-ENG[T.nodes[p]["engagement"]],
                                         T.nodes[p]["first_step"], p))
    if not ids:
        return {}
    idx = {p: i for i, p in enumerate(ids)}
    tier = np.array([2 - ENG[T.nodes[p]["engagement"]] for p in ids])
    n_t = [int((tier == t).sum()) for t in range(3)]

    def ring(count: int, floor: float, gap: float) -> float:
        return max(floor, count * gap / (2 * math.pi))

    # Ring floors collapse when the inner rings are empty — c01 never chose or
    # read a paper, and a huge blank bullseye in the middle of that figure reads
    # as a rendering bug rather than as the finding it is.
    # a lone focus node sits AT the origin and its label runs sideways, so the
    # first ring has to start beyond it
    f1 = (330 if n_t[0] == 1 else 250) if n_t[0] else 150
    f2 = 430 if (n_t[0] or n_t[1]) else 250
    r0 = 0.0 if n_t[0] <= 1 else ring(n_t[0], 130, 210)
    r1 = max(r0 + 210, ring(n_t[1], f1, 150)) if n_t[1] else r0
    r2 = max(r1 + 215, ring(n_t[2], f2, 118)) if n_t[2] else r1
    r0, r1, r2 = r0 * spread, r1 * spread, r2 * spread
    # A ring must clear the labels of the ring inside it. Titles are long and the
    # labels run sideways, so this, not the node count, is usually what sets the
    # spacing — without it an inner label lands on top of the next ring out.
    m = metrics or {}

    def reach_of(e: str) -> float:
        return (m.get(e) or {}).get("reach", 0.0)

    def seat(n: int, e: str) -> float:
        """Smallest semi-major axis whose ellipse perimeter seats n labels."""
        if n < 2:
            return 0.0
        k = 2 * math.pi * math.sqrt((1 + max(aspect, 1e-3) ** 2) / 2)
        return n * (m.get(e) or {}).get("pitch", 0.0) / k

    r0 = max(r0, seat(n_t[0], "focus"))
    r1 = max(r1, seat(n_t[1], "read"))
    r2 = max(r2, seat(n_t[2], "listed"))
    if n_t[0] and n_t[1]:
        r1 = max(r1, (0.0 if n_t[0] == 1 else r0) + reach_of("focus") + 60)
    if n_t[2]:
        if n_t[1]:
            r2 = max(r2, r1 + reach_of("read") + 55)
        elif n_t[0]:
            r2 = max(r2, r0 + reach_of("focus") + 55)
    R = np.array([r0, r1, r2])
    rad = R[tier]

    ang = np.zeros(len(ids))
    for t in range(3):
        w = np.where(tier == t)[0]
        for j, i in enumerate(w):
            ang[i] = 2 * math.pi * j / max(1, len(w))
    pos = np.stack([rad * np.cos(ang), rad * np.sin(ang)], axis=1)

    E = [(idx[e["src"]], idx[e["dst"]]) for e in T.edges.values()
         if e["src"] in idx and e["dst"] in idx]
    k = 160.0
    for it in range(320):
        d = pos[:, None, :] - pos[None, :, :]
        dist = np.sqrt((d ** 2).sum(-1)) + 1e-6
        rep = (d / dist[..., None]) * (k * k / dist)[..., None]
        np.fill_diagonal(dist, 1.0)
        disp = rep.sum(1)
        for a, b in E:
            v = pos[a] - pos[b]
            dd = math.hypot(*v) + 1e-6
            f = (v / dd) * (dd * dd / k) * 0.9
            disp[a] -= f
            disp[b] += f
        step = 30.0 * (1 - it / 320) + 2.0
        nrm = np.sqrt((disp ** 2).sum(-1))[:, None] + 1e-6
        pos = pos + disp / nrm * np.minimum(nrm, step)
        pos[rad == 0] = 0.0
        nz = rad > 0
        pn = np.sqrt((pos[nz] ** 2).sum(-1))[:, None] + 1e-6
        pos[nz] = pos[nz] / pn * rad[nz][:, None]

    def arc_params(n: int, a: float, b: float) -> list[float]:
        """n parameter angles equally spaced by ARC LENGTH round the ellipse.

        Equal ANGLE spacing bunches nodes vertically at the left and right ends
        of a squashed ellipse — which is exactly where the labels then collide.
        Equal arc length puts the spacing where the perimeter actually is."""
        ts = np.linspace(0, 2 * math.pi, 2001)
        d = np.hypot(np.diff(a * np.cos(ts)), np.diff(b * np.sin(ts)))
        cum = np.concatenate([[0.0], np.cumsum(d)])
        tgt = np.arange(n) / n * cum[-1]
        return list(np.interp(tgt, cum, ts) - math.pi / 2)

    out: dict[str, tuple[float, float]] = {}
    for t in range(3):
        w = list(np.where(tier == t)[0])
        if not w:
            continue
        if R[t] == 0:
            for i in w:
                out[ids[i]] = (0.0, 0.0)
            continue
        w.sort(key=lambda i: math.atan2(pos[i][1], pos[i][0]))
        # keep the force pass's ORDER; take the spacing from the ellipse
        for j, a in zip(w, arc_params(len(w), R[t], R[t] * max(aspect, 1e-3))):
            out[ids[j]] = (R[t] * math.cos(a), R[t] * math.sin(a))
    # only rings that actually hold something get a guide circle
    if aspect != 1.0:
        out = {k: (x, y * aspect) for k, (x, y) in out.items()}
    T.ring_r = tuple(r if n_t[t] else 0.0 for t, r in enumerate((r0, r1, r2)))
    T.ring_max = max(r0, r1, r2)
    T.aspect = aspect
    return out


# ── SVG ──────────────────────────────────────────────────────────────────────
def esc(s: str) -> str:
    return (str(s).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def short_title(t: str, limit: int = 52) -> str:
    """Titles in this corpus are 'Punchy Name: the long explanatory subtitle'."""
    t = re.sub(r"\s+", " ", t or "").strip()
    if len(t) <= limit:
        return t
    head = t.split(":")[0].strip()
    if 8 <= len(head) <= limit:
        return head
    return t[: limit - 1].rstrip() + "…"


def wrap(t: str, width: int) -> list[str]:
    words, lines, cur = t.split(), [], ""
    for w in words:
        if cur and len(cur) + 1 + len(w) > width:
            lines.append(cur)
            cur = w
        else:
            cur = f"{cur} {w}".strip()
    if cur:
        lines.append(cur)
    return lines


# friendly names for the timeline strip — the tool names are ours, the strip is
# for a reader who has never seen this tool surface
TOOL_NAME = {
    "find_paper": "look up by name", "search_contributions": "keyword search",
    "topic_structure": "topic map", "paper_neighbourhood": "neighbourhood",
    "edge_reasons": "read justifications", "citations_between": "citation detail",
    "get_paper": "paper record", "get_contribution": "contribution",
    "get_edges": "edges", "get_neighbors": "neighbours",
    "get_citations": "citations", "overview": "corpus overview",
}
CHOOSING = {"paper_neighbourhood", "edge_reasons", "citations_between",
            "get_paper", "get_contribution", "get_edges", "get_neighbors",
            "get_citations"}


def chip_label(s: dict, atlas: GraphAtlas) -> str:
    a = s["args"]
    name = TOOL_NAME.get(s["tool"], s["tool"])
    dead = " — no match" if str(s.get("note", "")).startswith("NO MATCH") else ""
    if a.get("query"):
        return f"{name} “{short_title(a['query'], 38)}”{dead}"
    pid = a.get("paper_id") or a.get("paper_id_a") or ""
    if not pid and a.get("contribution_id"):
        pid = _pid(a["contribution_id"])
    t = short_title((atlas.papers.get(pid) or {}).get("title", pid), 30) if pid else ""
    extra = ""
    if a.get("relation"):
        extra = f" · {a['relation']}"
    elif a.get("others"):
        extra = f" · {len(a['others'])} asked"
    elif a.get("paper_id_b"):
        extra = " → " + short_title(
            (atlas.papers.get(a['paper_id_b']) or {}).get("title", ""), 24)
    return f"{name}: {t}{extra}" if t else name


def plural(n: int, word: str) -> str:
    return f"{n} {word}" + ("" if n == 1 else "s")


ALL_RELS = ("contradicts", "refines", "builds_on", "supports", CITES)
REL_NAME = {"builds_on": "builds on", "refines": "refines",
            "contradicts": "contradicts", "supports": "supports",
            "contrast": "contrast", "mentions": "cites (citation layer)"}


def render_svg(T: Trace, pos: dict, opts) -> str:
    """One figure, sized for a poster.

    The key and the call sequence sit UNDER the graph by default, in columns —
    columns rather than a single stack because height is what the type size
    competes with. A figure printed at a quarter of an A0 sheet is ~297mm tall,
    and every pixel of key height is a pixel the graph and its labels do not get.
    `--layout side` puts them in a right-hand column instead, which is taller-type
    still if you need it.

    The relation key always lists ALL FIVE relations, whether or not this
    particular question used them, so two figures side by side on the poster read
    with the same legend.
    """
    fs = opts.font_scale
    font = getattr(opts, "font", None) or FONT
    side = getattr(opts, "layout", "below") == "side"
    W = opts.width
    S: list[str] = []
    A = S.append

    node_r = dict(NODE_R)
    lab_size = {k: v * fs for k, v in LAB_SIZE.items()}
    lab_width = dict(LAB_WIDTH)
    body = 18.5 * fs                      # key / call-sequence body text
    head = 15.0 * fs                      # the small-caps section headings
    pad = 22.0 * fs

    label_listed = opts.label_listed
    if label_listed is None:
        label_listed = sum(1 for n in T.nodes.values()
                           if n["engagement"] == "listed") <= 16

    n_focus = sum(1 for n in T.nodes.values() if n["engagement"] == "focus")
    show_q = (opts.queries == "on" or
              (opts.queries == "auto" and T.queries
               and (len(T.queries) <= 3 or n_focus == 0)))
    qpos: dict[int, tuple[float, float]] = {}
    qsize = 17.0 * fs

    def pill_text(q: dict) -> str:
        return short_title(q["text"], 34) + ("" if q["hits"] else " — no match")

    def pill_w(q: dict) -> float:
        return len(pill_text(q)) * qsize * 0.55 + 34

    if show_q and pos:
        nq = len(T.queries)
        reach = 0.0
        for _pid, (_x, _y) in pos.items():
            _n = T.nodes[_pid]
            _e = _n["engagement"]
            if _e != "listed" or label_listed:
                _ls = wrap(short_title(_n["title"]), lab_width[_e])[:3]
                _w = max(len(l) for l in _ls) * lab_size[_e] * 0.53 + node_r[_e] + 18
            else:
                _w = node_r[_e] + 4
            reach = max(reach, abs(_x) + _w)
        half = max(pill_w(q) for q in T.queries) / 2
        rq = max(getattr(T, "ring_max", 430) + (190 if nq <= 2 else 210),
                 reach + half + 34)
        want = []
        for j, q in enumerate(T.queries):
            pts = [pos[h] for h in q["hits"] if h in pos]
            ang = (math.atan2(sum(p[1] for p in pts) / len(pts),
                              sum(p[0] for p in pts) / len(pts)) if pts else
                   2 * math.pi * j / max(1, nq) - math.pi / 2)
            want.append((ang, q["step"]))
        want.sort()
        for j, (ang, step) in enumerate(want):
            if nq > 2:
                ang = 2 * math.pi * j / nq - math.pi / 2
            qpos[step] = (rq * math.cos(ang),
                          rq * math.sin(ang) * getattr(T, "aspect", 1.0))

    # ---- extents (tight: whitespace at the edge is wasted poster) -----------
    xs, ys = [0.0], [0.0]
    for pid, (x, y) in pos.items():
        n = T.nodes[pid]
        eng = n["engagement"]
        r = node_r[eng]
        if eng != "listed" or label_listed:
            lines = wrap(short_title(n["title"]), lab_width[eng])[:3]
            lw = max(len(l) for l in lines) * lab_size[eng] * 0.53 + r + 16
            lh = len(lines) * lab_size[eng] * 1.2 / 2 + 4
        else:
            lw, lh = r + 4, r + 4
        xs += [x - lw, x + lw]
        ys += [y - max(lh, r + 4), y + max(lh, r + 4)]
    for step, (x, y) in qpos.items():
        q = next(q for q in T.queries if q["step"] == step)
        w = pill_w(q)
        xs += [x - w / 2 - 6, x + w / 2 + 6]
        ys += [y - 24, y + 24]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    gw, gh = x1 - x0, y1 - y0

    # ---- title: the question, wrapped, never truncated ---------------------
    t_size, q_size = 34.0 * fs, 22.5 * fs
    q_lines: list[str] = []
    title_h = 0.0
    if not opts.no_title:
        q_lines = wrap(re.sub(r"\s+", " ", T.question).strip(),
                       max(40, int((W - 2 * pad) / (q_size * 0.5))))
        title_h = t_size * 1.15 + len(q_lines) * q_size * 1.28 + 18 * fs

    inner = W - 2 * pad
    col_w = (W * 0.30) if side else inner
    gap = 32 * fs if side else 0.0
    graph_w = inner - (col_w + gap if side else 0.0)
    scale = graph_w / gw
    graph_h = gh * scale

    # ---- key content, as data, so it can be measured before it is drawn -----
    steps = [] if opts.no_timeline else [
        (s["step"], chip_label(s, T.atlas), s["tool"] in CHOOSING)
        for s in T.steps]

    eng_rows = [("focus", "chose it — named as a call argument (n = step)"),
                ("read", "read its evidence — justification pulled"),
                ("listed", "listed only — delivered, not read"),
                ("gold", "named in the final answer")]
    if show_q:
        eng_rows += [("pill", "a search the agent typed (dotted lines → what "
                              "it found)"),
                     ("pilldead", "“no match” — nothing in the corpus fit it")]
    rel_rows = [("rel:" + r, REL_NAME[r] +
                 ("" if T.directed.get(r) else "  (symmetric)"))
                for r in ALL_RELS]
    rel_rows += [("note", SYMMETRIC_NOTE),
                 ("note", "solid = read · dashed = listed only")]

    ICON_W = {"focus": 34 * fs, "read": 34 * fs, "listed": 34 * fs,
              "gold": 34 * fs, "pill": 50 * fs, "pilldead": 50 * fs,
              "note": 0.0}
    for _r in ALL_RELS:
        ICON_W["rel:" + _r] = 54 * fs

    def wrapped(kind: str, txt: str, avail: float) -> list[str]:
        w = max(60.0, avail - ICON_W[kind])
        return wrap(txt, max(10, int(w / (body * 0.52))))[:3]

    def row_h(kind: str, txt: str, avail: float) -> float:
        n = len(wrapped(kind, txt, avail))
        base = body * (1.2 if kind == "note" else 1.7)
        return max(base, n * body * 1.2 + 7 * fs)

    def block_h(rows, avail: float, ncols: int) -> float:
        if not rows:
            return 0.0
        per = math.ceil(len(rows) / ncols)
        sub = avail / ncols
        return head + 15 * fs + max(
            sum(row_h(k, t, sub - 12 * fs) for k, t in rows[c * per:(c + 1) * per])
            for c in range(ncols))

    # ---- measure the key ---------------------------------------------------
    if side:
        key_h = 0.0
        if steps:
            key_h += head + 15 * fs
            for _n, txt, _c in steps:
                key_h += len(wrap(txt, max(12, int((col_w - 34 * fs) /
                                                   (body * 0.52))))) * body * 1.22 \
                    + 7 * fs
            key_h += 18 * fs
        if not opts.no_legend:
            key_h += block_h(eng_rows, col_w, 1) + 20 * fs
            key_h += block_h(rel_rows, col_w, 1)
        body_h = max(graph_h, key_h)
    else:
        tl_rows: list[list[tuple]] = []
        if steps:
            cur, curw = [], 0.0
            for num, txt, chose in steps:
                w = len(txt) * body * 0.52 + 40 * fs
                if cur and curw + w > inner:
                    tl_rows.append(cur)
                    cur, curw = [], 0.0
                cur.append((num, txt, chose, w))
                curw += w
            if cur:
                tl_rows.append(cur)
        tl_h = (head + 15 * fs + len(tl_rows) * body * 1.75 + 16 * fs) \
            if tl_rows else 0.0
        legend_h = 0.0
        if not opts.no_legend:
            legend_h = max(block_h(eng_rows, inner * 0.46, 1),
                           block_h(rel_rows, inner * 0.46, 1))
        key_h = tl_h + legend_h
        body_h = graph_h + key_h + 14 * fs

    cap_h = 0.0 if opts.no_caption else body * 2.0
    H = int(title_h + body_h + cap_h + 2 * pad)

    A(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
      f'viewBox="0 0 {W} {H}" font-family="{font}">')
    A(f'<rect x="0" y="0" width="{W}" height="{H}" fill="#ffffff"/>')

    used = sorted({e["relation"] for e in T.edges.values()} | set(ALL_RELS))
    A("<defs>")
    for rel in [r for r in used if T.directed.get(r)]:
        c = REL_COLOR.get(rel, MID)
        A(f'<marker id="a_{rel}" viewBox="0 0 10 10" refX="9.2" refY="5" '
          f'markerWidth="5.4" markerHeight="5.4" orient="auto-start-reverse">'
          f'<path d="M 0 0.6 L 10 5 L 0 9.4 z" fill="{c}"/></marker>')
        A(f'<marker id="af_{rel}" viewBox="0 0 10 10" refX="9.2" refY="5" '
          f'markerWidth="7.5" markerHeight="7.5" orient="auto-start-reverse">'
          f'<path d="M 0 0.6 L 10 5 L 0 9.4 z" fill="{c}" opacity="0.55"/>'
          f'</marker>')
    A("</defs>")

    # ---- title -------------------------------------------------------------
    yy = pad + t_size * 0.85
    if not opts.no_title:
        A(f'<text x="{pad:.0f}" y="{yy:.0f}" font-size="{t_size:.1f}" '
          f'font-weight="700" fill="{INK}">'
          f'{esc(opts.title or T.qid.upper() + " · " + T.family)}</text>')
        yy += q_size * 1.12
        for ln in q_lines:
            A(f'<text x="{pad:.0f}" y="{yy:.0f}" font-size="{q_size:.1f}" '
              f'fill="{MID}">{esc(ln)}</text>')
            yy += q_size * 1.28

    gx = pad - x0 * scale
    gy = pad + title_h - y0 * scale + (max(0.0, (body_h - graph_h) / 2) if side else 0.0)
    A(f'<g transform="translate({gx:.1f},{gy:.1f}) scale({scale:.4f})">')

    if not opts.no_rings:
        for r in getattr(T, "ring_r", ()):
            if r > 0:
                A(f'<ellipse cx="0" cy="0" rx="{r:.1f}" '
                  f'ry="{r * getattr(T, "aspect", 1.0):.1f}" fill="none" '
                  f'stroke="{PALE}" stroke-width="1.2" stroke-dasharray="2 8"/>')

    if show_q:
        for q in T.queries:
            if q["step"] not in qpos:
                continue
            qx, qy = qpos[q["step"]]
            for h in q["hits"]:
                if h in pos:
                    hx, hy = pos[h]
                    A(f'<line x1="{qx:.1f}" y1="{qy:.1f}" x2="{hx:.1f}" '
                      f'y2="{hy:.1f}" stroke="{PALE}" stroke-width="1.5" '
                      f'stroke-dasharray="3 6"/>')

    def edge_path(a, b, bow, r_a, r_b):
        """Bow away from the origin, and stop SHORT of both nodes — an arrowhead
        drawn at the node centre is hidden underneath the node."""
        (x1, y1), (x2, y2) = a, b
        mx, my = (x1 + x2) / 2, (y1 + y2) / 2
        L = math.hypot(x2 - x1, y2 - y1) or 1.0
        m = math.hypot(mx, my)
        if m > 0.15 * L:
            ux, uy = mx / m, my / m
        else:
            ux, uy = -(y2 - y1) / L, (x2 - x1) / L
        cx, cy = mx + ux * L * bow, my + uy * L * bow
        d1 = math.hypot(cx - x1, cy - y1) or 1.0
        d2 = math.hypot(x2 - cx, y2 - cy) or 1.0
        sx, sy = x1 + (cx - x1) / d1 * r_a, y1 + (cy - y1) / d1 * r_a
        ex, ey = x2 - (x2 - cx) / d2 * r_b, y2 - (y2 - cy) / d2 * r_b
        return f"M {sx:.1f} {sy:.1f} Q {cx:.1f} {cy:.1f} {ex:.1f} {ey:.1f}"

    for e in sorted(T.edges.values(), key=lambda e: ENG[e["engagement"]]):
        if e["src"] not in pos or e["dst"] not in pos:
            continue
        rel = e["relation"]
        c = REL_COLOR.get(rel, MID)
        read = e["engagement"] != "listed"
        dir_ = T.directed.get(rel, False)
        ra = node_r[T.nodes[e["src"]]["engagement"]] + (5 if read else 3)
        rb = node_r[T.nodes[e["dst"]]["engagement"]] + ((11 if read else 7)
                                                       if dir_ else (5 if read else 3))
        mark = f'marker-end="url(#{"a_" if read else "af_"}{rel})"' if dir_ else ""
        A(f'<path d="{edge_path(pos[e["src"]], pos[e["dst"]], 0.10 if read else 0.26, ra, rb)}" '
          f'fill="none" stroke="{c}" stroke-width="{4.2 if read else 1.6:.1f}" '
          f'opacity="{0.95 if read else 0.3:.2f}" '
          f'{"" if read else "stroke-dasharray=\'7 5\' "}{mark}/>')

    for pid, (x, y) in sorted(pos.items(),
                              key=lambda kv: ENG[T.nodes[kv[0]]["engagement"]]):
        n = T.nodes[pid]
        eng = n["engagement"]
        r = node_r[eng]
        if n["in_answer"]:
            A(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r + (4 if eng == "listed" else 6):.1f}" '
              f'fill="none" stroke="{GOLD}" '
              f'stroke-width="{2.4 if eng == "listed" else 3.4}"/>')
        if eng == "focus":
            A(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r:.1f}" fill="#ffffff" '
              f'stroke="{INK}" stroke-width="3.8"/>')
            A(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r - 8:.1f}" fill="{INK}"/>')
        elif eng == "read":
            A(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r:.1f}" fill="#ffffff" '
              f'stroke="{MID}" stroke-width="3"/>')
        else:
            A(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r:.1f}" fill="{FAINT}"/>')

        right = x >= 0
        if eng == "focus":
            bx = x + (r + 8) * (-1 if right else 1)
            A(f'<circle cx="{bx:.1f}" cy="{y - 18:.1f}" r="12.5" fill="{INK}"/>')
            A(f'<text x="{bx:.1f}" y="{y - 13:.1f}" font-size="16" '
              f'text-anchor="middle" fill="#ffffff" font-weight="700">'
              f'{n["first_step"]}</text>')

        if eng == "listed" and not label_listed:
            continue
        lines = wrap(short_title(n["title"]), lab_width[eng])[:3]
        size = lab_size[eng]
        tx = x + (r + 13) * (1 if right else -1)
        anchor = "start" if right else "end"
        ty = y - (len(lines) - 1) * size * 0.6 + size * 0.34
        col = INK if eng == "focus" else (MID if eng == "read" else "#7c848c")
        wt = "700" if eng == "focus" else "400"
        for j, ln in enumerate(lines):
            A(f'<text x="{tx:.1f}" y="{ty + j * size * 1.2:.1f}" '
              f'font-size="{size:.1f}" text-anchor="{anchor}" fill="{col}" '
              f'font-weight="{wt}">{esc(ln)}</text>')

    if show_q:
        for q in T.queries:
            if q["step"] not in qpos:
                continue
            x, y = qpos[q["step"]]
            dead = not q["hits"]
            txt = pill_text(q)
            w = pill_w(q)
            A(f'<rect x="{x - w / 2:.1f}" y="{y - qsize:.1f}" width="{w:.1f}" '
              f'height="{qsize * 2:.1f}" rx="{qsize:.1f}" '
              f'fill="{"#fff5f5" if dead else "#f1f3f5"}" '
              f'stroke="{REL_COLOR["contradicts"] if dead else "#ced4da"}" '
              f'stroke-width="1.6"{" stroke-dasharray=\'5 4\'" if dead else ""}/>')
            A(f'<text x="{x:.1f}" y="{y + qsize * 0.36:.1f}" '
              f'font-size="{qsize:.1f}" text-anchor="middle" '
              f'fill="{"#c92a2a" if dead else MID}">“{esc(txt)}”</text>')

    A("</g>")

    # ---- key drawing helpers ----------------------------------------------
    def draw_row(kind: str, txt: str, x: float, y: float, avail: float) -> float:
        cyy = y + body * 0.42
        if kind in ("focus", "read", "listed", "gold"):
            r = node_r.get(kind, 8.0) * 0.8
            cxx = x + 13 * fs
            if kind == "focus":
                A(f'<circle cx="{cxx:.1f}" cy="{cyy:.1f}" r="{r:.1f}" fill="#fff" '
                  f'stroke="{INK}" stroke-width="3.4"/>'
                  f'<circle cx="{cxx:.1f}" cy="{cyy:.1f}" r="{r - 6.5:.1f}" fill="{INK}"/>')
            elif kind == "read":
                A(f'<circle cx="{cxx:.1f}" cy="{cyy:.1f}" r="{r:.1f}" fill="#fff" '
                  f'stroke="{MID}" stroke-width="2.8"/>')
            elif kind == "listed":
                A(f'<circle cx="{cxx:.1f}" cy="{cyy:.1f}" r="{r:.1f}" fill="{FAINT}"/>')
            else:
                A(f'<circle cx="{cxx:.1f}" cy="{cyy:.1f}" r="{9.5 * fs:.1f}" '
                  f'fill="none" stroke="{GOLD}" stroke-width="3.4"/>')
        elif kind.startswith("pill"):
            dead = kind == "pilldead"
            pw, ph = 34 * fs, 17 * fs
            A(f'<rect x="{x:.1f}" y="{cyy - ph / 2:.1f}" width="{pw:.1f}" '
              f'height="{ph:.1f}" rx="{ph / 2:.1f}" '
              f'fill="{"#fff5f5" if dead else "#f1f3f5"}" '
              f'stroke="{REL_COLOR["contradicts"] if dead else "#ced4da"}" '
              f'stroke-width="1.7"{" stroke-dasharray=\'5 4\'" if dead else ""}/>')
        elif kind.startswith("rel:"):
            rel = kind[4:]
            A(f'<path d="M {x:.1f} {cyy:.1f} L {x + 34 * fs:.1f} {cyy:.1f}" '
              f'stroke="{REL_COLOR[rel]}" stroke-width="4.2" fill="none"'
              + (f' marker-end="url(#a_{rel})"' if T.directed.get(rel) else "")
              + '/>')
        size = body * (0.9 if kind == "note" else 1.0)
        col = FAINT if kind == "note" else MID
        for j, ln in enumerate(wrapped(kind, txt, avail)):
            A(f'<text x="{x + ICON_W[kind]:.1f}" '
              f'y="{y + body * (0.82 + j * 1.2):.1f}" font-size="{size:.1f}" '
              f'fill="{col}">{esc(ln)}</text>')
        return row_h(kind, txt, avail)

    def draw_block(label: str, rows, x: float, y: float, avail: float,
                   ncols: int) -> float:
        if not rows:
            return 0.0
        A(f'<text x="{x:.0f}" y="{y + head:.0f}" font-size="{head:.1f}" '
          f'font-weight="700" fill="{MID}" letter-spacing="0.8">{label}</text>')
        top = y + head + 15 * fs
        per = math.ceil(len(rows) / ncols)
        sub = avail / ncols
        tallest = 0.0
        for c in range(ncols):
            cy2 = top
            for k, t in rows[c * per:(c + 1) * per]:
                cy2 += draw_row(k, t, x + c * sub, cy2, sub - 12 * fs)
            tallest = max(tallest, cy2 - top)
        return head + 15 * fs + tallest

    # ---- key ---------------------------------------------------------------
    if side:
        cx0 = W - pad - col_w
        cy = pad + title_h + max(0.0, (body_h - key_h) / 2)
        if steps:
            A(f'<text x="{cx0:.0f}" y="{cy + head:.0f}" font-size="{head:.1f}" '
              f'font-weight="700" fill="{MID}" letter-spacing="0.8">'
              f'WHAT IT DID, IN ORDER</text>')
            cy += head + 15 * fs
            for num, txt, chose in steps:
                col = INK if chose else FAINT
                ls = wrap(txt, max(12, int((col_w - 34 * fs) / (body * 0.52))))
                A(f'<circle cx="{cx0 + 12 * fs:.1f}" cy="{cy + body * 0.42:.1f}" '
                  f'r="{12 * fs:.1f}" fill="{col}"/>')
                A(f'<text x="{cx0 + 12 * fs:.1f}" y="{cy + body * 0.84:.1f}" '
                  f'font-size="{body * 0.82:.1f}" text-anchor="middle" '
                  f'fill="#ffffff" font-weight="700">{num}</text>')
                for j, ln in enumerate(ls):
                    A(f'<text x="{cx0 + 30 * fs:.1f}" '
                      f'y="{cy + body * (0.88 + j * 1.22):.1f}" '
                      f'font-size="{body:.1f}" '
                      f'fill="{INK if chose else "#868e96"}">{esc(ln)}</text>')
                cy += len(ls) * body * 1.22 + 7 * fs
            cy += 18 * fs
        if not opts.no_legend:
            cy += draw_block("HOW THE AGENT ENGAGED", eng_rows, cx0, cy,
                             col_w, 1) + 20 * fs
            draw_block("RELATION", rel_rows, cx0, cy, col_w, 1)
    else:
        cy = pad + title_h + graph_h + 14 * fs
        if tl_rows:
            A(f'<text x="{pad:.0f}" y="{cy + head:.0f}" font-size="{head:.1f}" '
              f'font-weight="700" fill="{MID}" letter-spacing="0.8">'
              f'WHAT IT DID, IN ORDER</text>')
            cy += head + 15 * fs
            for rowc in tl_rows:
                cxx = pad
                for num, txt, chose, w in rowc:
                    col = INK if chose else FAINT
                    A(f'<circle cx="{cxx + 12 * fs:.1f}" cy="{cy + body * 0.42:.1f}" '
                      f'r="{12 * fs:.1f}" fill="{col}"/>')
                    A(f'<text x="{cxx + 12 * fs:.1f}" y="{cy + body * 0.84:.1f}" '
                      f'font-size="{body * 0.82:.1f}" text-anchor="middle" '
                      f'fill="#ffffff" font-weight="700">{num}</text>')
                    A(f'<text x="{cxx + 30 * fs:.1f}" y="{cy + body * 0.88:.1f}" '
                      f'font-size="{body:.1f}" '
                      f'fill="{INK if chose else "#868e96"}">{esc(txt)}</text>')
                    cxx += w
                cy += body * 1.75
            cy += 16 * fs
        if not opts.no_legend:
            draw_block("HOW THE AGENT ENGAGED", eng_rows, pad, cy,
                       inner * 0.46, 1)
            draw_block("RELATION", rel_rows, pad + inner * 0.54, cy,
                       inner * 0.46, 1)

    # ---- caption -----------------------------------------------------------
    if not opts.no_caption:
        nf = sum(1 for n in T.nodes.values() if n["engagement"] == "focus")
        nr = sum(1 for n in T.nodes.values() if n["engagement"] == "read")
        nl = sum(1 for n in T.nodes.values() if n["engagement"] == "listed")
        ne = sum(1 for e in T.edges.values() if e["kind"] == "semantic")
        cap = (f"{plural(len(T.steps), 'graph call')} · "
               f"{plural(nf, 'paper')} chosen · {nr} read in depth · "
               f"{nl} listed · {plural(ne, 'typed edge')} · "
               f"{plural(len(T.named_titles), 'paper')} in the answer")
        A(f'<text x="{pad:.0f}" y="{H - pad * 0.5:.0f}" font-size="{body * 0.92:.1f}" '
          f'fill="{FAINT}">{esc(cap)}</text>')

    A("</svg>")
    return "\n".join(S)


# ── Prior GlobalGraph export ─────────────────────────────────────────────────
def to_global_graph(T: Trace) -> dict:
    """frontend/src/lib/types.ts GlobalGraph. Nodes are CONTRIBUTIONS, as that
    type requires; citation-layer edges are attached to each paper's first
    contribution and marked `paper_level`, since the citation layer is
    paper-to-paper and has nowhere finer to attach."""
    at = T.atlas
    first_cid: dict[str, str] = {}
    for cid, c in at.contribs.items():
        first_cid.setdefault(c["paper_id"], cid)

    want: set[str] = set()
    for e in T.edges.values():
        if e["kind"] == "semantic":
            want |= {e.get("src_cid") or "", e.get("dst_cid") or ""}
    for pid, n in T.nodes.items():
        if n["engagement"] == "focus":
            want |= {c for c, v in at.contribs.items() if v["paper_id"] == pid}
        elif first_cid.get(pid):
            want.add(first_cid[pid])
    want = {c for c in want if c in at.contribs}

    nodes = []
    for cid in sorted(want):
        c = at.contribs[cid]
        pid = c["paper_id"]
        n = T.nodes.get(pid, {})
        p = at.papers.get(pid, {})
        nodes.append({
            "id": cid, "paper_id": pid,
            "label": (c.get("statement") or "")[:120],
            "problem": "", "method": c.get("kind") or "",
            "result": c.get("statement") or "",
            "paper": p.get("title") or pid, "year": p.get("year") or 0,
            # additive trace fields — ignored by the app, used by our own tooling
            "trace_engagement": n.get("engagement", "listed"),
            "trace_steps": n.get("steps", []),
            "trace_in_answer": bool(n.get("in_answer")),
        })

    edges = []
    for (src, dst, rel, kind), e in T.edges.items():
        if kind == "semantic":
            s, d = e.get("src_cid"), e.get("dst_cid")
        else:
            s, d = first_cid.get(src), first_cid.get(dst)
        if not s or not d or s not in at.contribs or d not in at.contribs:
            continue
        edges.append({
            "id": f"{s}|{rel}|{d}", "source": s, "target": d, "relation": rel,
            "provenance": "both" if kind == "citation" else "text",
            "confidence": 1.0 if e["engagement"] != "listed" else 0.5,
            "evidence": (e.get("reason") or "")[:1200],
            "trace_engagement": e["engagement"], "trace_steps": e["steps"],
            "trace_kind": kind,
            **({"paper_level": True} if kind == "citation" else {}),
        })

    return {"nodes": nodes, "edges": edges,
            "trace": {"question_id": T.qid, "question": T.question,
                      "family": T.family, "arm": "graph",
                      "n_calls": len(T.steps),
                      "steps": [{k: v for k, v in s.items() if k != "counts"}
                                for s in T.steps],
                      "papers_named": T.named_titles}}


# ── narrative ────────────────────────────────────────────────────────────────
def narrative(T: Trace) -> str:
    at = T.atlas
    L = [f"# {T.qid} — what the agent did on the graph", "",
         f"**Question.** {T.question}", "",
         f"*Family:* `{T.family}` · *graph calls:* {len(T.steps)} · "
         f"*papers named in the answer:* {len(T.named_titles)}", "",
         "Replayed from the logged tool arguments against the deterministic "
         "atlas — no model was called to produce this.", "", "## The calls", ""]
    for s in T.steps:
        a = ", ".join(f"{k}={json.dumps(v)[:90]}" for k, v in s["args"].items())
        L.append(f"**{s['step']}. `{s['tool']}`** — {a}")
        if s["tool"] in ("paper_neighbourhood", "edge_reasons", "get_paper",
                         "get_contribution", "citations_between"):
            pid = s["args"].get("paper_id") or s["args"].get("paper_id_a") or ""
            if not pid and s["args"].get("contribution_id"):
                pid = _pid(s["args"]["contribution_id"])
            t = (at.papers.get(pid) or {}).get("title")
            if t:
                L.append(f"    - on *{t}*")
        if s.get("counts"):
            c = s["counts"]
            L.append(f"    - shown: {c.get('n_typed_relations')} typed relations, "
                     f"{c.get('n_cited_by')} citing / {c.get('n_cites')} cited "
                     f"(relations: {c.get('relations')})")
        if s["surfaced"]:
            names = [short_title((at.papers.get(p) or {}).get("title", p), 46)
                     for p in dict.fromkeys(s["surfaced"])][:6]
            L.append(f"    - surfaced: {'; '.join(names)}"
                     + (f" … +{len(set(s['surfaced'])) - 6} more"
                        if len(set(s["surfaced"])) > 6 else ""))
        if s["note"]:
            L.append(f"    - **{s['note']}**")
        L.append("")

    read = [e for e in T.edges.values() if e["engagement"] != "listed" and e["reason"]]
    if read:
        L += ["## The evidence it actually read", "",
              "These are the edges whose justification prose was pulled — the "
              "distinction the v3 tool surface exists to make.", ""]
        for e in sorted(read, key=lambda e: e.get("read_step") or e["steps"][0]):
            st = (at.papers.get(e["src"]) or {}).get("title", e["src"])
            dt = (at.papers.get(e["dst"]) or {}).get("title", e["dst"])
            arrow = "-->" if T.directed.get(e["relation"]) else "--"
            L.append(f"- **{short_title(st, 44)}** --{e['relation']}{arrow} "
                     f"**{short_title(dt, 44)}**  "
                     f"*(read at step {e.get('read_step') or e['steps'][0]})*")
            L.append(f"  > {re.sub(chr(10), ' ', e['reason'])[:420]}…")
            L.append("")

    ans = T.row.get("answer") or {}
    L += ["## What came out", "",
          f"*Confidence:* `{ans.get('confidence')}` · "
          f"*papers named:* {len(T.named_titles)}", ""]
    for t in T.named_titles:
        L.append(f"- {t}")
    return "\n".join(L) + "\n"


def to_png(svgs: list[Path], scale: int) -> int:
    """Headless Chrome/Edge screenshot. Pure convenience: PowerPoint prefers the
    SVG (it stays vector and recolourable), but some tools will not take one."""
    import re as _re
    import shutil
    import subprocess
    cand = [shutil.which("chrome"), shutil.which("msedge"),
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            "/usr/bin/google-chrome", "/usr/bin/chromium"]
    exe = next((c for c in cand if c and Path(c).exists()), None)
    if not exe:
        return 0
    made = 0
    for svg in svgs:
        head = svg.read_text(encoding="utf-8")[:400]
        w = int(_re.search(r'width="(\d+)"', head).group(1))
        h = int(_re.search(r'height="(\d+)"', head).group(1))
        try:
            subprocess.run(
                [exe, "--headless", "--disable-gpu", "--hide-scrollbars",
                 f"--force-device-scale-factor={scale}",
                 "--default-background-color=FFFFFFFF",
                 f"--screenshot={svg.with_suffix('.png')}",
                 f"--window-size={w},{h}", svg.resolve().as_uri()],
                check=True, timeout=120,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            made += 1
        except Exception:
            pass
    return made


# ── main ─────────────────────────────────────────────────────────────────────
def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--file", default=str(OUT / "answers.jsonl"))
    ap.add_argument("--questions", help="comma-separated question_ids")
    ap.add_argument("--out", default=str(TRACES))
    ap.add_argument("--max-listed", type=int, default=14)
    ap.add_argument("--no-citations", action="store_true")
    ap.add_argument("--drop", default="", help="comma-separated title/id substrings")
    ap.add_argument("--keep", default="", help="comma-separated title/id substrings")
    ap.add_argument("--queries", choices=("auto", "on", "off"), default="auto")
    ap.add_argument("--label-listed", dest="label_listed", action="store_true",
                    default=None)
    ap.add_argument("--no-label-listed", dest="label_listed", action="store_false")
    ap.add_argument("--width", type=int, default=1900)
    ap.add_argument("--layout", choices=("below", "side"), default="below",
                    help="side (default) puts the key and the call sequence in a "
                         "right-hand column, giving a landscape band that keeps "
                         "the type large at a quarter of A0; below is the old "
                         "full-width strip")
    ap.add_argument("--font-scale", type=float, default=1.1,
                    help="scale every text size together (the graph geometry is "
                         "unchanged, so this really does make the type bigger "
                         "relative to the figure)")
    ap.add_argument("--font", default=FONT,
                    help="CSS font-family for every label (default Arial)")
    ap.add_argument("--aspect", type=float, default=0.62,
                    help="vertical squash of the graph: 1.0 = circular rings, "
                         "lower = a wider, shorter band (the type prints bigger)")
    ap.add_argument("--spread", type=float, default=0.92,
                    help="multiply all ring radii (>1 = airier)")
    ap.add_argument("--title", help="override the figure title")
    ap.add_argument("--no-title", action="store_true")
    ap.add_argument("--no-legend", action="store_true")
    ap.add_argument("--no-caption", action="store_true")
    ap.add_argument("--no-rings", action="store_true")
    ap.add_argument("--no-timeline", action="store_true",
                    help="drop the 'what it did, in order' strip")
    ap.add_argument("--no-md", action="store_true")
    ap.add_argument("--png", nargs="?", const=2, type=int, default=None,
                    metavar="SCALE",
                    help="also write a PNG at SCALE x (default 2) via headless "
                         "Chrome/Edge, if one is installed")
    args = ap.parse_args()

    path = Path(args.file)
    if not path.exists():
        raise SystemExit(f"no answers at {path} — run qa_gen.py first.")
    rows = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines()
            if l.strip()]
    graph = [r for r in rows if r.get("arm") == "graph"]
    if args.questions:
        keep = set(args.questions.split(","))
        graph = [r for r in graph if r["question_id"] in keep]
    if not graph:
        raise SystemExit("no graph-arm rows matched.")

    atlas = GraphAtlas()
    outdir = Path(args.out)
    outdir.mkdir(parents=True, exist_ok=True)
    drop = [d for d in args.drop.split(",") if d.strip()]
    keepp = [k for k in args.keep.split(",") if k.strip()]

    written: list[Path] = []
    for row in sorted(graph, key=lambda r: r["question_id"]):
        T = replay(row, atlas)
        prune(T, max_listed=args.max_listed, no_citations=args.no_citations,
              drop=drop, keep=keepp)
        pos = layout(T, spread=args.spread, aspect=args.aspect,
                     metrics=label_metrics(T, args.font_scale))

        svg = outdir / f"{T.qid}.svg"
        svg.write_text(render_svg(T, pos, args), encoding="utf-8")
        written.append(svg)
        (outdir / f"{T.qid}.json").write_text(
            json.dumps(to_global_graph(T), indent=1, ensure_ascii=False),
            encoding="utf-8")
        if not args.no_md:
            (outdir / f"{T.qid}.md").write_text(narrative(T), encoding="utf-8")

        nf = sum(1 for n in T.nodes.values() if n["engagement"] == "focus")
        nr = sum(1 for n in T.nodes.values() if n["engagement"] == "read")
        nl = sum(1 for n in T.nodes.values() if n["engagement"] == "listed")
        ne = sum(1 for e in T.edges.values() if e["kind"] == "semantic")
        nc = sum(1 for e in T.edges.values() if e["kind"] == "citation")
        print(f"{T.qid}: {len(T.steps):2} calls · focus {nf} read {nr} listed {nl}"
              f" (pruned {getattr(T, 'dropped', 0)}) · edges {ne} typed + {nc} citation"
              f" · answer names {len(T.named_titles)} "
              f"({sum(1 for n in T.nodes.values() if n['in_answer'])} on the figure)"
              f"  -> {svg.name}")

    if args.png:
        made = to_png(written, args.png)   # only this run's figures
        print(f"\n{made} PNG(s) at {args.png}x." if made
              else "\nno Chrome/Edge found - SVG only.")

    print(f"\nwritten to {outdir}")
    print("PowerPoint: Insert > Pictures > This Device, pick the .svg — Office "
          "keeps it as vector shapes, so it stays crisp and you can recolour it.")


if __name__ == "__main__":
    main()
