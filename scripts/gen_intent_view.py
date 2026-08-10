#!/usr/bin/env python3
"""Standalone D3 view of the TYPED CITATION graph (Milestone 2 output), with an
optional overlay of the Cartographer's SEMANTIC graph for overlap comparison.

Two graphs over the same papers, drawn as two layers on one paper-node layout:
  * CITATION layer (solid, arrow): citing -> cited, coloured by intent
    (background / uses_extends / compares_contrasts) + support + priority + a
    bibtex-quality gate. Built over citation_map.json.
  * SEMANTIC layer (dashed, no arrow): the Cartographer's contribution->contribution
    relations (supports / builds_on / refines / contradicts) rolled up to paper
    pairs. Produced by experiments/edge_quality/graph_overlap.py.

Toggle each layer, isolate the overlap, filter by any axis; click an edge for the
per-site justifications (citation) or the relation breakdown + evidence (semantic).

Key-free (stdlib only, D3 from CDN). Writes an inline, double-clickable HTML.

Usage:
  python experiments/edge_quality/graph_overlap.py   # first, builds graph_overlap.json
  python scripts/gen_intent_view.py                  # then this
  python scripts/gen_intent_view.py [OUT_DIR] [PAPERS_JSONL]
"""
from __future__ import annotations
import ast
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EQ = ROOT / "experiments" / "edge_quality" / "out"

OUT_DIR = Path(sys.argv[1]) if len(sys.argv) > 1 else EQ
PAPERS = Path(sys.argv[2]) if len(sys.argv) > 2 else ROOT / "data" / "prior-core-v0.2" / "papers_core.jsonl"

INTENT_F = EQ / "citations_intent.json"          # edge-level intent + per-site detail
TYPED_F = EQ / "citations_typed.json"            # edge-level support + priority
FLAGS_F = EQ / "citation_map.bibtex_flags.json"  # per-edge bibtex_valid quality gate
SEM_F = EQ / "graph_overlap.json"                # rolled-up semantic paper-edges (optional)
OUT = OUT_DIR / "view_intent.html"

# intent = primary encoding (citation edge colour)
INTENT = {"background": "#8d96a5", "uses_extends": "#0a9396", "compares_contrasts": "#ca6702"}
# support = verification verdict (pill colour in the detail panel + a filter)
SUPPORT = {"supports": "#5b8a72", "partial": "#c2a14a", "inconclusive": "#9aa0b0", "does_not": "#ae2012"}
# semantic relation palette (dashed overlay) — kept distinct from the intent hues
SEMREL = {"supports": "#7a9cc6", "builds_on": "#6f9e88", "refines": "#c9a24a", "contradicts": "#b5443a"}


def load_papers(path: Path) -> dict:
    return {p["id"]: p for p in (json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip())}


def yr(p):
    try:
        return int(str((p or {}).get("year") or "").strip()[:4])
    except (ValueError, TypeError):
        return None


def cite(p):
    au = p.get("authors") or []
    if isinstance(au, str):
        try:
            au = ast.literal_eval(au)
        except Exception:
            au = []
    if au and isinstance(au[0], dict):
        au = [a.get("name") or a.get("display_name") or "" for a in au]
    last = au[0].split()[-1] if au and au[0] else (p.get("title") or "?")[:16]
    return f"{last}{' et al.' if len(au) > 1 else ''} ({p.get('year')})"


def key(e):
    return (e["citing_id"], e["cited_id"])


A = load_papers(PAPERS)
intent_edges = json.loads(INTENT_F.read_text(encoding="utf-8"))["edges"]
typed_edges = json.loads(TYPED_F.read_text(encoding="utf-8"))["edges"]
flags = json.loads(FLAGS_F.read_text(encoding="utf-8"))
typed_by = {key(e): e for e in typed_edges}
flags_by = {key(f): f for f in flags}

# semantic overlay (optional — run graph_overlap.py to produce it)
sem_edges_raw = []
if SEM_F.exists():
    sem_edges_raw = json.loads(SEM_F.read_text(encoding="utf-8")).get("sem_edges", [])
else:
    print(f"note: {SEM_F.name} not found — run graph_overlap.py first for the semantic overlay. "
          "Building citation-only view.")

# set of unordered citation paper-pairs (to flag the overlap on both sides)
cit_pairset = {frozenset((e["citing_id"], e["cited_id"])) for e in intent_edges}

# ── join the three axes onto one citation edge record ───────────────────────
edges, node_ids = [], set()
deg_in, deg_out = Counter(), Counter()
for e in intent_edges:
    k = key(e)
    src, dst = e["citing_id"], e["cited_id"]
    node_ids.add(src)
    node_ids.add(dst)
    deg_out[src] += 1
    deg_in[dst] += 1
    t = typed_by.get(k, {})
    fl = flags_by.get(k, {})
    sites = [{"intent": s.get("intent", ""), "conf": round(s.get("confidence", 0), 2),
              "just": s.get("justification", ""), "claim": s.get("claim", "")}
             for s in e.get("sites", [])]
    tsites = {}
    for s in t.get("sites", []):
        tsites[(s.get("claim") or "")[:60]] = (s.get("supports_claim", ""), s.get("priority", ""))
    for s in sites:
        sp = tsites.get((s["claim"])[:60])
        if sp:
            s["support"], s["priority"] = sp
    edges.append({
        "source": src, "target": dst, "cite_key": e.get("cite_key", ""),
        "intent": e.get("intent", ""),
        "support": t.get("support", ""), "priority": t.get("priority", ""),
        "bibtex_valid": fl.get("bibtex_valid", True),
        "n_sites": e.get("n_sites", len(sites)),
        "conf": round(sum(s["conf"] for s in sites) / len(sites), 2) if sites else 0,
        "both": frozenset((src, dst)) in {frozenset((s["a"], s["b"])) for s in sem_edges_raw} if sem_edges_raw else False,
        "sites": sites,
    })

# semantic edges: keep only those on paper pairs whose endpoints we can render;
# add any semantic-only papers into the node set so the overlay is complete.
sem_edges = []
for s in sem_edges_raw:
    node_ids.add(s["a"])
    node_ids.add(s["b"])
    sem_edges.append({"source": s["a"], "target": s["b"], "rel": s["rel"],
                      "relations": s.get("relations", {}), "n": s.get("n", 1),
                      "trust": s.get("trust", 0.5), "evidence": s.get("evidence", []),
                      "both": bool(s.get("both"))})

nodes = [{"id": i, "cite": cite(A.get(i, {})), "title": (A.get(i, {}).get("title") or ""),
          "url": A.get(i, {}).get("url") or "", "year": yr(A.get(i)),
          "date": A.get(i, {}).get("date") or "", "dprec": A.get(i, {}).get("date_precision") or "",
          "venue": A.get(i, {}).get("venue") or "",
          "din": deg_in[i], "dout": deg_out[i], "deg": deg_in[i] + deg_out[i],
          "cited": i in cit_pairset or deg_in[i] + deg_out[i] > 0}
         for i in sorted(node_ids)]

ic = Counter(e["intent"] for e in edges)
sc = Counter(e["support"] for e in edges if e["support"])
pc = Counter(e["priority"] for e in edges if e["priority"])
srel = Counter(s["rel"] for s in sem_edges)
n_blob = sum(1 for e in edges if not e["bibtex_valid"])
n_both = sum(1 for e in edges if e["both"])
meta = {"papers": len(nodes), "edges": len(edges), "sem_edges": len(sem_edges),
        "intent": dict(ic), "support": dict(sc), "priority": dict(pc),
        "semrel": dict(srel), "blob": n_blob, "overlap": n_both}

payload = {"nodes": nodes, "edges": edges, "semEdges": sem_edges,
           "intent": INTENT, "support": SUPPORT, "semrel": SEMREL, "meta": meta}

TEMPLATE = r"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Prior — citation × semantic</title>
<script src="https://cdn.jsdelivr.net/npm/d3@7"></script><style>
 :root{--bg:#faf6ec;--elev:#fbfcfd;--e2:#f1ece0;--bd:#e2e5ea;--tx:#3b4252;--dim:#6b7686;--faint:#9aa0b0;
   --mono:ui-monospace,Menlo,Consolas,monospace;--sans:-apple-system,"Segoe UI",Roboto,sans-serif}
 *{box-sizing:border-box}html,body{height:100%;margin:0}
 body{display:flex;background:var(--bg);color:var(--tx);font-family:var(--sans);font-size:14px}
 #canvas{position:relative;flex:1;min-width:0}svg{width:100%;height:100%;cursor:grab}
 .hdr{position:absolute;top:14px;left:14px;z-index:5;max-width:62%}
 .hdr h1{margin:0;font-size:15px}.hdr .sub{font-size:12px;color:var(--dim);margin-top:2px}
 .abt{font-size:11px;color:#0a9396;cursor:pointer;text-decoration:underline;display:inline-block;margin-top:3px}
 .ctrl{margin-top:8px;font-size:12px;color:var(--dim);display:flex;flex-wrap:wrap;gap:11px 14px;align-items:center;max-width:680px}
 .ctrl label{display:inline-flex;align-items:center;gap:5px}
 .ctrl .seg{display:inline-flex;border:1px solid var(--bd);border-radius:7px;overflow:hidden}
 .ctrl .seg span{padding:4px 9px;cursor:pointer;background:var(--elev);font-size:11.5px;color:var(--dim)}
 .ctrl .seg span.on{background:#0a9396;color:#fff;font-weight:600}
 select,input[type=search]{border:1px solid var(--bd);border-radius:7px;padding:4px 8px;font-size:12px;font-family:var(--sans);background:var(--elev);color:var(--tx)}
 .zoom{position:absolute;top:14px;right:calc(380px + 14px);z-index:5;display:flex;flex-direction:column;gap:1px}
 .zoom button{width:30px;height:30px;background:var(--elev);color:var(--dim);border:1px solid var(--bd);cursor:pointer}
 .legend{position:absolute;bottom:14px;left:14px;z-index:5;background:var(--elev);border:1px solid var(--bd);
   border-radius:8px;padding:9px 11px;font-size:11.5px;max-width:255px}
 .legend .t{font-size:10px;text-transform:uppercase;letter-spacing:.5px;color:var(--faint);margin:8px 0 4px}
 .legend .t:first-child{margin-top:0}
 .lg{display:flex;align-items:center;gap:7px;margin-bottom:3px;cursor:pointer}
 .lg .sw{width:16px;border-top:3px solid;display:inline-block;flex:0 0 auto}.lg.off{opacity:.3}
 .lg .sw.dash{border-top-style:dashed}
 #side{width:380px;flex:0 0 380px;background:var(--elev);border-left:1px solid var(--bd);overflow-y:auto;padding:18px}
 #side .empty{color:var(--faint);text-align:center;padding:34px 6px}
 .k{font-size:10.5px;text-transform:uppercase;letter-spacing:.6px;color:var(--faint);margin:12px 0 3px}
 .pill{display:inline-block;padding:2px 9px;border-radius:5px;font-size:11px;font-weight:600;color:#fff}
 .pill.ln{border:1px solid var(--bd);color:var(--dim);background:var(--e2)}
 .src{font-family:var(--mono);font-size:11px;color:#0a9396}
 .nb{border:1px solid var(--bd);border-radius:6px;padding:8px 10px;margin-bottom:7px;background:var(--e2)}
 .claim{font-size:12px;color:var(--dim);line-height:1.5;margin-top:5px}
 .claim b{background:#ffe9c7;color:#8a5a12;padding:0 2px;border-radius:2px;font-weight:700}
 text.lab{font:600 10.5px var(--sans);fill:var(--tx);paint-order:stroke;stroke:var(--bg);stroke-width:3px;pointer-events:none}
</style></head><body>
<div id="canvas">
 <div class="hdr"><h1>Prior — citation × semantic graph</h1>
   <div class="sub" id="sub"></div>
   <div><span class="abt" onclick="aboutPanel()">ⓘ how this was built</span></div>
   <div class="ctrl">
     <span class="seg" id="layers"><span data-l="cit" class="on">citation</span><span data-l="sem" class="on">semantic</span></span>
     <label><input id="fo" type="checkbox"> overlap only</label>
     <label>support <select id="fs"><option value="">all</option></select></label>
     <label>priority <select id="fp"><option value="">all</option></select></label>
     <label><input id="fb" type="checkbox"> hide blob</label>
     <label>min conf <input id="fc" type="range" min="0" max="0.95" step="0.05" value="0" style="vertical-align:middle"> <span id="fcv">0.00</span></label>
     <input id="q" type="search" placeholder="search papers…" style="width:170px">
   </div>
 </div>
 <div class="zoom"><button id="zi">+</button><button id="zo">&minus;</button><button id="zf">fit</button></div>
 <div class="legend" id="legend"></div>
</div>
<div id="side"><div class="empty">Solid arrows = citations (coloured by intent); dashed = semantic relations. Hover a paper to focus its edges; click an edge for detail. Toggle layers & intent/relation classes; “overlap only” shows shared pairs.</div></div>
<script id="d" type="application/json">__DATA__</script>
<script>
const D=JSON.parse(document.getElementById("d").textContent),SIDE=document.getElementById("side");
const IN=D.intent, SP=D.support, SR=D.semrel;
const ICOL=t=>IN[t]||"#c9cdd2", SCOL=s=>SP[s]||"#9aa0b0", RCOL=r=>SR[r]||"#b9bcc2";
const esc=s=>(s||"").toString().replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const claimHTML=s=>esc(s).replace(/\[CITED:TARGET\]/g,"<b>[CITED:TARGET]</b>").replace(/\[CITED\]/g,"<span style='color:#b9b3a3'>[CITED]</span>");
const MON=["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
const fmtDate=(dt,pr)=>{if(!dt)return"";const y=dt.slice(0,4),m=+dt.slice(5,7),dd=+dt.slice(8,10);if(pr==="day"&&dd)return dd+" "+MON[m-1]+" "+y;if(m)return MON[m-1]+" "+y;return y;};

const off=new Set(), semOff=new Set();   // intent / relation classes toggled off
let layerCit=true, layerSem=D.semEdges.length>0, overlapOnly=false;
let fSupport="", fPriority="", fBlob=false, fConf=0, sel=null;
let sim, node, link, semLink, lab, NODES, CITL, SEML, adj, byId, visNodes=new Set();

const canvas=document.getElementById("canvas");let W=canvas.clientWidth,H=canvas.clientHeight;
const svg=d3.select("#canvas").append("svg").attr("viewBox",[0,0,W,H]);
const _defs=svg.append("defs");
Object.entries(IN).forEach(([t,c])=>_defs.append("marker").attr("id","arr-"+t).attr("viewBox","0 -5 10 10").attr("refX",22).attr("refY",0).attr("markerWidth",8).attr("markerHeight",8).attr("markerUnits","userSpaceOnUse").attr("orient","auto").append("path").attr("d","M0,-4L9,0L0,4").attr("fill",c).attr("fill-opacity",0.85));
const root=svg.append("g");
const zoom=d3.zoom().scaleExtent([0.1,6]).on("zoom",e=>root.attr("transform",e.transform));
svg.call(zoom).on("click",e=>{if(!e.defaultPrevented)clearSel();});
window.addEventListener("keydown",e=>{if(e.key==="Escape")clearSel();if(e.target.tagName==="INPUT"||e.target.tagName==="SELECT")return;if(e.key==="0"||e.key==="f")fit();});
document.getElementById("sub").innerHTML=`<b>${D.nodes.length}</b> papers · <b>${D.edges.length}</b> citations · <b>${D.semEdges.length}</b> semantic edges · <b>${D.meta.overlap}</b> overlap`;

function citVis(e){
  if(!layerCit)return false;
  if(overlapOnly&&!e.both)return false;
  if(off.has(e.intent))return false;
  if(fSupport&&e.support!==fSupport)return false;
  if(fPriority&&e.priority!==fPriority)return false;
  if(fBlob&&!e.bibtex_valid)return false;
  if(e.conf<fConf)return false;
  return true;
}
function semVis(e){
  if(!layerSem)return false;
  if(overlapOnly&&!e.both)return false;
  if(semOff.has(e.rel))return false;
  return true;
}
const nid=x=>x&&x.id!==undefined?x.id:x;
function nodeVis(n){return visNodes.has(n.id);}
function recompVis(){visNodes=new Set();
  CITL.forEach(l=>{if(citVis(l)){visNodes.add(nid(l.source));visNodes.add(nid(l.target));}});
  SEML.forEach(l=>{if(semVis(l)){visNodes.add(nid(l.source));visNodes.add(nid(l.target));}});}

function build(){
  NODES=D.nodes.map(n=>({...n}));
  CITL=D.edges.map(e=>({...e,kind:"cit"}));
  SEML=D.semEdges.map(e=>({...e,kind:"sem"}));
  byId=new Map(NODES.map(n=>[n.id,n]));
  adj=new Map(NODES.map(n=>[n.id,new Set([n.id])]));
  CITL.concat(SEML).forEach(l=>{adj.get(l.source).add(l.target);adj.get(l.target).add(l.source);});
  const rad=d=>3+Math.sqrt(d.deg)*1.6;
  semLink=root.append("g").selectAll("line").data(SEML).join("line")
    .attr("stroke",d=>RCOL(d.rel)).attr("stroke-dasharray","4 3")
    .attr("stroke-width",d=>0.6+Math.min(3,Math.sqrt(d.n))*0.7)
    .attr("stroke-opacity",d=>0.1+0.35*(d.trust||0.5)).style("cursor","pointer")
    .on("click",(e,d)=>{e.stopPropagation();semDetail(d);});
  link=root.append("g").selectAll("line").data(CITL).join("line")
    .attr("stroke",d=>ICOL(d.intent)).attr("stroke-width",d=>0.6+(d.conf||0.5)*1.7)
    .attr("stroke-opacity",d=>0.14+0.42*(d.conf||0.5))
    .attr("marker-end",d=>`url(#arr-${d.intent})`).style("cursor","pointer")
    .on("click",(e,d)=>{e.stopPropagation();edgeDetail(d);});
  node=root.append("g").selectAll("circle").data(NODES).join("circle")
    .attr("r",rad).attr("fill","#b9bcc2").attr("stroke","#fbfcfd").attr("stroke-width",1.2)
    .style("cursor","pointer").call(d3.drag().on("start",ds).on("drag",dd).on("end",de))
    .on("mouseover",(_,d)=>focus(d.id)).on("mouseout",()=>focus(sel))
    .on("click",(e,d)=>{e.stopPropagation();sel=d.id;focus(d.id);paperDetail(d);});
  const top=[...NODES].sort((a,b)=>b.deg-a.deg).slice(0,22);const tp=new Set(top.map(n=>n.id));
  lab=root.append("g").selectAll("text").data(NODES.filter(n=>tp.has(n.id))).join("text").attr("class","lab").attr("dx",d=>rad(d)+3).attr("dy",4).text(d=>d.cite);
  sim=d3.forceSimulation(NODES)
    .force("link",d3.forceLink(CITL.concat(SEML)).id(d=>d.id).distance(l=>l.kind==="sem"?75:55).strength(l=>l.kind==="sem"?0.025:0.06))
    .force("charge",d3.forceManyBody().strength(-130))
    .force("center",d3.forceCenter(W/2,H/2))
    .force("collide",d3.forceCollide(d=>rad(d)+3)).stop();
  for(let i=0;i<440;i++)sim.tick(); tick(); sim.on("tick",tick); applyFilters(); fit();
}
function tick(){
  const pos=s=>s.attr("x1",d=>d.source.x).attr("y1",d=>d.source.y).attr("x2",d=>d.target.x).attr("y2",d=>d.target.y);
  pos(link); pos(semLink);
  node.attr("cx",d=>d.x).attr("cy",d=>d.y); if(lab)lab.attr("x",d=>d.x).attr("y",d=>d.y);}
function applyFilters(){recompVis();
  link.style("display",l=>citVis(l)?null:"none");
  semLink.style("display",l=>semVis(l)?null:"none");
  node.style("display",n=>nodeVis(n)?null:"none");
  if(lab)lab.style("display",n=>nodeVis(n)?null:"none");
  focus(sel);}
function focus(id){
  node.attr("opacity",n=>!nodeVis(n)?0:(!id||adj.get(id).has(n.id)?1:0.12));
  link.attr("stroke-opacity",l=>{if(!citVis(l))return 0;const s=nid(l.source),t=nid(l.target);
    if(!id)return 0.14+0.42*(l.conf||0.5);return(s===id||t===id)?0.9:0.03;});
  semLink.attr("stroke-opacity",l=>{if(!semVis(l))return 0;const s=nid(l.source),t=nid(l.target);
    if(!id)return 0.1+0.35*(l.trust||0.5);return(s===id||t===id)?0.85:0.02;});
  if(lab)lab.style("display",n=>(nodeVis(n)&&(!id||adj.get(id).has(n.id)))?null:"none");
}
const PCITE={},PURL={};D.nodes.forEach(p=>{PCITE[p.id]=p.cite;PURL[p.id]=p.url||"";});
const plink=(p,txt)=>PURL[p]?`<a class="src" style="text-decoration:underline" href="${PURL[p]}" target="_blank">${esc(txt)}</a>`:esc(txt);
function paperDetail(d){
  const out=D.edges.filter(e=>e.source===d.id), inc=D.edges.filter(e=>e.target===d.id);
  const sem=D.semEdges.filter(e=>e.source===d.id||e.target===d.id);
  const crow=e=>`<div class="nb" style="cursor:pointer;padding:6px 9px" onclick="window.__edge('${e.source}','${e.target}')">
    <span class="pill" style="background:${ICOL(e.intent)}">${esc(e.intent)}</span>${e.both?' <span class="pill ln">overlap</span>':''}
    <div class="src" style="margin-top:3px">${e.source===d.id?"→ ":"← "}${esc(PCITE[e.source===d.id?e.target:e.source]||"")}</div></div>`;
  const srow=e=>`<div class="nb" style="cursor:pointer;padding:6px 9px" onclick="window.__sem('${e.source}','${e.target}')">
    <span class="pill" style="background:${RCOL(e.rel)}">${esc(e.rel)}</span>${e.both?' <span class="pill ln">overlap</span>':''}
    <div class="src" style="margin-top:3px">≈ ${esc(PCITE[e.source===d.id?e.target:e.source]||"")}</div></div>`;
  SIDE.innerHTML=`<div class="k">Paper</div>
   <div>${d.url?`<a class="src" style="text-decoration:underline" href="${d.url}" target="_blank">${esc(d.title)}</a>`:esc(d.title)}</div>
   <div class="k">Cite</div><div class="src">${esc(d.cite)}</div>
   <div class="k">Date</div><div>${esc(fmtDate(d.date,d.dprec)||String(d.year||"—"))}${d.venue?` · ${esc(d.venue)}`:""}</div>
   <div class="k">Citations</div><div>${d.dout} outgoing · ${d.din} incoming</div>
   ${out.length?`<div class="k">Cites (${out.length}) — intent</div>${out.map(crow).join("")}`:""}
   ${inc.length?`<div class="k">Cited by (${inc.length}) — intent</div>${inc.map(crow).join("")}`:""}
   ${sem.length?`<div class="k">Semantic relations (${sem.length})</div>${sem.map(srow).join("")}`:""}`;
}
function edgeDetail(e){
  const gate=e.bibtex_valid?"":`<span class="pill" style="background:#ae2012">⚠ blob bibtex (endpoint may be wrong)</span>`;
  SIDE.innerHTML=`<div>
     <span class="pill" style="background:${ICOL(e.intent)}">${esc(e.intent)}</span>
     ${e.support?`<span class="pill" style="background:${SCOL(e.support)}">${esc(e.support)}</span>`:""}
     ${e.priority?`<span class="pill ln">${esc(e.priority)}</span>`:""}${e.both?' <span class="pill ln">overlap</span>':''} ${gate}</div>
   <div class="k">Citation (solid)</div>
   <div class="src">${plink(e.source,PCITE[e.source]||e.source)}</div>
   <div style="text-align:center;color:var(--faint);font-size:11px;margin:2px 0">cites ↓</div>
   <div class="src">${plink(e.target,PCITE[e.target]||e.target)}</div>
   <div class="k">Cite key</div><div class="src">${esc(e.cite_key)}</div>
   <div class="k">Claim sites (${e.sites.length}) · mean conf ${e.conf}</div>
   ${e.sites.map(s=>`<div class="nb">
       <span class="pill" style="background:${ICOL(s.intent)}">${esc(s.intent)}</span>
       ${s.support?`<span class="pill" style="background:${SCOL(s.support)}">${esc(s.support)}</span>`:""}
       ${s.priority?`<span class="pill ln">${esc(s.priority)}</span>`:""}
       <span class="src" style="margin-left:4px">conf ${s.conf}</span>
       <div style="font-size:12px;margin-top:5px">${esc(s.just)}</div>
       ${s.claim?`<div class="claim">${claimHTML(s.claim)}</div>`:""}
     </div>`).join("")}`;
}
function semDetail(e){
  const rels=Object.entries(e.relations||{}).sort((a,b)=>b[1]-a[1]);
  SIDE.innerHTML=`<div><span class="pill" style="background:${RCOL(e.rel)}">${esc(e.rel)}</span>
     <span class="pill ln">semantic · trust ${e.trust}</span>${e.both?' <span class="pill ln">overlap</span>':''}</div>
   <div class="k">Semantic relation (dashed)</div>
   <div class="src">${plink(e.source,PCITE[e.source]||e.source)}</div>
   <div style="text-align:center;color:var(--faint);font-size:11px;margin:2px 0">≈ relates ≈</div>
   <div class="src">${plink(e.target,PCITE[e.target]||e.target)}</div>
   <div class="k">Relation breakdown (${e.n} contribution-edges${e.mixed?", mixed":""})</div>
   <div>${rels.map(([r,n])=>`<span class="pill" style="background:${RCOL(r)};margin:0 4px 4px 0">${esc(r)} ×${n}</span>`).join("")}</div>
   ${e.mixed?`<div style="font-size:11px;color:var(--faint);margin-top:4px">Line colour = most severe relation (contradicts &gt; refines &gt; builds_on &gt; supports), so a contradicts is never hidden.</div>`:""}
   ${e.both?`<div style="font-size:11.5px;color:#0a9396;margin-top:8px">✓ This paper-pair also has a citation edge — click the solid line to compare intent vs. this semantic relation.</div>`:`<div style="font-size:11.5px;color:var(--faint);margin-top:8px">Semantic-only pair (no citation between these papers).</div>`}
   ${(e.evidence||[]).length?`<div class="k">Evidence samples</div>${e.evidence.map(ev=>`<div class="nb"><span class="pill" style="background:${RCOL(ev[0])}">${esc(ev[0])}</span><div style="font-size:12px;margin-top:4px;color:var(--dim)">${esc(ev[1])}</div></div>`).join("")}`:""}`;
}
window.__edge=(s,t)=>{const e=D.edges.find(x=>x.source===s&&x.target===t);if(e)edgeDetail(e);};
window.__sem=(s,t)=>{const e=D.semEdges.find(x=>x.source===s&&x.target===t);if(e)semDetail(e);};
window.__focus=id=>{const d=byId.get(id);if(!d)return;sel=id;focus(id);paperDetail(d);};
function clearSel(){sel=null;focus(null);const qe=document.getElementById("q");if(qe)qe.value="";
  SIDE.innerHTML='<div class="empty">Solid arrows = citations (coloured by intent); dashed = semantic relations. Hover a paper to focus its edges; click an edge for detail. Toggle layers & intent/relation classes; “overlap only” shows shared pairs.</div>';}
function aboutPanel(){const m=D.meta;
  const bar=obj=>Object.entries(obj).map(([k,v])=>`<div style="display:flex;justify-content:space-between;font-size:12px;color:var(--dim);margin:1px 0"><span>${esc(k)}</span><b>${v}</b></div>`).join("");
  SIDE.innerHTML=`<div style="font-weight:700;font-size:14px">How this view was built</div>
   <div style="font-size:11.5px;color:var(--dim);margin:6px 0 12px">Two graphs on one paper layout. <b>Citation</b> (solid, arrow): who cites whom, stamped with intent/support/priority over <span class="src">citation_map.json</span>. <b>Semantic</b> (dashed): the Cartographer's contribution→contribution relations rolled up to paper pairs. Node size = citation degree.</div>
   <div class="k">Overlap (unordered paper-pairs)</div>
   <div style="font-size:12px;color:var(--dim)">${m.overlap} pairs have <b>both</b> a citation and a semantic edge.</div>
   <div class="k">Citation intent</div>${bar(m.intent)}
   <div class="k">Semantic relation</div>${bar(m.semrel)}
   <div class="k">Support · Priority</div>${bar(m.support)}${bar(m.priority)}
   <div class="k">Quality</div><div style="font-size:12px;color:var(--dim)">${m.blob}/${m.edges} citation edges flagged blob-bibtex (filter with “hide blob”).</div>
   <div style="font-size:11.5px;color:var(--dim);margin-top:12px;border-top:1px solid var(--bd);padding-top:9px">The semantic graph is ~70% <i>supports</i> — it rarely fires <i>contradicts</i>, so the contrast/critique signal the intent axis captures is largely invisible to it. Full analysis: <span class="src">out/graph_overlap.md</span>.</div>`;
}
window.aboutPanel=aboutPanel;

// legend
const semLegend=D.semEdges.length?`<div class="t">Semantic relation (dashed · colour = most severe · toggle)</div>`+
  Object.entries(SR).map(([k,c])=>`<div class="lg" data-r="${k}"><span class="sw dash" style="border-color:${c}"></span><span>${esc(k)} (${D.meta.semrel[k]||0})</span></div>`).join(""):"";
document.getElementById("legend").innerHTML=`<div class="t">Citation intent (solid · toggle)</div>`+
  Object.entries(IN).map(([k,c])=>`<div class="lg" data-i="${k}"><span class="sw" style="border-color:${c}"></span><span>${esc(k)} (${D.meta.intent[k]||0})</span></div>`).join("")+
  semLegend+
  `<div class="t">Support (detail pill)</div>`+
  Object.entries(SP).map(([k,c])=>`<div class="lg" style="cursor:default"><span class="sw" style="border-color:${c}"></span><span>${esc(k)}</span></div>`).join("")+
  `<div class="t">Node size = citation degree · → citing→cited</div>`;
document.querySelectorAll(".lg[data-i]").forEach(el=>el.onclick=()=>{const k=el.dataset.i;off.has(k)?off.delete(k):off.add(k);el.classList.toggle("off");applyFilters();});
document.querySelectorAll(".lg[data-r]").forEach(el=>el.onclick=()=>{const k=el.dataset.r;semOff.has(k)?semOff.delete(k):semOff.add(k);el.classList.toggle("off");applyFilters();});

// controls
document.querySelectorAll("#layers span").forEach(el=>el.onclick=()=>{const l=el.dataset.l;
  if(l==="cit")layerCit=!layerCit;else layerSem=!layerSem;el.classList.toggle("on");applyFilters();});
if(!D.semEdges.length){const s=document.querySelector('#layers span[data-l="sem"]');if(s){s.classList.remove("on");s.style.opacity=.4;s.style.pointerEvents="none";}}
[...new Set(D.edges.map(e=>e.support).filter(Boolean))].sort().forEach(s=>document.getElementById("fs").insertAdjacentHTML("beforeend",`<option value="${s}">${s}</option>`));
[...new Set(D.edges.map(e=>e.priority).filter(Boolean))].sort().forEach(p=>document.getElementById("fp").insertAdjacentHTML("beforeend",`<option value="${p}">${p}</option>`));
document.getElementById("fo").onchange=e=>{overlapOnly=e.target.checked;applyFilters();};
document.getElementById("fs").onchange=e=>{fSupport=e.target.value;applyFilters();};
document.getElementById("fp").onchange=e=>{fPriority=e.target.value;applyFilters();};
document.getElementById("fb").onchange=e=>{fBlob=e.target.checked;applyFilters();};
document.getElementById("fc").oninput=e=>{fConf=+e.target.value;document.getElementById("fcv").textContent=fConf.toFixed(2);applyFilters();};
document.getElementById("q").addEventListener("input",runSearch);
function runSearch(){const q=(document.getElementById("q").value||"").trim().toLowerCase();
  if(!q){clearSel();return;}
  const ids=new Set();NODES.forEach(n=>{if(nodeVis(n)&&((n.title||"")+" "+(n.cite||"")).toLowerCase().includes(q))ids.add(n.id);});
  sel=null;node.attr("opacity",n=>!nodeVis(n)?0:(ids.has(n.id)?1:0.08));
  link.attr("stroke-opacity",0.03);semLink.attr("stroke-opacity",0.02);if(lab)lab.style("display",n=>ids.has(n.id)?null:"none");
  const arr=[...ids].map(i=>byId.get(i));
  SIDE.innerHTML=`<div class="k">Search</div><div><b>${arr.length}</b> paper(s) match “${esc(q)}”</div>`+
    arr.slice(0,40).map(d=>`<div class="nb" style="cursor:pointer" onclick="window.__focus('${d.id}')"><div>${esc(d.title||d.cite)}</div><div class="src" style="margin-top:2px">${esc(d.cite)}</div></div>`).join("");
}
document.getElementById("zi").onclick=()=>svg.transition().call(zoom.scaleBy,1.4);
document.getElementById("zo").onclick=()=>svg.transition().call(zoom.scaleBy,1/1.4);
document.getElementById("zf").onclick=fit;
function fit(){const ns=NODES.filter(nodeVis);if(!ns.length)return;const xs=ns.map(n=>n.x),ys=ns.map(n=>n.y);
  const a=Math.min(...xs),b=Math.max(...xs),c=Math.min(...ys),e=Math.max(...ys),gw=b-a||1,gh=e-c||1,k=Math.min((W-160)/gw,(H-160)/gh,1.8);
  svg.transition().duration(400).call(zoom.transform,d3.zoomIdentity.translate(W/2-k*(a+gw/2),H/2-k*(c+gh/2)).scale(k));}
function ds(e,d){if(!e.active)sim.alphaTarget(0.3).restart();d.fx=d.x;d.fy=d.y;}
function dd(e,d){d.fx=e.x;d.fy=e.y;}
function de(e,d){if(!e.active)sim.alphaTarget(0);d.fx=null;d.fy=null;}
build();
</script></body></html>"""

OUT.write_text(TEMPLATE.replace("__DATA__", json.dumps(payload, ensure_ascii=False)), encoding="utf-8")
print(f"wrote {OUT}")
print(f"  {len(nodes)} papers · {len(edges)} citations · {len(sem_edges)} semantic edges · {n_both} overlap")
print(f"  intent {dict(ic)}")
print(f"  semrel {dict(srel)}")
