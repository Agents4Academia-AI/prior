#!/usr/bin/env python3
"""Generate a standalone, dependency-free D3 view of the contribution layer.

Reads data/atlas/contributions.json (+ paper metadata from atlas.json) and writes
data/atlas/view_global_d3.html with the data embedded inline (double-clickable,
like the original view_contributions.html).

The view is a two-layer radial graph (after Matt Might's "Illustrated Guide to a
PhD"): foundational work at the centre, each lineage step (refines/extends/
builds_on) pushes a ring outward, frontier at the rim. Papers are sandy boxes,
contributions aqua dots joined by faint stated_in edges; muted "teal-to-rust"
palette. Papers with no lineage are greyed ("known · not yet connected").

Two modes:
  * View — clean, read-only.
  * Edit — surfaces data-quality flags (duplicate papers, isolated papers) as
    badges + a review queue; Apply/Ignore each, see the graph update live, and
    export the decisions. Nothing mutates the source; resolutions are exportable.

Usage:  python3 scripts/gen_global_d3.py
"""
from __future__ import annotations

import ast
import json
import re
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "data" / "atlas" / "contributions.json"
ATLAS = ROOT / "data" / "atlas" / "atlas.json"
OUT = ROOT / "data" / "atlas" / "view_global_d3.html"


# ── paper metadata helpers ──────────────────────────────────────────────────
def _authors(p: dict) -> list[str]:
    a = p.get("authors") or []
    if isinstance(a, str):
        try:
            a = ast.literal_eval(a)
        except (ValueError, SyntaxError):
            a = [a] if a else []
    return [str(x) for x in a] if isinstance(a, list) else []


def cite_of(p: dict) -> str:
    year = str(p.get("year") or "").strip()
    authors = _authors(p)
    if not authors:
        base = (p.get("title") or p.get("id") or "paper")[:28]
        return f"{base} ({year})" if year else base
    last = authors[0].split()[-1] if authors[0].split() else authors[0]
    tail = " et al." if len(authors) > 1 else ""
    return f"{last}{tail} ({year})" if year else f"{last}{tail}"


def authors_str(p: dict) -> str:
    return ", ".join(_authors(p))


def _norm_title(t: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (t or "").lower()).strip()


def _cited(p: dict) -> int:
    try:
        return int(p.get("cited_by_count") or 0)
    except (TypeError, ValueError):
        return 0


# ── flag builder: detect data-quality issues, each with an applyable op ──────
def build_flags(contributions: list, edges: list, atlas: dict) -> list[dict]:
    cpaper = {c["id"]: c["paper_id"] for c in contributions}
    used = list(dict.fromkeys(c["paper_id"] for c in contributions))
    groups: dict[str, list] = defaultdict(list)
    for pid in used:
        groups[_norm_title((atlas.get(pid) or {}).get("title")) or pid].append(pid)

    flags: list[dict] = []

    # duplicate paper records (same title) → a full merge op.
    for pids in groups.values():
        if len(pids) < 2:
            continue
        canon = sorted(pids, key=lambda p: (-_cited(atlas.get(p) or {}), p))[0]
        members = [c["id"] for c in contributions if c["paper_id"] in pids]
        mset = set(members)
        parent = {m: m for m in members}

        def find(x):
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        # merge contributions joined by a cross-record 'supports' edge (restatements)
        for e in edges:
            s, d = e.get("src"), e.get("dst")
            if (e.get("relation") == "supports" and s in mset and d in mset
                    and cpaper[s] != cpaper[d]):
                ra, rb = find(s), find(d)
                if ra != rb:
                    parent[max(ra, rb)] = min(ra, rb)
        contrib_remap = {m: find(m) for m in members if find(m) != m}

        dois = "; ".join((atlas.get(p) or {}).get("doi") or "?" for p in pids)
        venues = {(("arXiv preprint" if "arxiv" in ((atlas.get(p) or {}).get("doi") or "").lower()
                    else ((atlas.get(p) or {}).get("venue") or "published")))
                  for p in pids}
        ver = f" Versions: {', '.join(sorted(venues))}." if len(venues) > 1 else ""
        flags.append({
            "id": "dup:" + canon, "type": "duplicate_paper", "severity": "high",
            "title": (atlas.get(canon) or {}).get("title"),
            "detail": f"{len(pids)} records share a title — likely one paper.{ver} DOIs: {dois}",
            "action": "Merge into one paper",
            "items": ["paper:" + p for p in pids],
            "op": {"kind": "merge", "canon": canon, "from": pids, "contrib_remap": contrib_remap},
        })

    # isolated papers (no cross-paper relations) → remove op (reviewer decides).
    touched = set()
    for e in edges:
        for x in (e.get("src"), e.get("dst")):
            if x in cpaper:
                touched.add(cpaper[x])
    for pid in used:
        if pid not in touched:
            flags.append({
                "id": "iso:" + pid, "type": "isolated_paper", "severity": "low",
                "title": (atlas.get(pid) or {}).get("title"),
                "detail": "No cross-paper relations — unconnected to the rest of the atlas.",
                "action": "Remove from atlas",
                "items": ["paper:" + pid],
                "op": {"kind": "remove", "paper": pid},
            })
    return flags


TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>Prior — contribution graph (D3)</title>
<script src="https://cdn.jsdelivr.net/npm/d3@7"></script>
<style>
  :root{
    /* muted "teal-to-rust" palette, matching view_contributions.html */
    --bg:#faf6ec; --bg-elev:#fbfcfd; --bg-elev-2:#f1ece0;
    --border:#e2e5ea; --border-soft:#eceff4;
    --text:#3b4252; --text-dim:#6b7686; --text-faint:#9aa0b0;
    --accent:#0a9396; --accent-soft:rgba(10,147,150,.12);
    --mono:ui-monospace,SFMono-Regular,"SF Mono",Menlo,Consolas,monospace;
    --sans:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
  }
  *{box-sizing:border-box}
  html,body{height:100%;margin:0}
  body{display:flex;background:var(--bg);color:var(--text);
       font-family:var(--sans);font-size:14px;line-height:1.45;-webkit-font-smoothing:antialiased}
  #canvas{position:relative;flex:1;min-width:0}
  svg{width:100%;height:100%;display:block;cursor:grab}
  svg:active{cursor:grabbing}

  .header{position:absolute;top:14px;left:14px;z-index:5;max-width:60%}
  .header h1{margin:0;font-size:15px;letter-spacing:.3px}
  .header .sub{margin-top:3px;font-size:12px;color:var(--text-dim)}
  .header .sub b{color:var(--text)}
  .controls{margin-top:9px;display:flex;gap:8px;align-items:center;flex-wrap:wrap}
  .controls label{display:inline-flex;align-items:center;gap:6px;font-size:12px;color:var(--text-dim);
                  background:var(--bg-elev);border:1px solid var(--border);border-radius:8px;padding:5px 10px;cursor:pointer}
  .controls input{accent-color:var(--accent)}
  .seg{display:inline-flex;border:1px solid var(--border);border-radius:8px;overflow:hidden}
  .seg button{background:var(--bg-elev);border:none;color:var(--text-dim);padding:6px 14px;font-size:12px;cursor:pointer}
  .seg button.on{background:var(--accent);color:#fff;font-weight:600}
  .issues{font-size:12px;color:#9c5a00;background:#fdf2dc;border:1px solid #f0d9b0;border-radius:8px;padding:4px 9px}

  .legend{position:absolute;bottom:14px;left:14px;z-index:5;background:var(--bg-elev);
          border:1px solid var(--border);border-radius:8px;padding:9px 11px;font-size:11px;max-width:240px}
  .legend .lg-title{color:var(--text-faint);text-transform:uppercase;letter-spacing:.5px;font-size:10px;margin:0 0 5px}
  .legend .lg-row + .lg-title{margin-top:9px}
  .lg-row{display:flex;align-items:center;gap:7px;margin-bottom:3px}
  .swatch{width:20px;height:0;border-top:3px solid;display:inline-block}
  .swatch.faint{border-top-width:1.5px;opacity:.7}
  .glyph{width:13px;height:13px;display:inline-block;border-radius:50%}
  .glyph.box{border-radius:3px;border:1.5px solid var(--text-dim);background:var(--bg-elev-2)}

  .zoom{position:absolute;top:14px;right:calc(360px + 14px);z-index:5;display:flex;flex-direction:column;gap:1px}
  .zoom button{width:30px;height:30px;background:var(--bg-elev);color:var(--text-dim);
               border:1px solid var(--border);font-size:16px;line-height:1;cursor:pointer}
  .zoom button:first-child{border-radius:8px 8px 0 0}
  .zoom button:last-child{border-radius:0 0 8px 8px;font-size:11px}
  .zoom button:hover{color:var(--text);background:var(--bg-elev-2)}

  #side{width:360px;flex:0 0 360px;background:var(--bg-elev);border-left:1px solid var(--border);
        overflow-y:auto;padding:18px}
  #side .empty{color:var(--text-faint);text-align:center;padding:36px 6px;font-size:13px}
  .field{margin-bottom:14px}
  .field .k{font-size:10.5px;text-transform:uppercase;letter-spacing:.6px;color:var(--text-faint);margin-bottom:3px}
  .field .v{font-size:13px}
  .pill{display:inline-block;padding:2px 8px;border-radius:4px;font-size:10px;font-weight:600;color:#fff}
  .quote{font-size:12.5px;color:var(--text-dim);border-left:2px solid var(--border);padding-left:9px;font-style:italic}
  .src{font-family:var(--mono);font-size:11px;color:var(--accent)}
  a.src{text-decoration:none}
  .neighbour{border:1px solid var(--border-soft);border-radius:6px;padding:8px 10px;margin-bottom:7px;background:var(--bg-elev-2)}
  .neighbour .nh{display:flex;align-items:center;gap:7px;flex-wrap:wrap;margin-bottom:4px}
  .neighbour .ev{font-size:11.5px;color:var(--text-dim)}
  .neighbour .nid{font-family:var(--mono);font-size:10.5px;color:var(--text-faint)}

  /* review queue (edit mode) */
  .qhead{font-size:12px;color:var(--text-dim);margin-bottom:11px}
  .flag{border:1px solid var(--border);border-left-width:3px;border-radius:7px;padding:9px 11px;margin-bottom:9px;
        background:var(--bg-elev);cursor:pointer}
  .flag.high{border-left-color:#ae2012} .flag.medium{border-left-color:#ca6702} .flag.low{border-left-color:#9aa0b0}
  .flag .ft{display:flex;justify-content:space-between;gap:8px;align-items:center;font-weight:600;font-size:12.5px}
  .flag .sev{font-size:9px;text-transform:uppercase;letter-spacing:.5px;padding:1px 6px;border-radius:4px;color:#fff}
  .flag.high .sev{background:#ae2012} .flag.medium .sev{background:#ca6702} .flag.low .sev{background:#9aa0b0}
  .flag .ttl{font-size:11.5px;color:var(--text);margin:5px 0 0}
  .flag .fd{font-size:11px;color:var(--text-dim);margin:4px 0 8px}
  .flag .acts{display:flex;gap:6px}
  .flag .acts button{font-size:11.5px;border-radius:6px;padding:4px 11px;border:1px solid var(--border);cursor:pointer}
  .flag .apply{background:var(--accent);color:#fff;border-color:var(--accent)}
  .flag .ignore{background:var(--bg-elev-2);color:var(--text)}
  .qdone{color:var(--accent);text-align:center;padding:26px 8px;font-size:14px}
  .expbtn{width:100%;margin-top:4px;padding:9px;border-radius:7px;border:1px solid var(--border);
          background:var(--bg-elev-2);color:var(--text);cursor:pointer;font-size:12px}

  text.nodelabel{font-family:var(--sans);font-size:10.5px;fill:var(--text);paint-order:stroke;
             stroke:var(--bg);stroke-width:3px;stroke-linejoin:round;pointer-events:none}
  .paper-box text{font-family:var(--sans);font-size:10.5px;font-weight:600;pointer-events:none;
                  dominant-baseline:middle;text-anchor:middle}
  .badge text{pointer-events:none}
</style>
</head>
<body>
  <div id="canvas">
    <div class="header">
      <h1>Prior — contribution graph</h1>
      <div class="sub" id="sub"></div>
      <div class="controls">
        <div class="seg"><button id="mView" class="on">View</button><button id="mEdit">Edit</button></div>
        <label><input type="checkbox" id="togglePapers" checked /> Paper layer</label>
        <span class="issues" id="issueCount" style="display:none"></span>
      </div>
    </div>
    <div class="zoom">
      <button id="zin" title="Zoom in">+</button>
      <button id="zout" title="Zoom out">&minus;</button>
      <button id="zfit" title="Fit">fit</button>
    </div>
    <div class="legend" id="legend"></div>
  </div>
  <div id="side"><div class="empty">Hover a node to focus its neighbours. Click for details — click empty space or press Esc to deselect.</div></div>

  <script id="graph-data" type="application/json">__DATA__</script>
  <script>
  const RAW = JSON.parse(document.getElementById("graph-data").textContent);
  // Working copy (Edit mode mutates this, never the embedded source).
  const DATA = {
    contributions: RAW.contributions.map((c) => ({ ...c })),
    edges: RAW.edges.map((e) => ({ ...e })),
    papers: RAW.papers || {},
    flags: (RAW.flags || []).map((f) => ({ ...f })),
  };
  const SIDE = document.getElementById("side");
  const EMPTY_HINT = "Hover a node to focus its neighbours. Click for details — click empty space or press Esc to deselect.";

  // relation styling (muted) ------------------------------------------------
  const relColor = {
    supports:"#0a9396", refines:"#ca6702", builds_on:"#287271", extends:"#ee9b00",
    contradicts:"#ae2012", contrast:"#bb6b00", mentions:"#9aa0b0",
  };
  const STATED = "#d8cdb5";
  const directed = new Set(["refines","builds_on","extends","contradicts","contrast"]);
  const relOf = (r) => (relColor[r] ? r : "mentions");
  const DOT = "#94d2bd", DOT_BORDER = "#c5cbd6";
  const PAPER_FILL = "#e9d8a6", PAPER_BORDER = "#c5b78f";
  const GREY_DOT = "#cdd2cc", GREY_DOT_BORDER = "#dcd9d0";
  const GREY_PAPER_FILL = "#edeae1", GREY_PAPER_BORDER = "#d3cdbf", GREY_TEXT = "#9aa0b0";

  const meta = DATA.papers;
  const citeOf = (pid) => (meta[pid] && meta[pid].cite) ||
    pid.replace(/^openalex:/, "").replace(/^arxiv:/, "arXiv ");

  // derived state (recomputed whenever the working data changes) -------------
  let papers, nContrib, rank, inLineage, maxRank, unsitList;
  const situated = (pid) => !!(inLineage && inLineage.has(pid));

  function recompute() {
    papers = Array.from(new Set(DATA.contributions.map((c) => c.paper_id)));
    nContrib = {};
    DATA.contributions.forEach((c) => (nContrib[c.paper_id] = (nContrib[c.paper_id] || 0) + 1));

    const LIN = new Set(["refines", "extends", "builds_on"]);
    const pidOf = (cid) => cid.split("::")[0];
    const cset = new Set(DATA.contributions.map((c) => c.id));
    const succ = new Map(papers.map((p) => [p, new Set()]));
    const indeg = new Map(papers.map((p) => [p, 0]));
    inLineage = new Set();
    DATA.edges.forEach((e) => {
      if (!LIN.has(e.relation) || !cset.has(e.src) || !cset.has(e.dst)) return;
      const a = pidOf(e.dst), b = pidOf(e.src);
      if (a === b || !succ.has(a) || !succ.has(b)) return;
      if (!succ.get(a).has(b)) { succ.get(a).add(b); indeg.set(b, indeg.get(b) + 1); }
      inLineage.add(a); inLineage.add(b);
    });
    rank = new Map(papers.map((p) => [p, 0]));
    const ind = new Map(indeg);
    const q = papers.filter((p) => ind.get(p) === 0);
    while (q.length) {
      const u = q.shift();
      succ.get(u).forEach((v) => {
        rank.set(v, Math.max(rank.get(v), rank.get(u) + 1));
        ind.set(v, ind.get(v) - 1);
        if (ind.get(v) === 0) q.push(v);
      });
    }
    maxRank = Math.max(0, ...papers.filter(situated).map((p) => rank.get(p)));
    unsitList = papers.filter((p) => !situated(p));
  }

  // svg scaffold (persists across rebuilds) ----------------------------------
  const canvas = document.getElementById("canvas");
  let W = canvas.clientWidth, H = canvas.clientHeight;
  const svg = d3.select("#canvas").append("svg").attr("viewBox", [0, 0, W, H]);
  const defs = svg.append("defs");
  Object.entries(relColor).forEach(([rel, c]) => {
    defs.append("marker").attr("id", "arrow-" + rel).attr("viewBox", "0 -5 10 10")
      .attr("refX", 18).attr("refY", 0).attr("markerWidth", 6).attr("markerHeight", 6).attr("orient", "auto")
      .append("path").attr("d", "M0,-4L9,0L0,4").attr("fill", c);
  });
  const root = svg.append("g");
  const zoom = d3.zoom().scaleExtent([0.2, 4]).on("zoom", (e) => root.attr("transform", e.transform));
  svg.call(zoom);
  svg.on("click", (e) => { if (!e.defaultPrevented) clearSelection(); });

  let mode = "view", showPapers = true, selectedId = null;
  let sim, sNode, cNode, cLabel, relLink, statedLink, badge, byId, adj, incident;

  function build() {
    root.selectAll("*").remove();
    badge = null;

    // radial geometry: ring per lineage rank, frontier at the rim
    const cx = W / 2, cy = H / 2;
    const maxROut = Math.min(W, H) / 2 - 64;
    const frontierRank = maxRank + (unsitList.length ? 1 : 0);
    const R0 = Math.max(72, maxROut * 0.2);
    const ringGap = (maxROut - R0) / Math.max(1, frontierRank);
    const radiusOfRank = (r) => R0 + r * ringGap;
    const radiusOf = (pid) => radiusOfRank(situated(pid) ? rank.get(pid) : frontierRank);
    const ringMembers = {};
    papers.forEach((p) => {
      const k = situated(p) ? rank.get(p) : frontierRank;
      (ringMembers[k] = ringMembers[k] || []).push(p);
    });
    const angle = new Map();
    Object.keys(ringMembers).forEach((k) => {
      const arr = ringMembers[k], off = Number(k) * 0.7;
      arr.forEach((p, i) => angle.set(p, off + (2 * Math.PI * i) / arr.length));
    });
    const targetOf = (pid) => {
      const r = radiusOf(pid), a = angle.get(pid) || 0;
      return { x: cx + r * Math.cos(a), y: cy + r * Math.sin(a), r };
    };
    drawRings(cx, cy, radiusOfRank, frontierRank, unsitList.length > 0);

    const cNodes = DATA.contributions.map((c) => ({
      id: c.id, type: "contribution", paper_id: c.paper_id,
      statement: c.statement, kind: c.kind, quote: c.quote,
    }));
    const pNodes = showPapers
      ? papers.map((pid) => ({ id: "paper:" + pid, type: "paper", paper_id: pid }))
      : [];
    const nodes = cNodes.concat(pNodes);
    byId = new Map(nodes.map((n) => [n.id, n]));
    nodes.forEach((n) => { const t = targetOf(n.paper_id); n.tx = t.x; n.ty = t.y; n._r = t.r; });

    const relLinks = DATA.edges
      .filter((e) => byId.has(e.src) && byId.has(e.dst))
      .map((e, i) => ({ id: "r" + i, kind: "relation", source: e.src, target: e.dst,
        relation: relOf(e.relation), rawRelation: e.relation, evidence: e.evidence, confidence: e.confidence }));
    const statedLinks = showPapers
      ? DATA.contributions.map((c, i) => ({ id: "s" + i, kind: "stated_in", source: c.id, target: "paper:" + c.paper_id }))
          .filter((l) => byId.has(l.target))
      : [];
    const links = relLinks.concat(statedLinks);

    adj = new Map(nodes.map((n) => [n.id, new Set([n.id])]));
    incident = new Map(nodes.map((n) => [n.id, new Set()]));
    links.forEach((l) => {
      adj.get(l.source).add(l.target); adj.get(l.target).add(l.source);
      incident.get(l.source).add(l.id); incident.get(l.target).add(l.id);
    });

    statedLink = root.append("g").attr("stroke", STATED).selectAll("line").data(statedLinks).join("line")
      .attr("stroke-width", 1).attr("stroke-opacity", 0.45);
    relLink = root.append("g").attr("fill", "none").selectAll("line").data(relLinks).join("line")
      .attr("stroke", (d) => relColor[d.relation])
      .attr("stroke-width", (d) => 1 + 2 * (d.confidence ?? 0.5))
      .attr("stroke-opacity", 0.6)
      .attr("marker-end", (d) => (directed.has(d.rawRelation) ? `url(#arrow-${d.relation})` : null));

    sNode = root.append("g").selectAll("g.paper-box").data(pNodes).join("g").attr("class", "paper-box")
      .style("cursor", "pointer")
      .call(d3.drag().on("start", dragStart).on("drag", dragged).on("end", dragEnd))
      .on("mouseover", (_, d) => focus(d.id))
      .on("mouseout", () => focus(selectedId))
      .on("click", (e, d) => { e.stopPropagation(); selectedId = d.id; focus(d.id); if (mode !== "edit") showPaperDetail(d.paper_id); });
    sNode.each(function (d) {
      const label = citeOf(d.paper_id);
      const w = Math.max(58, label.length * 6.2 + 16);
      const sit = situated(d.paper_id);
      const g = d3.select(this);
      g.append("rect").attr("x", -w / 2).attr("y", -11).attr("width", w).attr("height", 22)
        .attr("rx", 6).attr("fill", sit ? PAPER_FILL : GREY_PAPER_FILL)
        .attr("stroke", sit ? PAPER_BORDER : GREY_PAPER_BORDER).attr("stroke-width", 1.8)
        .attr("stroke-dasharray", sit ? null : "4 3");
      g.append("text").attr("y", 1).attr("fill", sit ? "#3b4252" : GREY_TEXT).text(label);
    });

    cNode = root.append("g").selectAll("circle").data(cNodes).join("circle")
      .attr("r", 7).attr("fill", (d) => (situated(d.paper_id) ? DOT : GREY_DOT))
      .attr("stroke", DOT_BORDER).attr("stroke-width", 1.5).style("cursor", "pointer")
      .call(d3.drag().on("start", dragStart).on("drag", dragged).on("end", dragEnd))
      .on("mouseover", (_, d) => focus(d.id))
      .on("mouseout", () => focus(selectedId))
      .on("click", (e, d) => { e.stopPropagation(); selectedId = d.id; focus(d.id); if (mode !== "edit") showDetail(d); });

    cLabel = root.append("g").selectAll("text").data(cNodes).join("text")
      .attr("class", "nodelabel").attr("dx", 10).attr("dy", 4).style("display", "none")
      .text((d) => truncate(d.statement, 46));

    sim = d3.forceSimulation(nodes)
      .force("link", d3.forceLink(links).id((d) => d.id)
        .distance((l) => (l.kind === "stated_in" ? 46 : 115))
        .strength((l) => (l.kind === "stated_in" ? 0.7 : 0.12)))
      .force("charge", d3.forceManyBody().strength((d) => (d.type === "paper" ? -240 : -85)))
      .force("radial", d3.forceRadial((d) => d._r, cx, cy).strength(0.88))
      .force("x", d3.forceX((d) => d.tx).strength(0.09))
      .force("y", d3.forceY((d) => d.ty).strength(0.09))
      .force("collide", d3.forceCollide((d) => (d.type === "paper" ? 28 : 13)))
      .stop();
    for (let i = 0; i < 420; i++) sim.tick();
    if (mode === "edit") drawBadges();
    ticked();
    sim.on("tick", ticked);

    markSelected();
    focus(selectedId);
    fit();
  }

  function drawBadges() {
    const flagged = new Set();
    DATA.flags.forEach((f) => (f.items || []).forEach((id) => flagged.add(id)));
    const data = Array.from(flagged).map((id) => byId.get(id)).filter(Boolean);
    badge = root.append("g").selectAll("g.badge").data(data).join("g").attr("class", "badge")
      .style("cursor", "pointer").on("click", (e, d) => { e.stopPropagation(); focus(d.id); });
    badge.append("circle").attr("cx", 11).attr("cy", -11).attr("r", 7)
      .attr("fill", "#d98324").attr("stroke", "#fff").attr("stroke-width", 1.5);
    badge.append("text").attr("x", 11).attr("y", -7.5).attr("text-anchor", "middle")
      .attr("font-size", 10).attr("font-weight", 700).attr("fill", "#fff").text("!");
  }

  function ticked() {
    statedLink.attr("x1", (d) => d.source.x).attr("y1", (d) => d.source.y)
              .attr("x2", (d) => d.target.x).attr("y2", (d) => d.target.y);
    relLink.attr("x1", (d) => d.source.x).attr("y1", (d) => d.source.y)
           .attr("x2", (d) => d.target.x).attr("y2", (d) => d.target.y);
    cNode.attr("cx", (d) => d.x).attr("cy", (d) => d.y);
    cLabel.attr("x", (d) => d.x).attr("y", (d) => d.y);
    sNode.attr("transform", (d) => `translate(${d.x},${d.y})`);
    if (badge) badge.attr("transform", (d) => `translate(${d.x},${d.y})`);
  }

  function focus(id) {
    if (!id) {
      cNode.attr("opacity", 1); sNode.attr("opacity", 1);
      relLink.attr("stroke-opacity", 0.6).attr("stroke-width", (d) => 1 + 2 * (d.confidence ?? 0.5));
      statedLink.attr("stroke-opacity", 0.45);
      cLabel.style("display", "none");
      return;
    }
    const near = adj.get(id) || new Set([id]);
    const inc = incident.get(id) || new Set();
    cNode.attr("opacity", (n) => (near.has(n.id) ? 1 : 0.1));
    sNode.attr("opacity", (n) => (near.has(n.id) ? 1 : 0.1));
    relLink.attr("stroke-opacity", (l) => (inc.has(l.id) ? 0.95 : 0.04))
           .attr("stroke-width", (l) => (inc.has(l.id) ? 2 + 2 * (l.confidence ?? 0.5) : 1));
    statedLink.attr("stroke-opacity", (l) => (inc.has(l.id) ? 0.8 : 0.03));
    cLabel.style("display", (n) => (near.has(n.id) ? null : "none"));
  }

  function markSelected() {
    cNode.attr("stroke", (d) => (d.id === selectedId ? "#3b4252" : (situated(d.paper_id) ? DOT_BORDER : GREY_DOT_BORDER)))
         .attr("stroke-width", (d) => (d.id === selectedId ? 2.5 : 1.5));
    sNode.select("rect").attr("stroke", (d) => (d.id === selectedId ? "#3b4252" : (situated(d.paper_id) ? PAPER_BORDER : GREY_PAPER_BORDER)))
         .attr("stroke-width", (d) => (d.id === selectedId ? 3 : 1.8));
  }

  function clearSelection() {
    selectedId = null;
    focus(null); markSelected();
    if (mode !== "edit") SIDE.innerHTML = `<div class="empty">${EMPTY_HINT}</div>`;
  }

  // side panel (view mode) ---------------------------------------------------
  function showDetail(d) {
    markSelected();
    const nbrs = DATA.edges.filter((e) => e.src === d.id || e.dst === d.id).map((e) => {
      const out = e.src === d.id;
      return { rel: e.relation, dir: out ? "→" : "←", other: out ? e.dst : e.src, evidence: e.evidence, confidence: e.confidence };
    });
    const nbrHtml = nbrs.length === 0
      ? '<div class="empty" style="padding:8px 0">No cross-paper relations.</div>'
      : nbrs.map((nb) => `
          <div class="neighbour">
            <div class="nh"><span class="pill" style="background:${relColor[relOf(nb.rel)]}">${nb.rel}</span>
              <span class="nid">conf ${(nb.confidence ?? 0).toFixed(2)}</span></div>
            <div class="nid">${nb.dir} ${esc(citeOf((byId.get(nb.other) || {}).paper_id || ""))}</div>
            ${nb.evidence ? `<div class="ev">${esc(nb.evidence)}</div>` : ""}
          </div>`).join("");
    SIDE.innerHTML = `
      <div class="field"><span class="pill" style="background:#94d2bd;color:#1f2933">${esc(d.kind || "contribution")}</span></div>
      <div class="field"><div class="k">Contribution</div><div class="v">${esc(d.statement)}</div></div>
      ${d.quote ? `<div class="field"><div class="k">Stated as</div><div class="v quote">${esc(d.quote)}</div></div>` : ""}
      <div class="field"><div class="k">Paper</div><div class="v src">${esc(citeOf(d.paper_id))}</div></div>
      <div class="field"><div class="k">Cross-paper relations (${nbrs.length})</div>${nbrHtml}</div>`;
  }

  function showPaperDetail(pid) {
    markSelected();
    const m = meta[pid] || {};
    SIDE.innerHTML = `
      <div class="field"><span class="pill" style="background:#e9d8a6;color:#3b4252">paper</span></div>
      <div class="field"><div class="k">Title</div><div class="v">${esc(m.title || citeOf(pid))}</div></div>
      <div class="field"><div class="k">Cite</div><div class="v src">${esc(m.cite || citeOf(pid))}</div></div>
      ${m.authors ? `<div class="field"><div class="k">Authors</div><div class="v">${esc(m.authors)}</div></div>` : ""}
      ${m.year ? `<div class="field"><div class="k">Year</div><div class="v">${esc(m.year)}</div></div>` : ""}
      <div class="field"><div class="k">Contributions in this atlas</div><div class="v">${nContrib[pid] || 0}</div></div>
      ${m.url ? `<div class="field"><a class="src" href="${m.url}" target="_blank">open source ↗</a></div>` : ""}`;
  }

  // ── Edit mode: review queue + apply/ignore ──────────────────────────────
  const decisions = { applied: [], ignored: [] };

  function renderQueue() {
    document.getElementById("issueCount").textContent = DATA.flags.length + " open";
    if (!DATA.flags.length) {
      SIDE.innerHTML = `<div class="qdone">✓ No open issues.</div>
        <button class="expbtn" onclick="review.export()">⬇ Export resolutions (${decisions.applied.length + decisions.ignored.length})</button>`;
      return;
    }
    const order = { high: 0, medium: 1, low: 2 };
    const fs = [...DATA.flags].sort((a, b) => order[a.severity] - order[b.severity]);
    SIDE.innerHTML = `<div class="qhead">${DATA.flags.length} issue(s) flagged for review. Apply a fix, or ignore. Nothing is saved until you export.</div>`
      + fs.map((f) => `
        <div class="flag ${f.severity}" onclick="review.focus('${f.id}')">
          <div class="ft"><span>${f.type.replace(/_/g, " ")}</span><span class="sev">${f.severity}</span></div>
          ${f.title ? `<div class="ttl"><b>${esc(f.title)}</b></div>` : ""}
          <div class="fd">${esc(f.detail)}</div>
          <div class="acts">
            <button class="apply" onclick="event.stopPropagation();review.apply('${f.id}')">${esc(f.action || "Apply")}</button>
            <button class="ignore" onclick="event.stopPropagation();review.ignore('${f.id}')">Ignore</button>
          </div>
        </div>`).join("")
      + `<button class="expbtn" onclick="review.export()">⬇ Export resolutions (${decisions.applied.length + decisions.ignored.length})</button>`;
  }

  function applyOp(op) {
    if (op.kind === "merge") {
      const from = new Set(op.from);
      DATA.contributions.forEach((c) => { if (from.has(c.paper_id)) c.paper_id = op.canon; });
      const cr = op.contrib_remap || {};
      const drop = new Set(Object.keys(cr));
      DATA.contributions = DATA.contributions.filter((c) => !drop.has(c.id));
      DATA.edges.forEach((e) => { if (cr[e.src]) e.src = cr[e.src]; if (cr[e.dst]) e.dst = cr[e.dst]; });
      const cp = {}; DATA.contributions.forEach((c) => (cp[c.id] = c.paper_id));
      const seen = new Set();
      DATA.edges = DATA.edges.filter((e) => {
        if (e.src === e.dst) return false;
        if (cp[e.src] && cp[e.src] === cp[e.dst]) return false;
        const k = e.src + "|" + e.dst + "|" + e.relation;
        if (seen.has(k)) return false; seen.add(k); return true;
      });
    } else if (op.kind === "remove") {
      const cs = new Set(DATA.contributions.filter((c) => c.paper_id === op.paper).map((c) => c.id));
      DATA.contributions = DATA.contributions.filter((c) => c.paper_id !== op.paper);
      DATA.edges = DATA.edges.filter((e) => !cs.has(e.src) && !cs.has(e.dst));
    }
  }

  const review = {
    apply(id) {
      const f = DATA.flags.find((x) => x.id === id);
      if (!f) return;
      applyOp(f.op);
      decisions.applied.push({ id: f.id, type: f.type, op: f.op });
      DATA.flags = DATA.flags.filter((x) => x.id !== id);
      selectedId = null;
      recompute(); build(); renderQueue();
    },
    ignore(id) {
      const f = DATA.flags.find((x) => x.id === id);
      if (!f) return;
      decisions.ignored.push({ id: f.id, type: f.type });
      DATA.flags = DATA.flags.filter((x) => x.id !== id);
      build(); renderQueue();
    },
    focus(id) {
      const f = DATA.flags.find((x) => x.id === id);
      if (!f || !f.items) return;
      const node = f.items.map((i) => byId.get(i)).find(Boolean);
      if (node) { selectedId = node.id; focus(node.id); markSelected(); }
    },
    export() {
      const blob = new Blob([JSON.stringify(decisions, null, 2)], { type: "application/json" });
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob); a.download = "review_resolutions.json"; a.click();
      URL.revokeObjectURL(a.href);
    },
  };
  window.review = review;

  function enterMode(m) {
    mode = m;
    document.getElementById("mView").classList.toggle("on", m === "view");
    document.getElementById("mEdit").classList.toggle("on", m === "edit");
    document.getElementById("issueCount").style.display = m === "edit" ? "inline-block" : "none";
    selectedId = null;
    if (m === "edit") {
      document.getElementById("togglePapers").checked = true; showPapers = true;
      renderQueue();
    } else {
      SIDE.innerHTML = `<div class="empty">${EMPTY_HINT}</div>`;
    }
    build();
  }

  // rings + chrome -----------------------------------------------------------
  function drawRings(cx, cy, radiusOfRank, frontierRank, outerUnsituated) {
    const g = root.append("g");
    for (let r = 0; r <= frontierRank; r++) {
      const outer = r === frontierRank;
      g.append("circle").attr("cx", cx).attr("cy", cy).attr("r", radiusOfRank(r)).attr("fill", "none")
        .attr("stroke", outer ? (outerUnsituated ? "#d7d3c8" : "#c9b89a") : "#e2e5ea")
        .attr("stroke-width", outer ? 1.4 : 1).attr("stroke-dasharray", outer ? "7 5" : "2 7");
    }
    g.append("text").attr("x", cx).attr("y", cy + 3).attr("text-anchor", "middle")
      .attr("fill", "#b9a98a").attr("font-size", 11).attr("font-style", "italic").text("foundational");
    g.append("text").attr("x", cx).attr("y", cy - radiusOfRank(frontierRank) - 10).attr("text-anchor", "middle")
      .attr("fill", outerUnsituated ? "#a7a395" : "#9aa0b0").attr("font-size", 11)
      .attr("font-style", outerUnsituated ? "italic" : "normal")
      .text(outerUnsituated ? "known · not yet connected" : "frontier of knowledge →");
  }

  function fit() {
    const ns = (cNode.data() || []).concat(sNode.data() || []);
    if (!ns.length) return;
    const xs = ns.map((n) => n.x), ys = ns.map((n) => n.y);
    const minX = Math.min(...xs), maxX = Math.max(...xs), minY = Math.min(...ys), maxY = Math.max(...ys);
    const gw = maxX - minX || 1, gh = maxY - minY || 1, pad = 80;
    const k = Math.min((W - pad * 2) / gw, (H - pad * 2) / gh, 2.2);
    svg.transition().duration(350).call(zoom.transform,
      d3.zoomIdentity.translate(W / 2 - k * (minX + gw / 2), H / 2 - k * (minY + gh / 2)).scale(k));
  }

  function dragStart(e, d) { if (!e.active) sim.alphaTarget(0.3).restart(); d.fx = d.x; d.fy = d.y; }
  function dragged(e, d) { d.fx = e.x; d.fy = e.y; }
  function dragEnd(e, d) { if (!e.active) sim.alphaTarget(0); d.fx = null; d.fy = null; }

  function truncate(s, n) { return s && s.length > n ? s.slice(0, n - 1) + "…" : (s || ""); }
  function esc(s) { return (s || "").toString().replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c])); }

  // controls -----------------------------------------------------------------
  document.getElementById("zin").onclick = () => svg.transition().call(zoom.scaleBy, 1.4);
  document.getElementById("zout").onclick = () => svg.transition().call(zoom.scaleBy, 1 / 1.4);
  document.getElementById("zfit").onclick = fit;
  document.getElementById("togglePapers").onchange = (e) => { showPapers = e.target.checked; build(); };
  document.getElementById("mView").onclick = () => enterMode("view");
  document.getElementById("mEdit").onclick = () => enterMode("edit");
  window.addEventListener("keydown", (e) => { if (e.key === "Escape") clearSelection(); });
  window.addEventListener("resize", () => {
    W = canvas.clientWidth; H = canvas.clientHeight;
    svg.attr("viewBox", [0, 0, W, H]);
    if (sim) sim.force("radial", d3.forceRadial((d) => d._r, W / 2, H / 2).strength(0.88)).alpha(0.2).restart();
  });

  // legend -------------------------------------------------------------------
  const relsPresent = Array.from(new Set(RAW.edges.map((e) => e.relation)));
  document.getElementById("legend").innerHTML =
    `<div class="lg-title">Nodes</div>` +
    `<div class="lg-row"><span class="glyph box" style="background:#e9d8a6;border-color:#c5b78f"></span><span>paper</span></div>` +
    `<div class="lg-row"><span class="glyph" style="background:#94d2bd;border:1.5px solid #c5cbd6"></span><span>contribution</span></div>` +
    `<div class="lg-row"><span class="glyph box" style="background:#edeae1;border-color:#d3cdbf;border-style:dashed"></span><span>not yet connected</span></div>` +
    `<div class="lg-title">Edges</div>` +
    relsPresent.map((r) => `<div class="lg-row"><span class="swatch" style="border-color:${relColor[relOf(r)]}"></span><span>${r}</span></div>`).join("") +
    `<div class="lg-row"><span class="swatch faint" style="border-color:${STATED}"></span><span>stated_in</span></div>`;

  document.getElementById("sub").innerHTML =
    `<b>${RAW.contributions.length}</b> contributions · <b>${new Set(RAW.contributions.map((c) => c.paper_id)).size}</b> papers · ` +
    `<b>${RAW.edges.length}</b> cross-paper relations`;

  // init ---------------------------------------------------------------------
  const params = new URLSearchParams(location.search);
  recompute();
  enterMode(params.get("mode") === "edit" ? "edit" : "view");
  if (params.get("apply") === "all") {
    DATA.flags.filter((f) => f.op && f.op.kind === "merge").map((f) => f.id).forEach((id) => review.apply(id));
  }
  </script>
</body>
</html>
"""


def main() -> None:
    data = json.loads(SRC.read_text())
    atlas = {p["id"]: p for p in json.loads(ATLAS.read_text()).get("papers", [])}
    contribs = data.get("contributions", [])
    edges = data.get("edges", [])
    flags = build_flags(contribs, edges, atlas)

    used = {c["paper_id"] for c in contribs}
    papers_meta = {}
    for pid in used:
        p = atlas.get(pid) or {"id": pid}
        papers_meta[pid] = {
            "cite": cite_of(p), "title": p.get("title") or "",
            "year": str(p.get("year") or ""), "authors": authors_str(p),
            "url": p.get("url") or "",
        }

    payload = {"contributions": contribs, "edges": edges, "papers": papers_meta, "flags": flags}
    html = TEMPLATE.replace("__DATA__", json.dumps(payload))
    OUT.write_text(html)
    print(f"wrote {OUT}  ({len(html):,} bytes, {len(contribs)} contributions, "
          f"{len(used)} papers, {len(edges)} relations, {len(flags)} flags)")


if __name__ == "__main__":
    main()
