"""Render the atlas as a self-contained, interactive HTML graph.

Reads data/atlas/atlas.json, writes data/atlas/view.html — one file, no server,
vis-network loaded from a CDN. Claims and papers are nodes (two colours); edges
are coloured by type. Click a node to see its details (claim text + confidence +
source, or paper title). Open the file in a browser.
"""

from __future__ import annotations

import json
from pathlib import Path

from . import config
from .atlas import Atlas

# Edge styling by relation type.
EDGE_STYLE = {
    "stated_in":     {"color": "#c4c4c4", "dashes": True,  "label": "stated_in"},
    "cites":         {"color": "#9aa0a6", "dashes": True,  "label": "cites"},
    "supports":      {"color": "#2e9e4f", "dashes": False, "label": "supports"},
    "contradicts":   {"color": "#d93025", "dashes": False, "label": "contradicts"},
    "refines":       {"color": "#1a73e8", "dashes": False, "label": "refines"},
    "extends":       {"color": "#8430ce", "dashes": False, "label": "extends"},
    "contributes_to":{"color": "#00897b", "dashes": False, "label": "contributes_to"},
}
CLAIM_COLOR = "#e8a13a"
PAPER_COLOR = "#5b8def"


def _truncate(s: str, n: int) -> str:
    s = " ".join((s or "").split())
    return s if len(s) <= n else s[: n - 1] + "…"


# Claim types that represent a paper's contribution (vs. definitional framing /
# background restatement). Heuristic proxy for "contribution" until the global
# canonical layer lands.
CONTRIBUTION_TYPES = {"methodological", "empirical", "theoretical"}


def _nodes_edges(atlas: Atlas, contributions_only: bool = False
                 ) -> tuple[list[dict], list[dict]]:
    if contributions_only:
        keep_claims = {c.id for c in atlas.claims.values()
                       if c.claim_type in CONTRIBUTION_TYPES}
        keep_papers = {atlas.claims[cid].paper_id for cid in keep_claims}
    else:
        keep_claims = set(atlas.claims)
        keep_papers = set(atlas.papers)

    nodes: list[dict] = []
    for p in atlas.papers.values():
        if p.id not in keep_papers:
            continue
        nodes.append({
            "id": p.id, "group": "paper", "shape": "box",
            "label": p.short_cite(), "color": PAPER_COLOR,
            "title": f"{p.title} ({p.year})\ncited_by={p.cited_by_count}",
            "detail": {"kind": "paper", "title": p.title, "cite": p.short_cite(),
                       "year": p.year, "url": p.url},
        })
    for c in atlas.claims.values():
        if c.id not in keep_claims:
            continue
        src = atlas.papers.get(c.paper_id)
        nodes.append({
            "id": c.id, "group": "claim", "shape": "dot",
            "label": _truncate(c.text, 40), "color": CLAIM_COLOR,
            "title": f"[{c.claim_type}] {c.text}\nconfidence={c.confidence}",
            "detail": {"kind": "claim", "text": c.text, "type": c.claim_type,
                       "confidence": c.confidence, "evidence": c.evidence,
                       "source": src.short_cite() if src else c.paper_id},
        })
    keep = keep_claims | keep_papers
    edges: list[dict] = []
    for e in atlas.edges:
        dst = e.to if hasattr(e, "to") else e.dst
        if e.src not in keep or dst not in keep:   # drop edges to filtered nodes
            continue
        st = EDGE_STYLE.get(e.relation, {"color": "#bbb", "dashes": False,
                                         "label": e.relation})
        edges.append({
            "from": e.src, "to": dst,
            "arrows": "to", "color": {"color": st["color"]},
            "dashes": st["dashes"], "label": st["label"], "font": {"size": 9},
            "title": e.evidence or st["label"],
        })
    return nodes, edges


_HTML = """<!doctype html>
<html><head><meta charset="utf-8"><title>Prior — atlas: %TOPIC%</title>
<script src="https://unpkg.com/vis-network/standalone/umd/vis-network.min.js"></script>
<style>
  body{margin:0;font:14px/1.4 system-ui,sans-serif;display:flex;height:100vh}
  #graph{flex:1;height:100%}
  #side{width:340px;border-left:1px solid #ddd;padding:14px;overflow:auto}
  h1{font-size:15px;margin:0 0 4px} .muted{color:#777;font-size:12px}
  .legend span{display:inline-block;margin:2px 8px 2px 0;font-size:12px}
  .sw{display:inline-block;width:12px;height:12px;border-radius:2px;vertical-align:middle;margin-right:3px}
  #detail{margin-top:12px;font-size:13px} #detail b{color:#333}
  .pill{display:inline-block;padding:1px 6px;border-radius:9px;background:#eee;font-size:11px}
</style></head>
<body>
<div id="graph"></div>
<div id="side">
  <h1>Prior — atlas</h1>
  <div class="muted">%TOPIC% · %NP% papers · %NC% claims</div>
  <div class="legend" style="margin-top:8px">
    <span><span class="sw" style="background:%CLAIMC%"></span>claim</span>
    <span><span class="sw" style="background:%PAPERC%"></span>paper</span><br>
    <span><span class="sw" style="background:#2e9e4f"></span>supports</span>
    <span><span class="sw" style="background:#d93025"></span>contradicts</span>
    <span><span class="sw" style="background:#1a73e8"></span>refines</span>
    <span><span class="sw" style="background:#8430ce"></span>extends</span>
    <span><span class="sw" style="background:#9aa0a6"></span>cites/stated_in</span>
  </div>
  <div id="detail" class="muted">Click a node for details.</div>
</div>
<script>
const nodes = new vis.DataSet(%NODES%);
const edges = new vis.DataSet(%EDGES%);
const net = new vis.Network(document.getElementById('graph'),
  {nodes, edges},
  {physics:{stabilization:true,barnesHut:{springLength:140}},
   interaction:{hover:true,tooltipDelay:120},
   nodes:{font:{size:11}}});
const D = document.getElementById('detail');
net.on('click', p => {
  if(!p.nodes.length){D.innerHTML='<span class="muted">Click a node for details.</span>';return;}
  const n = nodes.get(p.nodes[0]).detail;
  if(n.kind==='claim'){
    D.innerHTML = `<span class="pill">${n.type}</span> <span class="pill">conf ${n.confidence}</span>
      <p><b>Claim.</b> ${n.text}</p>
      <p><b>Evidence.</b> <i>${n.evidence||'—'}</i></p>
      <p><b>Source.</b> ${n.source}</p>`;
  } else {
    D.innerHTML = `<p><b>Paper.</b> ${n.title}</p>
      <p>${n.cite} · ${n.year||''}</p>
      ${n.url?`<p><a href="${n.url}" target="_blank">open source ↗</a></p>`:''}`;
  }
});
</script></body></html>"""


def render(atlas_path: Path | None = None, out_path: Path | None = None,
           contributions_only: bool = False) -> Path:
    atlas_path = atlas_path or (config.ATLAS / "atlas.json")
    atlas = Atlas.load(atlas_path)
    nodes, edges = _nodes_edges(atlas, contributions_only=contributions_only)
    n_claims = sum(1 for n in nodes if n["group"] == "claim")
    n_papers = sum(1 for n in nodes if n["group"] == "paper")
    topic = atlas.topic or "—"
    if contributions_only:
        topic += "  ·  contributions only (definitional/background filtered)"
    html = (_HTML
            .replace("%TOPIC%", topic)
            .replace("%NP%", str(n_papers))
            .replace("%NC%", str(n_claims))
            .replace("%CLAIMC%", CLAIM_COLOR).replace("%PAPERC%", PAPER_COLOR)
            .replace("%NODES%", json.dumps(nodes))
            .replace("%EDGES%", json.dumps(edges)))
    if out_path is None:
        out_path = config.ATLAS / ("view_contributions.html" if contributions_only
                                   else "view.html")
    out_path.write_text(html)
    return out_path


if __name__ == "__main__":
    print(render())
