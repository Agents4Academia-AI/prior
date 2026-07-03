#!/usr/bin/env python3
"""Paper-level, community-grouped map of a dense atlas — readable where the radial
contribution view hairballs. One node per paper (sized by degree, coloured by
auto-labelled community), grouped into spatial neighbourhoods. Muted palette,
hover-focus, click-detail, zoom. Key-free (stdlib + networkx); writes an inline
standalone HTML.

Usage: python3 scripts/gen_community_view.py [ATLAS_DIR] [CONTRIB_FILE]
"""
from __future__ import annotations
import os
import ast, json, sys, re
from collections import Counter, defaultdict
from pathlib import Path

DIR = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(
    os.environ.get("PRIOR_DATA_DIR", "data") + "/atlas")
CONTRIB = sys.argv[2] if len(sys.argv) > 2 else "contributions_core.json"
OUT = DIR / "view_communities.html"

# content signatures → label + muted colour (assigned to communities by keyword vote)
LABELS = [
    ("Autonomous AI-scientist systems", "#5b8a72",
     ["ai scientist", "end-to-end", "end to end", "researchagent", "evoscientist",
      "kosmos", "autonomous discovery", "fully automated", "laborator", "automation of"]),
    ("Benchmarks & critiques", "#9c6b4f",
     ["bench", "benchmark", "why llms", "without reasoning", "mlgym", "evaluat",
      "failure", "aren't scientist", "rigorous assessment", "reproducib"]),
    ("AI peer review & feedback", "#4a6d8c",
     ["review", "reviewer", "peer", "feedback", "rebuttal", "openreview", "critic"]),
    ("Hypothesis & idea generation", "#8d6a9f",
     ["hypothes", "hypo", "idea", "novelty", "moose", "rediscover", "exploration"]),
]


def cite(p):
    au = p.get("authors") or []
    if isinstance(au, str):
        try: au = ast.literal_eval(au)
        except Exception: au = []
    last = au[0].split()[-1] if au else (p.get("title") or "?")[:16]
    return f"{last}{' et al.' if len(au) > 1 else ''} ({p.get('year')})"


C = json.loads((DIR / CONTRIB).read_text())
A = {p["id"]: p for p in json.loads((DIR / "atlas.json").read_text())["papers"]}
cons, edges = C["contributions"], C["edges"]
by_paper = defaultdict(list)
for c in cons:
    by_paper[c["paper_id"]].append(c)
papers = list(by_paper)

# paper-level rollup
pair = Counter(); pair_rel = defaultdict(Counter)
padj = defaultdict(set)
for e in edges:
    a, b = e["src"].split("::")[0], e["dst"].split("::")[0]
    if a in by_paper and b in by_paper and a != b:
        k = tuple(sorted((a, b)))
        pair[k] += 1; pair_rel[k][e["relation"]] += 1
        padj[a].add(b); padj[b].add(a)
deg = {p: len(padj[p]) for p in papers}

import networkx as nx
G = nx.Graph(); G.add_nodes_from(papers)
for (a, b) in pair:
    G.add_edge(a, b)
comms = sorted(nx.community.greedy_modularity_communities(G), key=len, reverse=True)

# assign each community a label by keyword vote (greedy 1-1)
def title_blob(cset):
    return " ".join((A.get(p, {}).get("title") or "").lower() for p in cset)
scores = []
for ci, cset in enumerate(comms):
    blob = title_blob(cset)
    for li, (lab, col, kws) in enumerate(LABELS):
        scores.append((sum(blob.count(k) for k in kws), ci, li))
scores.sort(reverse=True)
comm_label = {}; used_l = set(); used_c = set()
for s, ci, li in scores:
    if ci in used_c or li in used_l:
        continue
    comm_label[ci] = LABELS[li]; used_c.add(ci); used_l.add(li)
for ci in range(len(comms)):           # any leftover (more comms than labels)
    comm_label.setdefault(ci, ("Other", "#9aa0b0", []))

paper_comm = {}
for ci, cset in enumerate(comms):
    for p in cset:
        paper_comm[p] = ci

nodes = [{
    "id": p, "cite": cite(A.get(p, {})), "title": (A.get(p, {}).get("title") or ""),
    "deg": deg[p], "comm": paper_comm[p], "n": len(by_paper[p]),
    "url": A.get(p, {}).get("url") or "",
    "top": [c.get("statement", "")[:150] for c in
            sorted(by_paper[p], key=lambda c: len(c.get("statement", "")), reverse=True)[:3]],
} for p in papers]
links = [{"source": a, "target": b, "w": w,
          "rel": pair_rel[(a, b)].most_common(1)[0][0],
          "cross": paper_comm[a] != paper_comm[b]} for (a, b), w in pair.items()]
legend = [{"id": ci, "label": comm_label[ci][0], "color": comm_label[ci][1],
           "n": len(comms[ci])} for ci in range(len(comms))]

payload = {"nodes": nodes, "links": links, "legend": legend,
           "topic": "agents for the scientific process"}

TEMPLATE = r"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Prior — community map</title><script src="https://cdn.jsdelivr.net/npm/d3@7"></script>
<style>
 :root{--bg:#faf6ec;--elev:#fbfcfd;--bd:#e2e5ea;--tx:#3b4252;--dim:#6b7686;--faint:#9aa0b0;
   --mono:ui-monospace,Menlo,Consolas,monospace;--sans:-apple-system,"Segoe UI",Roboto,sans-serif}
 *{box-sizing:border-box}html,body{height:100%;margin:0}
 body{display:flex;background:var(--bg);color:var(--tx);font-family:var(--sans);font-size:14px}
 #canvas{position:relative;flex:1;min-width:0}svg{width:100%;height:100%;cursor:grab}
 .hdr{position:absolute;top:14px;left:14px;z-index:5;max-width:60%}
 .hdr h1{margin:0;font-size:15px}.hdr .sub{font-size:12px;color:var(--dim);margin-top:2px}
 .legend{position:absolute;bottom:14px;left:14px;z-index:5;background:var(--elev);border:1px solid var(--bd);
   border-radius:8px;padding:10px 12px;font-size:12px}
 .legend .t{font-size:10px;text-transform:uppercase;letter-spacing:.5px;color:var(--faint);margin-bottom:6px}
 .lg{display:flex;align-items:center;gap:8px;margin-bottom:4px;cursor:pointer}
 .lg .sw{width:12px;height:12px;border-radius:50%;display:inline-block}
 .lg.off{opacity:.35}
 .zoom{position:absolute;top:14px;right:calc(360px + 14px);z-index:5;display:flex;flex-direction:column;gap:1px}
 .zoom button{width:30px;height:30px;background:var(--elev);color:var(--dim);border:1px solid var(--bd);cursor:pointer}
 #side{width:360px;flex:0 0 360px;background:var(--elev);border-left:1px solid var(--bd);overflow-y:auto;padding:18px}
 #side .empty{color:var(--faint);text-align:center;padding:34px 6px}
 .k{font-size:10.5px;text-transform:uppercase;letter-spacing:.6px;color:var(--faint);margin:12px 0 3px}
 .pill{display:inline-block;padding:2px 9px;border-radius:5px;font-size:11px;font-weight:600;color:#fff}
 .src{font-family:var(--mono);font-size:11px;color:#0a9396}
 ul{margin:4px 0;padding-left:16px}li{margin-bottom:5px;font-size:12.5px;color:var(--dim)}
 text.lab{font:600 11px var(--sans);fill:var(--tx);paint-order:stroke;stroke:var(--bg);stroke-width:3px;pointer-events:none}
 text.clab{font:700 13px var(--sans);paint-order:stroke;stroke:var(--bg);stroke-width:4px;pointer-events:none;opacity:.8}
</style></head><body>
<div id="canvas">
  <div class="hdr"><h1>Prior — community map</h1><div class="sub" id="sub"></div></div>
  <div class="zoom"><button id="zi">+</button><button id="zo">&minus;</button><button id="zf">fit</button></div>
  <div class="legend" id="legend"></div>
</div>
<div id="side"><div class="empty">Hover a paper to focus its links. Click for details. Click a legend swatch to toggle a community.</div></div>
<script id="d" type="application/json">__DATA__</script>
<script>
const D=JSON.parse(document.getElementById("d").textContent);
const SIDE=document.getElementById("side");
const COL={}; D.legend.forEach(l=>COL[l.id]=l.color);
const off=new Set();
document.getElementById("sub").innerHTML=`<b>${D.nodes.length}</b> papers · <b>${D.links.length}</b> paper-level links · <b>${D.legend.length}</b> communities · ${D.topic}`;
const canvas=document.getElementById("canvas");let W=canvas.clientWidth,H=canvas.clientHeight;
const svg=d3.select("#canvas").append("svg").attr("viewBox",[0,0,W,H]);
const root=svg.append("g");
const zoom=d3.zoom().scaleExtent([0.15,4]).on("zoom",e=>root.attr("transform",e.transform));
svg.call(zoom).on("click",e=>{if(!e.defaultPrevented)clearSel();});

// community centroids around a circle
const K=D.legend.length, cx=W/2, cy=H/2, R=Math.min(W,H)/3.2;
const cen={}; D.legend.forEach((l,i)=>{const a=2*Math.PI*i/K - Math.PI/2; cen[l.id]={x:cx+R*Math.cos(a),y:cy+R*Math.sin(a)};});
const rad=d=>3+Math.sqrt(d.deg)*1.7;
const byId=new Map(D.nodes.map(n=>[n.id,n]));
const adj=new Map(D.nodes.map(n=>[n.id,new Set([n.id])]));
D.links.forEach(l=>{adj.get(l.source).add(l.target);adj.get(l.target).add(l.source);});

const link=root.append("g").selectAll("line").data(D.links).join("line")
  .attr("stroke",d=>d.cross?"#c9b89a":"#e4ddcf").attr("stroke-width",d=>Math.min(3,0.5+d.w*0.25))
  .attr("stroke-opacity",d=>d.cross?0.5:0.35);
const node=root.append("g").selectAll("circle").data(D.nodes).join("circle")
  .attr("r",rad).attr("fill",d=>COL[d.comm]).attr("stroke","#fbfcfd").attr("stroke-width",1.2)
  .style("cursor","pointer").call(d3.drag().on("start",ds).on("drag",dd).on("end",de))
  .on("mouseover",(_,d)=>focus(d.id)).on("mouseout",()=>focus(sel))
  .on("click",(e,d)=>{e.stopPropagation();sel=d.id;focus(d.id);detail(d);});
// label only the top hubs per community
const tops=new Set();
D.legend.forEach(l=>{D.nodes.filter(n=>n.comm===l.id).sort((a,b)=>b.deg-a.deg).slice(0,3).forEach(n=>tops.add(n.id));});
const lab=root.append("g").selectAll("text").data(D.nodes.filter(n=>tops.has(n.id))).join("text")
  .attr("class","lab").attr("dx",d=>rad(d)+3).attr("dy",4).text(d=>d.cite);
const clab=root.append("g").selectAll("text").data(D.legend).join("text").attr("class","clab")
  .attr("fill",d=>d.color).attr("text-anchor","middle").attr("x",d=>cen[d.id].x).attr("y",d=>cen[d.id].y-R*0.34).text(d=>d.label);

const sim=d3.forceSimulation(D.nodes)
  .force("link",d3.forceLink(D.links).id(d=>d.id).distance(40).strength(0.05))
  .force("charge",d3.forceManyBody().strength(-70))
  .force("x",d3.forceX(d=>cen[d.comm].x).strength(0.22))
  .force("y",d3.forceY(d=>cen[d.comm].y).strength(0.22))
  .force("collide",d3.forceCollide(d=>rad(d)+2)).stop();
for(let i=0;i<400;i++)sim.tick();
tick(); sim.on("tick",tick);
function tick(){link.attr("x1",d=>d.source.x).attr("y1",d=>d.source.y).attr("x2",d=>d.target.x).attr("y2",d=>d.target.y);
  node.attr("cx",d=>d.x).attr("cy",d=>d.y); lab.attr("x",d=>d.x).attr("y",d=>d.y);}

let sel=null;
function visible(d){return !off.has(d.comm);}
function focus(id){
  node.attr("opacity",n=>!visible(n)?0.04:(!id||adj.get(id).has(n.id)?1:0.12));
  link.attr("stroke-opacity",l=>{const s=l.source.id||l.source,t=l.target.id||l.target;
    const vis=visible(byId.get(s))&&visible(byId.get(t));
    if(!vis)return 0.02; if(!id)return l.cross?0.5:0.3;
    return (s===id||t===id)?0.85:0.03;});
  lab.style("display",n=>(visible(n)&&(!id||adj.get(id).has(n.id)))?null:"none");
}
function detail(d){
  SIDE.innerHTML=`<div><span class="pill" style="background:${COL[d.comm]}">${esc(D.legend[d.comm].label)}</span></div>
    <div class="k">Paper</div><div>${esc(d.title)}</div>
    <div class="k">Cite</div><div class="src">${esc(d.cite)}</div>
    <div class="k">Degree / contributions</div><div>${d.deg} links · ${d.n} contributions</div>
    <div class="k">Top contributions</div><ul>${d.top.map(t=>`<li>${esc(t)}</li>`).join("")}</ul>
    ${d.url?`<div class="k"></div><a class="src" href="${d.url}" target="_blank">open ↗</a>`:""}`;
}
function clearSel(){sel=null;focus(null);SIDE.innerHTML='<div class="empty">Hover a paper to focus its links. Click for details. Click a legend swatch to toggle a community.</div>';}

document.getElementById("legend").innerHTML=`<div class="t">Communities</div>`+
  D.legend.map(l=>`<div class="lg" data-c="${l.id}"><span class="sw" style="background:${l.color}"></span><span>${esc(l.label)} (${l.n})</span></div>`).join("");
document.querySelectorAll(".lg").forEach(el=>el.onclick=()=>{const c=+el.dataset.c;
  if(off.has(c)){off.delete(c);el.classList.remove("off");}else{off.add(c);el.classList.add("off");}
  node.style("display",n=>visible(n)?null:"none"); focus(sel);});

document.getElementById("zi").onclick=()=>svg.transition().call(zoom.scaleBy,1.4);
document.getElementById("zo").onclick=()=>svg.transition().call(zoom.scaleBy,1/1.4);
document.getElementById("zf").onclick=fit;
function fit(){const xs=D.nodes.map(n=>n.x),ys=D.nodes.map(n=>n.y);
  const a=Math.min(...xs),b=Math.max(...xs),c=Math.min(...ys),e=Math.max(...ys);
  const gw=b-a||1,gh=e-c||1,k=Math.min((W-160)/gw,(H-160)/gh,1.8);
  svg.transition().duration(400).call(zoom.transform,d3.zoomIdentity.translate(W/2-k*(a+gw/2),H/2-k*(c+gh/2)).scale(k));}
fit();
function ds(e,d){if(!e.active)sim.alphaTarget(0.3).restart();d.fx=d.x;d.fy=d.y;}
function dd(e,d){d.fx=e.x;d.fy=e.y;}function de(e,d){if(!e.active)sim.alphaTarget(0);d.fx=null;d.fy=null;}
function esc(s){return(s||"").toString().replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));}
</script></body></html>"""

OUT.write_text(TEMPLATE.replace("__DATA__", json.dumps(payload)))
print(f"wrote {OUT}  ({len(payload['nodes'])} papers, {len(payload['links'])} links)")
for l in legend:
    print(f"  community {l['id']}: {l['label']} ({l['n']} papers)  {l['color']}")
