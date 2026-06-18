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
# Muted, low-saturation palette (Nord-inspired) — easy on the eyes.
EDGE_STYLE = {
    "stated_in":     {"color": "#dde2ea", "dashes": True,  "label": "stated_in"},
    "cites":         {"color": "#cdd3de", "dashes": True,  "label": "cites"},
    "supports":      {"color": "#a3be8c", "dashes": False, "label": "supports"},
    "contradicts":   {"color": "#bf828a", "dashes": False, "label": "contradicts"},
    "refines":       {"color": "#81a1c1", "dashes": False, "label": "refines"},
    "extends":       {"color": "#b48ead", "dashes": False, "label": "extends"},
    "contributes_to":{"color": "#8fbcbb", "dashes": False, "label": "contributes_to"},
}
CLAIM_COLOR = "#9db8d6"   # soft blue dot
PAPER_COLOR = "#dfe3ea"   # light grey-blue box (dark text stays readable)

# Contribution nodes, coloured by kind (muted).
KIND_COLOR = {
    "method": "#9db8d6", "framework": "#c2a8c9", "empirical_finding": "#aecf99",
    "dataset": "#93c4c2", "model": "#dba98e", "analysis": "#9fcad4",
    "resource": "#e3cd97", "other": "#c2c7d0",
}


def _truncate(s: str, n: int) -> str:
    s = " ".join((s or "").split())
    return s if len(s) <= n else s[: n - 1] + "…"


def _fill(c: str) -> dict:
    """Explicit color object so vis-network can't fall back to its default group
    palette (whose group-1 default is neon yellow)."""
    return {"background": c, "border": "#c5cbd6",
            "highlight": {"background": c, "border": "#9aa0b0"},
            "hover": {"background": c, "border": "#9aa0b0"}}


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
            "id": p.id,  "shape": "box",
            "label": p.short_cite(), "color": _fill(PAPER_COLOR),
            "title": f"{p.title} ({p.year})\ncited_by={p.cited_by_count}",
            "detail": {"kind": "paper", "title": p.title, "cite": p.short_cite(),
                       "year": p.year, "url": p.url},
        })
    for c in atlas.claims.values():
        if c.id not in keep_claims:
            continue
        src = atlas.papers.get(c.paper_id)
        nodes.append({
            "id": c.id,  "shape": "dot",
            "label": _truncate(c.text, 40), "color": _fill(CLAIM_COLOR),
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
<script src="https://unpkg.com/vis-network@9.1.9/standalone/umd/vis-network.min.js"></script>
<style>
  body{margin:0;font:14px/1.4 system-ui,sans-serif;display:flex;height:100vh;
       background:#f5f6f8;color:#3b4252}
  #graph{flex:1;height:100%;background:#f5f6f8}
  #side{width:340px;border-left:1px solid #e2e5ea;padding:14px;overflow:auto;background:#fbfcfd}
  h1{font-size:15px;margin:0 0 4px} .muted{color:#8a909c;font-size:12px}
  .legend span{display:inline-block;margin:2px 8px 2px 0;font-size:12px}
  .sw{display:inline-block;width:12px;height:12px;border-radius:3px;vertical-align:middle;margin-right:3px}
  #detail{margin-top:12px;font-size:13px} #detail b{color:#4c566a}
  .pill{display:inline-block;padding:1px 6px;border-radius:9px;background:#eceff4;font-size:11px}
</style></head>
<body>
<div id="graph"></div>
<div id="side">
  <h1>Prior — atlas</h1>
  <div class="muted">%TOPIC% · %NP% papers · %NC% claims</div>
  <div class="legend" style="margin-top:8px">
    <span><span class="sw" style="background:%CLAIMC%"></span>claim</span>
    <span><span class="sw" style="background:%PAPERC%"></span>paper</span><br>
    <span><span class="sw" style="background:#a3be8c"></span>supports</span>
    <span><span class="sw" style="background:#bf828a"></span>contradicts</span>
    <span><span class="sw" style="background:#81a1c1"></span>refines</span>
    <span><span class="sw" style="background:#b48ead"></span>extends</span>
    <span><span class="sw" style="background:#cdd3de"></span>cites/stated_in</span>
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
   groups:{useDefaultGroups:false},
   nodes:{font:{size:11,color:'#3b4252'},borderWidth:1,shapeProperties:{useBorderWithImage:false}},
   edges:{font:{size:9,color:'#8a909c',strokeWidth:3,strokeColor:'#f5f6f8'},
          smooth:{type:'continuous'}}});
const D = document.getElementById('detail');
net.on('click', p => {
  if(!p.nodes.length){D.innerHTML='<span class="muted">Click a node for details.</span>';return;}
  const n = nodes.get(p.nodes[0]).detail;
  if(n.kind==='contribution'){
    D.innerHTML = `<span class="pill">${n.ckind}</span>
      <p><b>Contribution.</b> ${n.statement}</p>
      <p><b>Stated as.</b> <i>${n.quote||'—'}</i></p>
      <p><b>Paper.</b> ${n.source}</p>`;
  } else if(n.kind==='claim'){
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
    n_claims = sum(1 for n in nodes if n["shape"] == "dot")
    n_papers = sum(1 for n in nodes if n["shape"] == "box")
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


def render_contributions(out_path: Path | None = None) -> Path:
    """Render the REAL contributions (data/atlas/contributions.json) as a graph:
    each contribution is a node (coloured by kind) attached to its paper."""
    contribs = json.loads((config.ATLAS / "contributions.json").read_text())
    atlas = Atlas.load(config.ATLAS / "atlas.json")
    cs = contribs.get("contributions", [])
    paper_ids = list(dict.fromkeys(c["paper_id"] for c in cs))

    nodes: list[dict] = []
    for pid in paper_ids:
        p = atlas.papers.get(pid)
        nodes.append({
            "id": pid,  "shape": "box",
            "label": p.short_cite() if p else pid, "color": _fill(PAPER_COLOR),
            "title": (p.title if p else pid),
            "detail": {"kind": "paper", "title": (p.title if p else pid),
                       "cite": p.short_cite() if p else pid,
                       "year": p.year if p else None, "url": p.url if p else ""},
        })
    edges: list[dict] = []
    for c in cs:
        p = atlas.papers.get(c["paper_id"])
        src = f"{p.short_cite()} — {p.title}" if p else c["paper_id"]
        nodes.append({
            "id": c["id"],  "shape": "dot",
            "label": _truncate(c["statement"], 42),
            "color": _fill(KIND_COLOR.get(c["kind"], "#c2c7d0")),
            "title": f"[{c['kind']}] " + _truncate(c["statement"], 55),
            "detail": {"kind": "contribution", "ckind": c["kind"],
                       "statement": c["statement"], "quote": c.get("quote", ""),
                       "source": src},
        })
        edges.append({"from": c["id"], "to": c["paper_id"], "arrows": "to",
                      "color": {"color": "#dde2ea"}, "label": "stated_in",
                      "font": {"size": 8}})

    # cross-contribution relations (the cross-paper "cross-talk")
    rels = 0
    for e in contribs.get("edges", []):
        st = EDGE_STYLE.get(e["relation"], {"color": "#bbb", "dashes": False,
                                            "label": e["relation"]})
        edges.append({"from": e["src"], "to": e["dst"], "arrows": "to",
                      "color": {"color": st["color"]}, "dashes": st["dashes"],
                      "label": st["label"], "font": {"size": 9},
                      "title": e.get("evidence", "")})
        rels += 1

    topic = (f"{atlas.topic or '—'}  ·  {len(cs)} contributions from {len(paper_ids)} "
             f"papers  ·  {rels} cross-paper relations")
    html = (_HTML.replace("%TOPIC%", topic)
            .replace("%NP%", str(len(paper_ids))).replace("%NC%", str(len(cs)))
            .replace("%CLAIMC%", CLAIM_COLOR).replace("%PAPERC%", PAPER_COLOR)
            .replace("%NODES%", json.dumps(nodes)).replace("%EDGES%", json.dumps(edges)))
    out_path = out_path or (config.ATLAS / "view_contributions.html")
    out_path.write_text(html)
    return out_path


_EVO_HTML = """<!doctype html>
<html><head><meta charset="utf-8"><title>Prior — atlas evolution</title>
<script src="https://unpkg.com/vis-network@9.1.9/standalone/umd/vis-network.min.js"></script>
<style>
  body{margin:0;font:14px system-ui,sans-serif;display:flex;height:100vh;
       background:#f5f6f8;color:#3b4252}
  #graph{flex:1;height:100%;background:#f5f6f8;position:relative}
  #side{width:340px;border-left:1px solid #e2e5ea;padding:14px;overflow:auto;background:#fbfcfd}
  .bar{position:absolute;top:10px;left:10px;z-index:10;background:#fbfcfdee;
       padding:8px 12px;border:1px solid #e2e5ea;border-radius:8px}
  .bar button{font:13px system-ui;margin:0 3px;padding:4px 9px;cursor:pointer;
       border:1px solid #d3d8e0;border-radius:6px;background:#fff;color:#4c566a}
  .bar button.on{background:#81a1c1;color:#fff;border-color:#81a1c1}
  h1{font-size:15px;margin:0 0 4px} .muted{color:#8a909c;font-size:12px}
  .legend span{display:inline-block;margin:2px 8px 2px 0;font-size:12px}
  .sw{display:inline-block;width:12px;height:12px;border-radius:3px;vertical-align:middle;margin-right:3px}
  #detail{margin-top:12px;font-size:13px} #detail b{color:#4c566a}
  .pill{display:inline-block;padding:1px 6px;border-radius:9px;background:#eceff4;font-size:11px}
</style></head><body>
<div class="bar"><b>Atlas evolution</b>&nbsp;
  <button id="s1" onclick="setStage(1)">1 · Papers</button>
  <button id="s2" onclick="setStage(2)">2 · + Contributions</button>
  <button id="s3" onclick="setStage(3)">3 · + Relations</button></div>
<div id="graph"></div>
<div id="side">
  <h1>Prior — atlas evolution</h1>
  <div class="muted" id="cap"></div>
  <div class="legend" style="margin-top:8px">
    <span><span class="sw" style="background:%PAPERC%"></span>paper</span>
    <span class="muted">· node colour = contribution kind</span><br>
    <span><span class="sw" style="background:#a3be8c"></span>supports</span>
    <span><span class="sw" style="background:#bf828a"></span>contradicts</span>
    <span><span class="sw" style="background:#81a1c1"></span>refines</span>
    <span><span class="sw" style="background:#b48ead"></span>extends</span>
    <span><span class="sw" style="background:#dde2ea"></span>stated_in</span>
  </div>
  <div id="detail" class="muted">Click a node for details.</div>
</div>
<script>
const nodes = new vis.DataSet(%NODES%);
const edges = new vis.DataSet(%EDGES%);
const net = new vis.Network(document.getElementById('graph'), {nodes, edges},
  {physics:{stabilization:true,barnesHut:{springLength:130}},
   interaction:{hover:true,tooltipDelay:150},
   groups:{useDefaultGroups:false},
   nodes:{font:{size:11,color:'#3b4252'},borderWidth:1},
   edges:{font:{size:9,color:'#8a909c',strokeWidth:3,strokeColor:'#f5f6f8'},
          smooth:{type:'continuous'}}});
const CAP = ['','%N1% papers','%N1% papers + their %N2% contributions',
             '%N1% papers · %N2% contributions · %N3% cross-paper relations'];
const D = document.getElementById('detail');
net.on('click', p => {
  if(!p.nodes.length){D.innerHTML='<span class="muted">Click a node for details.</span>';return;}
  const n = nodes.get(p.nodes[0]).detail;
  if(n.kind==='contribution'){
    D.innerHTML = `<span class="pill">${n.ckind}</span>
      <p><b>Contribution.</b> ${n.statement}</p>
      <p><b>Stated as.</b> <i>${n.quote||'—'}</i></p>
      <p><b>Source.</b> ${n.source}</p>`;
  } else {
    D.innerHTML = `<p><b>Paper.</b> ${n.title}</p><p>${n.cite}${n.year?' · '+n.year:''}</p>
      ${n.url?`<p><a href="${n.url}" target="_blank">open source ↗</a></p>`:''}`;
  }
});
function setStage(s){
  nodes.forEach(n => nodes.update({id:n.id, hidden: n.stage>s}));
  edges.forEach(e => edges.update({id:e.id, hidden: e.stage>s}));
  for(const i of [1,2,3]) document.getElementById('s'+i).className = (i<=s?'on':'');
  document.getElementById('cap').textContent = CAP[s];
}
setStage(1);
</script></body></html>"""


def render_evolution(out_path: Path | None = None) -> Path:
    """Staged-reveal view telling the pipeline story: papers → contributions →
    relations. One HTML with stage buttons."""
    contribs = json.loads((config.ATLAS / "contributions.json").read_text())
    atlas = Atlas.load(config.ATLAS / "atlas.json")
    cs = contribs.get("contributions", [])
    rels = contribs.get("edges", [])
    paper_ids = list(dict.fromkeys(c["paper_id"] for c in cs))

    nodes: list[dict] = []
    for pid in paper_ids:                       # stage 1
        p = atlas.papers.get(pid)
        cite = p.short_cite() if p else pid
        nodes.append({"id": pid, "stage": 1,  "shape": "box",
                      "label": cite, "color": _fill(PAPER_COLOR),
                      "title": (p.title if p else pid),
                      "detail": {"kind": "paper", "title": (p.title if p else pid),
                                 "cite": cite, "year": p.year if p else None,
                                 "url": p.url if p else ""}})
    for c in cs:                                # stage 2
        p = atlas.papers.get(c["paper_id"])
        src = (f"{p.short_cite()} — {p.title}" if p else c["paper_id"])
        nodes.append({"id": c["id"], "stage": 2, 
                      "shape": "dot", "label": _truncate(c["statement"], 38),
                      "color": _fill(KIND_COLOR.get(c["kind"], "#c2c7d0")),
                      "title": f"[{c['kind']}] " + _truncate(c["statement"], 55),
                      "detail": {"kind": "contribution", "ckind": c["kind"],
                                 "statement": c["statement"],
                                 "quote": c.get("quote", ""), "source": src}})

    edges: list[dict] = []
    eid = 0
    for c in cs:                                # stage 2: provenance
        eid += 1
        edges.append({"id": eid, "stage": 2, "from": c["id"], "to": c["paper_id"],
                      "arrows": "to", "color": {"color": "#dcdcdc"}, "label": "stated_in",
                      "font": {"size": 8}})
    for e in rels:                              # stage 3: cross-talk
        eid += 1
        st = EDGE_STYLE.get(e["relation"], {"color": "#bbb", "dashes": False,
                                            "label": e["relation"]})
        edges.append({"id": eid, "stage": 3, "from": e["src"], "to": e["dst"],
                      "arrows": "to", "color": {"color": st["color"]},
                      "dashes": st["dashes"], "label": st["label"],
                      "font": {"size": 9}, "title": e.get("evidence", "")})

    html = (_EVO_HTML.replace("%NODES%", json.dumps(nodes))
            .replace("%EDGES%", json.dumps(edges))
            .replace("%PAPERC%", PAPER_COLOR)
            .replace("%N1%", str(len(paper_ids))).replace("%N2%", str(len(cs)))
            .replace("%N3%", str(len(rels))))
    out_path = out_path or (config.ATLAS / "view_evolution.html")
    out_path.write_text(html)
    return out_path


if __name__ == "__main__":
    print(render())
