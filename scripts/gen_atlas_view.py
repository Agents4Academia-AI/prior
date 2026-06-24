#!/usr/bin/env python3
"""Unified atlas viewer over the raw contributions, with a level switch:
  * Contributions — every contribution as a dot, coloured & grouped by its
    EDGE-BASED community (greedy modularity on the relation graph; 9 clusters).
    Edge-isolated contributions are greyed ("unclustered").
  * Communities  — one node per paper, coloured by its dominant cluster, sized by
    degree, with a dashed BRIDGE RING for papers spanning >=2 clusters.
Both share the cluster colouring, legend toggles, hover-focus, click-detail, zoom.
Key-free (stdlib + networkx). Muted palette.

Usage: python3 scripts/gen_atlas_view.py [ATLAS_DIR] [CONTRIB_FILE]
"""
from __future__ import annotations
import ast, json, sys
from collections import Counter, defaultdict
from pathlib import Path

DIR = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(
    "/Users/kk1918_1/Desktop/hackathon/prior/data_hackathon/atlas")
CONTRIB = sys.argv[2] if len(sys.argv) > 2 else "contributions_core.json"
OUT = DIR / "view_atlas.html"
MIN = 8  # min cluster size to be a labelled community

# labels + muted colours, assigned to clusters by size rank (matches the analysis)
# label + muted colour + content keywords; clusters labelled by keyword vote (not size)
LABELKW = [
    ("Autonomous systems", "#5b8a72", ["autonomous", "end-to-end", "fully automated", "pipeline", "ai scientist", "discovery system", "self-evolving"]),
    ("Multi-agent orchestration", "#8d6a9f", ["multi-agent", "orchestrat", "centralized", "decentralized", "asynchronous", "agent team", "coordinat", "tool", "apis"]),
    ("Peer review", "#4a6d8c", ["review", "reviewer", "peer", "rebuttal", "rating", "openreviewer", "manuscript", "acceptance"]),
    ("Benchmarks & eval", "#b07a52", ["benchmark", "evaluat", "reproduc", "metric", "icml", "leaderboard", "assess", "trajectory"]),
    ("Hypothesis generation", "#c2a14a", ["hypothes", "rediscover", "chemistry", "conjecture", "scientific discovery"]),
    ("Idea novelty / eval", "#3f7d7b", ["novelty", "ideation", "feasibility", "originality", "novel idea", "idea generation"]),
    ("RAG / literature-QA", "#b56b78", ["retrieval", "rag", "literature", "citation", "paperqa", "query", "corpus"]),
    ("Safety / risk", "#9c6b6b", ["safety", "risk", "calibrat", "harm", "guardrail", "misuse", "reliab", "hallucinat"]),
    ("Domain-science agents", "#9c7b62", ["biolog", "material", "quantum", "clinical", "genom", "crispr", "cell", "molecul"]),
]
GREY = "#c9cdd2"
REL = {"supports": "#0a9396", "builds_on": "#5b8fb0", "refines": "#ca6702", "contradicts": "#ae2012"}


def cite(p):
    au = p.get("authors") or []
    if isinstance(au, str):
        try: au = ast.literal_eval(au)
        except Exception: au = []
    last = au[0].split()[-1] if au else (p.get("title") or "?")[:16]
    return f"{last}{' et al.' if len(au) > 1 else ''} ({p.get('year')})"


C = json.loads((DIR / CONTRIB).read_text())
A = {p["id"]: p for p in json.loads((DIR / "atlas.json").read_text())["papers"]}
cons = C["contributions"]
_ce = json.loads((DIR / "contributions_core_consensus.json").read_text())
edges = _ce["edges"] if isinstance(_ce, dict) and "edges" in _ce else _ce
ids = {c["id"] for c in cons}
by_paper = defaultdict(list)
for c in cons:
    by_paper[c["paper_id"]].append(c)

import networkx as nx
G = nx.Graph(); G.add_nodes_from(ids)
for e in edges:
    if e["src"] in ids and e["dst"] in ids and e["src"] != e["dst"]:
        G.add_edge(e["src"], e["dst"])
comms = sorted(nx.community.greedy_modularity_communities(G), key=len, reverse=True)
big = [cs for cs in comms if len(cs) >= MIN][:9]
comm_of = {}
for ci, cs in enumerate(big):
    for n in cs:
        comm_of[n] = ci
for n in ids:
    comm_of.setdefault(n, -1)   # isolated / small → grey

# label each cluster by CONTENT (keyword vote over member statements, greedy 1-1)
_st = {c["id"]: (c.get("statement") or "").lower() for c in cons}
_blob = {ci: " ".join(_st[n] for n in cs) for ci, cs in enumerate(big)}
_sc = sorted(((sum(_blob[ci].count(k) for k in kw), ci, li)
              for ci in range(len(big)) for li, (lb, co, kw) in enumerate(LABELKW)), reverse=True)
clabel, _uc, _ul = {}, set(), set()
for s, ci, li in _sc:
    if ci in _uc or li in _ul:
        continue
    clabel[ci] = LABELKW[li]; _uc.add(ci); _ul.add(li)
for ci in range(len(big)):
    clabel.setdefault(ci, (f"cluster {ci}", "#9aa0b0", []))

legend = [{"id": ci, "label": clabel[ci][0], "color": clabel[ci][1],
           "n": sum(1 for n in ids if comm_of[n] == ci)} for ci in range(len(big))]
n_iso = sum(1 for n in ids if comm_of[n] == -1)
legend.append({"id": -1, "label": "unclustered (isolated)", "color": GREY, "n": n_iso})

# paper dominant cluster (over big-cluster members) + bridge
paper_dom, paper_bridge, paper_spread = {}, {}, {}
for p, cs in by_paper.items():
    cl = [comm_of[c["id"]] for c in cs if comm_of[c["id"]] >= 0]
    cnt = Counter(cl)
    paper_dom[p] = cnt.most_common(1)[0][0] if cnt else -1
    paper_spread[p] = sorted(cnt)
    paper_bridge[p] = len(cnt) >= 2

# paper rollup edges
pair = Counter()
for e in edges:
    a, b = e["src"].split("::")[0], e["dst"].split("::")[0]
    if a in by_paper and b in by_paper and a != b:
        pair[tuple(sorted((a, b)))] += 1
deg = Counter()
for (a, b) in pair:
    deg[a] += 1; deg[b] += 1

papers_n = [{"id": p, "cite": cite(A.get(p, {})), "title": A.get(p, {}).get("title") or "",
             "deg": deg[p], "comm": paper_dom[p], "bridge": paper_bridge[p],
             "spread": paper_spread[p], "n": len(by_paper[p]), "url": A.get(p, {}).get("url") or "",
             "top": [c.get("statement", "")[:150] for c in
                     sorted(by_paper[p], key=lambda c: len(c.get("statement", "")), reverse=True)[:3]]}
            for p in by_paper]
paper_links = [{"source": a, "target": b, "w": w, "cross": paper_dom[a] != paper_dom[b]}
               for (a, b), w in pair.items()]
contribs_n = [{"id": c["id"], "comm": comm_of[c["id"]], "kind": c.get("kind", ""),
               "stmt": c.get("statement", ""), "quote": c.get("quote", ""),
               "cite": cite(A.get(c["paper_id"], {}))} for c in cons]
contrib_links = [{"source": e["src"], "target": e["dst"], "rel": e["relation"],
                  "ev": (e.get("evidence") or "")[:160],
                  "trust": round(e.get("trust", 0.5), 2),
                  "tier": (e.get("agreement") or {}).get("tier", "")}
                 for e in edges if e["src"] in ids and e["dst"] in ids
                 and e["src"].split("::")[0] != e["dst"].split("::")[0]]

payload = {"papers": papers_n, "paperLinks": paper_links, "contribs": contribs_n,
           "contribLinks": contrib_links, "legend": legend, "rel": REL,
           "topic": "agents for the scientific process"}

TEMPLATE = r"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Prior — atlas</title>
<script src="https://cdn.jsdelivr.net/npm/d3@7"></script><style>
 :root{--bg:#faf6ec;--elev:#fbfcfd;--e2:#f1ece0;--bd:#e2e5ea;--tx:#3b4252;--dim:#6b7686;--faint:#9aa0b0;
   --mono:ui-monospace,Menlo,Consolas,monospace;--sans:-apple-system,"Segoe UI",Roboto,sans-serif}
 *{box-sizing:border-box}html,body{height:100%;margin:0}
 body{display:flex;background:var(--bg);color:var(--tx);font-family:var(--sans);font-size:14px}
 #canvas{position:relative;flex:1;min-width:0}svg{width:100%;height:100%;cursor:grab}
 .hdr{position:absolute;top:14px;left:14px;z-index:5;max-width:55%}
 .hdr h1{margin:0;font-size:15px}.hdr .sub{font-size:12px;color:var(--dim);margin-top:2px}
 .seg{margin-top:8px;display:inline-flex;border:1px solid var(--bd);border-radius:8px;overflow:hidden}
 .seg button{background:var(--elev);border:none;color:var(--dim);padding:6px 14px;font-size:12px;cursor:pointer}
 .seg button.on{background:#0a9396;color:#fff;font-weight:600}
 .legend{position:absolute;bottom:14px;left:14px;z-index:5;background:var(--elev);border:1px solid var(--bd);
   border-radius:8px;padding:9px 11px;font-size:11.5px;max-width:240px}
 .legend .t{font-size:10px;text-transform:uppercase;letter-spacing:.5px;color:var(--faint);margin:7px 0 4px}
 .legend .t:first-child{margin-top:0}
 .lg{display:flex;align-items:center;gap:7px;margin-bottom:3px;cursor:pointer}
 .lg .sw{width:11px;height:11px;border-radius:50%;display:inline-block;flex:0 0 auto}.lg.off{opacity:.32}
 .rg{display:flex;align-items:center;gap:6px;margin-bottom:2px}.rg .ln{width:16px;border-top:3px solid}
 .zoom{position:absolute;top:14px;right:calc(360px + 14px);z-index:5;display:flex;flex-direction:column;gap:1px}
 .zoom button{width:30px;height:30px;background:var(--elev);color:var(--dim);border:1px solid var(--bd);cursor:pointer}
 #side{width:360px;flex:0 0 360px;background:var(--elev);border-left:1px solid var(--bd);overflow-y:auto;padding:18px}
 #side .empty{color:var(--faint);text-align:center;padding:34px 6px}
 .k{font-size:10.5px;text-transform:uppercase;letter-spacing:.6px;color:var(--faint);margin:12px 0 3px}
 .pill{display:inline-block;padding:2px 9px;border-radius:5px;font-size:11px;font-weight:600;color:#fff}
 .src{font-family:var(--mono);font-size:11px;color:#0a9396}.quote{font-style:italic;color:var(--dim);border-left:2px solid var(--bd);padding-left:9px;font-size:12.5px}
 ul{margin:4px 0;padding-left:16px}li{margin-bottom:5px;font-size:12.5px;color:var(--dim)}
 .nb{border:1px solid var(--bd);border-radius:6px;padding:7px 9px;margin-bottom:6px;background:var(--e2)}
 text.lab{font:600 11px var(--sans);fill:var(--tx);paint-order:stroke;stroke:var(--bg);stroke-width:3px;pointer-events:none}
 text.clab{font:700 12px var(--sans);paint-order:stroke;stroke:var(--bg);stroke-width:4px;pointer-events:none;opacity:.9}
</style></head><body>
<div id="canvas">
 <div class="hdr"><h1>Prior — atlas</h1><div class="sub" id="sub"></div>
   <div class="seg"><button id="mC" class="on">Contributions</button><button id="mP">Communities</button></div>
   <label style="margin-left:10px;font-size:12px;color:var(--dim)">min trust <input id="tf" type="range" min="0" max="0.95" step="0.05" value="0" style="vertical-align:middle"> <span id="tfv">0.00</span></label>
   <label style="margin-left:10px;font-size:12px;color:var(--dim)"><input id="conly" type="checkbox" style="vertical-align:middle"> contradictions only</label></div>
 <div class="zoom"><button id="zi">+</button><button id="zo">&minus;</button><button id="zf">fit</button></div>
 <div class="legend" id="legend"></div>
</div>
<div id="side"><div class="empty">Hover a node to focus its links. Click for details. Toggle clusters in the legend; switch level top-left.</div></div>
<script id="d" type="application/json">__DATA__</script>
<script>
const D=JSON.parse(document.getElementById("d").textContent),SIDE=document.getElementById("side");
const LG={}; D.legend.forEach(l=>LG[l.id]=l);
const COL=id=>(LG[id]?LG[id].color:"#c9cdd2"), LAB=id=>(LG[id]?LG[id].label:"unclustered");
const off=new Set(), kindOff=new Set(); let level="contribs", sel=null, minTrust=0, contradictOnly=false, sim, node, link, lab, ring, NODES, LINKS, adj, byId;
const canvas=document.getElementById("canvas");let W=canvas.clientWidth,H=canvas.clientHeight;
const svg=d3.select("#canvas").append("svg").attr("viewBox",[0,0,W,H]);const root=svg.append("g");
const zoom=d3.zoom().scaleExtent([0.1,5]).on("zoom",e=>root.attr("transform",e.transform));
svg.call(zoom).on("click",e=>{if(!e.defaultPrevented)clearSel();});
const real=D.legend.filter(l=>l.id>=0), cx=W/2, cy=H/2, R=Math.min(W,H)/2.7, cen={};
real.forEach((l,i)=>{const a=2*Math.PI*i/real.length-Math.PI/2;cen[l.id]={x:cx+R*Math.cos(a),y:cy+R*Math.sin(a)};});
cen[-1]={x:cx,y:cy};
const esc=s=>(s||"").toString().replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const pid=id=>id.split("::")[0];
const contradictNodes=new Set(), contradictPapers=new Set();
D.contribLinks.forEach(l=>{if(l.rel==="contradicts"){contradictNodes.add(l.source);contradictNodes.add(l.target);contradictPapers.add(pid(l.source));contradictPapers.add(pid(l.target));}});
const KINDS=Array.from(new Set(D.contribs.map(c=>c.kind).filter(Boolean))).sort();

function build(){
  root.selectAll("*").remove(); const isP=level==="papers";
  NODES=(isP?D.papers:D.contribs).map(n=>({...n}));
  const idset=new Set(NODES.map(n=>n.id));
  LINKS=(isP?D.paperLinks:D.contribLinks).filter(l=>idset.has(l.source)&&idset.has(l.target)).map(l=>({...l}));
  byId=new Map(NODES.map(n=>[n.id,n]));
  adj=new Map(NODES.map(n=>[n.id,new Set([n.id])]));
  LINKS.forEach(l=>{adj.get(l.source).add(l.target);adj.get(l.target).add(l.source);});
  const rad=isP?d=>3+Math.sqrt(d.deg)*1.7:()=>4;
  clab=root.append("g").selectAll("text").data(real).join("text").attr("class","clab")
    .attr("fill",d=>d.color).attr("text-anchor","middle").attr("x",d=>cen[d.id].x).attr("y",d=>cen[d.id].y-R*0.20).text(d=>d.label);
  link=root.append("g").selectAll("line").data(LINKS).join("line")
    .attr("stroke",d=>isP?(d.cross?"#c9b89a":"#e4ddcf"):(D.rel[d.rel]||"#c9cdd2"))
    .attr("stroke-width",d=>isP?Math.min(3,0.5+d.w*0.25):(0.5+(d.trust||0.5)*1.6)).attr("stroke-opacity",d=>isP?0.4:(0.06+0.42*(d.trust||0.5)));
  if(isP){ring=root.append("g").selectAll("circle").data(NODES.filter(d=>d.bridge)).join("circle")
    .attr("fill","none").attr("stroke","#3b4252").attr("stroke-width",1.2).attr("stroke-dasharray","2 2")
    .attr("r",d=>rad(d)+3).style("pointer-events","none");}
  else ring=null;
  node=root.append("g").selectAll("circle").data(NODES).join("circle")
    .attr("r",rad).attr("fill",d=>COL(d.comm)).attr("stroke","#fbfcfd").attr("stroke-width",isP?1.2:0.7)
    .style("cursor","pointer").call(d3.drag().on("start",ds).on("drag",dd).on("end",de))
    .on("mouseover",(_,d)=>focus(d.id)).on("mouseout",()=>focus(sel))
    .on("click",(e,d)=>{e.stopPropagation();sel=d.id;focus(d.id);isP?paperDetail(d):contribDetail(d);});
  let ld=[];
  if(isP){const tp=new Set();real.forEach(l=>D.papers.filter(n=>n.comm===l.id).sort((a,b)=>b.deg-a.deg).slice(0,3).forEach(n=>tp.add(n.id)));ld=NODES.filter(n=>tp.has(n.id));}
  lab=root.append("g").selectAll("text").data(ld).join("text").attr("class","lab").attr("dx",d=>rad(d)+3).attr("dy",4).text(d=>d.cite);
  sim=d3.forceSimulation(NODES)
    .force("link",d3.forceLink(LINKS).id(d=>d.id).distance(isP?40:20).strength(isP?0.05:0.03))
    .force("charge",d3.forceManyBody().strength(isP?-70:-18))
    .force("x",d3.forceX(d=>cen[d.comm].x).strength(d=>d.comm<0?0.04:0.25))
    .force("y",d3.forceY(d=>cen[d.comm].y).strength(d=>d.comm<0?0.04:0.25))
    .force("collide",d3.forceCollide(d=>rad(d)+1.4)).stop();
  for(let i=0;i<440;i++)sim.tick(); tick(); sim.on("tick",tick); applyFilters(); fit();
}
function tick(){link.attr("x1",d=>d.source.x).attr("y1",d=>d.source.y).attr("x2",d=>d.target.x).attr("y2",d=>d.target.y);
  node.attr("cx",d=>d.x).attr("cy",d=>d.y); if(lab)lab.attr("x",d=>d.x).attr("y",d=>d.y);
  if(ring)ring.attr("cx",d=>d.x).attr("cy",d=>d.y);}
function nodeVis(d){if(!d)return false;const isP=level==="papers";
  if(off.has(d.comm))return false;
  if(!isP&&kindOff.has(d.kind))return false;
  if(contradictOnly&&!(isP?contradictPapers.has(d.id):contradictNodes.has(d.id)))return false;
  return true;}
function applyFilters(){const isP=level==="papers";
  node.style("display",d=>nodeVis(d)?null:"none");
  if(ring)ring.style("display",d=>nodeVis(d)?null:"none");
  if(link)link.style("display",l=>{const s=l.source.id||l.source,t=l.target.id||l.target;
    if(!nodeVis(byId.get(s))||!nodeVis(byId.get(t)))return "none";
    if(!isP){if(contradictOnly&&l.rel!=="contradicts")return "none";if(l.trust!==undefined&&l.trust<minTrust)return "none";}
    return null;});}
function focus(id){
  node.attr("opacity",n=>!nodeVis(n)?0:(!id||adj.get(id).has(n.id)?1:0.1));
  link.attr("stroke-opacity",l=>{const s=l.source.id||l.source,t=l.target.id||l.target;
    if(!id)return level==="papers"?(l.cross?0.4:0.3):(0.06+0.42*(l.trust||0.5)); return(s===id||t===id)?0.9:0.02;});
  if(lab)lab.style("display",n=>(nodeVis(n)&&(!id||adj.get(id).has(n.id)))?null:"none");
}
function paperDetail(d){const spread=d.spread.map(LAB).join(" · ");
  SIDE.innerHTML=`<div><span class="pill" style="background:${COL(d.comm)}">${esc(LAB(d.comm))}</span>${d.bridge?' <span class="pill" style="background:#3b4252">bridge</span>':''}</div>
  <div class="k">Paper</div><div>${esc(d.title)}</div><div class="k">Cite</div><div class="src">${esc(d.cite)}</div>
  <div class="k">Degree / contributions</div><div>${d.deg} links · ${d.n} contributions</div>
  <div class="k">Clusters spanned</div><div>${esc(spread)||"—"}</div>
  <div class="k">Top contributions</div><ul>${d.top.map(t=>`<li>${esc(t)}</li>`).join("")}</ul>
  ${d.url?`<a class="src" href="${d.url}" target="_blank">open ↗</a>`:""}`;}
const PCITE={};D.papers.forEach(p=>PCITE[p.id]=p.cite);
function contribDetail(d){const nb=D.contribLinks.filter(l=>l.source===d.id||l.target===d.id).map(l=>{const o=l.source===d.id;return{rel:l.rel,dir:o?"→":"←",other:o?l.target:l.source,ev:l.ev,trust:l.trust,tier:l.tier};});
  SIDE.innerHTML=`<div><span class="pill" style="background:${COL(d.comm)}">${esc(LAB(d.comm))}</span> <span class="pill" style="background:#9aa0b0">${esc(d.kind||"contribution")}</span></div>
   <div class="k">Contribution</div><div>${esc(d.stmt)}</div>
   ${d.quote?`<div class="k">Stated as</div><div class="quote">${esc(d.quote)}</div>`:""}
   <div class="k">Paper</div><div class="src">${esc(d.cite)}</div>
   <div class="k">Cross-paper relations (${nb.length})</div>
   ${nb.map(n=>`<div class="nb"><span class="pill" style="background:${D.rel[n.rel]||'#9aa0b0'}">${n.rel}</span> <span class="src">trust ${n.trust} · ${esc(n.tier)}</span>
     <div class="src" style="margin-top:3px">${n.dir} ${esc(PCITE[pid(n.other)]||n.other)}</div>
     ${n.ev?`<div style="font-size:11.5px;color:var(--dim);margin-top:3px">${esc(n.ev)}</div>`:""}</div>`).join("")||'<div class="empty" style="padding:6px">none — isolated</div>'}`;}
function clearSel(){sel=null;focus(null);SIDE.innerHTML='<div class="empty">Hover a node to focus its links. Click for details. Toggle clusters in the legend; switch level top-left.</div>';}
function setLevel(l){level=l;sel=null;document.getElementById("mC").classList.toggle("on",l==="contribs");document.getElementById("mP").classList.toggle("on",l==="papers");
  document.getElementById("sub").innerHTML=l==="papers"?`<b>${D.papers.length}</b> papers · <b>${D.paperLinks.length}</b> links · ${D.topic}`:`<b>${D.contribs.length}</b> contributions · <b>${D.contribLinks.length}</b> relations · ${D.topic}`;build();}
document.getElementById("mC").onclick=()=>setLevel("contribs");document.getElementById("mP").onclick=()=>setLevel("papers");
document.getElementById("legend").innerHTML=`<div class="t">Clusters (edge-based)</div>`+
  D.legend.map(l=>`<div class="lg" data-c="${l.id}"><span class="sw" style="background:${l.color}"></span><span>${esc(l.label)} (${l.n})</span></div>`).join("")+
  `<div class="t">Relations (opacity/width = consensus trust)</div>`+Object.entries(D.rel).map(([k,c])=>`<div class="rg"><span class="ln" style="border-color:${c}"></span><span>${k}</span></div>`).join("")+
  `<div class="t">Contribution kinds (toggle, contributions view)</div>`+
  KINDS.map(k=>`<div class="lg" data-k="${esc(k)}"><span class="sw" style="background:#b9bcc2"></span><span>${esc(k)}</span></div>`).join("")+
  `<div class="t">Papers view</div><div class="rg"><span class="ln" style="border-top:1.2px dashed #3b4252;width:16px"></span><span>bridge (spans ≥2)</span></div>`;
document.querySelectorAll(".lg").forEach(el=>el.onclick=()=>{
  if(el.dataset.c!==undefined){const c=+el.dataset.c; off.has(c)?off.delete(c):off.add(c);}
  else if(el.dataset.k!==undefined){const k=el.dataset.k; kindOff.has(k)?kindOff.delete(k):kindOff.add(k);}
  el.classList.toggle("off"); applyFilters(); focus(sel);});
document.getElementById("tf").oninput=e=>{minTrust=+e.target.value;document.getElementById("tfv").textContent=minTrust.toFixed(2);applyFilters();};
document.getElementById("conly").onchange=e=>{contradictOnly=e.target.checked;applyFilters();focus(sel);};
document.getElementById("zi").onclick=()=>svg.transition().call(zoom.scaleBy,1.4);document.getElementById("zo").onclick=()=>svg.transition().call(zoom.scaleBy,1/1.4);document.getElementById("zf").onclick=fit;
function fit(){const xs=NODES.map(n=>n.x),ys=NODES.map(n=>n.y);const a=Math.min(...xs),b=Math.max(...xs),c=Math.min(...ys),e=Math.max(...ys),gw=b-a||1,gh=e-c||1,k=Math.min((W-150)/gw,(H-150)/gh,1.8);
  svg.transition().duration(400).call(zoom.transform,d3.zoomIdentity.translate(W/2-k*(a+gw/2),H/2-k*(c+gh/2)).scale(k));}
function ds(e,d){if(!e.active)sim.alphaTarget(0.3).restart();d.fx=d.x;d.fy=d.y;}function dd(e,d){d.fx=e.x;d.fy=e.y;}function de(e,d){if(!e.active)sim.alphaTarget(0);d.fx=null;d.fy=null;}
const _q=new URLSearchParams(location.search);
const _tp=_q.get("trust");
if(_tp){minTrust=+_tp;document.getElementById("tf").value=_tp;document.getElementById("tfv").textContent=(+_tp).toFixed(2);}
if(_q.get("contradicts")){contradictOnly=true;document.getElementById("conly").checked=true;}
setLevel("contribs");
</script></body></html>"""

OUT.write_text(TEMPLATE.replace("__DATA__", json.dumps(payload)))
print(f"wrote {OUT}")
for l in legend:
    print(f"  cluster {l['id']:>2}: {l['label']} ({l['n']})  {l['color']}")
