import { useEffect, useRef } from "react";
import * as d3 from "d3";
import type { RenderPayload, RLink } from "../lib/api";

type Node = {
  id: string; comm: number; kind: string; stmt: string; deg: number;
  year: number | null; cite: string;
  x?: number; y?: number; fx?: number | null; fy?: number | null;
};
type Link = { source: string | Node; target: string | Node; rel: string; trust: number; ev: string; tier: string };

const GREY = "#c9cdd2";
const DIRECTED = new Set(["builds_on", "refines"]);

export type EdgePick = { source: string; target: string; rel: string; ev: string; tier: string };

export default function GraphD3({
  payload, selectedId, focusComm, onSelectNode, onSelectEdge,
}: {
  payload: RenderPayload;
  selectedId: string | null;
  focusComm: number | null;
  onSelectNode: (id: string | null) => void;
  onSelectEdge: (e: EdgePick) => void;
}) {
  const svgRef = useRef<SVGSVGElement | null>(null);
  const cb = useRef({ onSelectNode, onSelectEdge });
  cb.current = { onSelectNode, onSelectEdge };
  // view handles for the styling effect (set on (re)build)
  const view = useRef<{
    node?: d3.Selection<SVGCircleElement, Node, SVGGElement, unknown>;
    link?: d3.Selection<SVGLineElement, Link, SVGGElement, unknown>;
    adj?: Map<string, Set<string>>;
  }>({});

  // build / rebuild when the data changes
  useEffect(() => {
    const el = svgRef.current;
    if (!el) return;
    const width = el.clientWidth || 900;
    const height = el.clientHeight || 700;
    const commColor = new Map(payload.legend.map((l) => [l.id, l.color]));

    const nodes: Node[] = payload.contribs.map((c) => ({ ...c }));
    const ids = new Set(nodes.map((n) => n.id));
    const links: Link[] = payload.contribLinks
      .filter((l) => ids.has(l.source) && ids.has(l.target))
      .map((l: RLink) => ({ ...l }));

    const adj = new Map<string, Set<string>>();
    nodes.forEach((n) => adj.set(n.id, new Set()));
    links.forEach((l) => {
      adj.get(l.source as string)?.add(l.target as string);
      adj.get(l.target as string)?.add(l.source as string);
    });

    const svg = d3.select(el);
    svg.selectAll("*").remove();

    const defs = svg.append("defs");
    Object.entries(payload.rel).forEach(([rel, color]) => {
      defs.append("marker").attr("id", `arw-${rel}`).attr("viewBox", "0 -5 10 10")
        .attr("refX", 18).attr("refY", 0).attr("markerWidth", 5).attr("markerHeight", 5)
        .attr("orient", "auto").append("path").attr("d", "M0,-4L8,0L0,4").attr("fill", color);
    });

    const g = svg.append("g");
    const zoom = d3.zoom<SVGSVGElement, unknown>().scaleExtent([0.1, 5])
      .on("zoom", (e) => g.attr("transform", e.transform.toString()));
    svg.call(zoom).on("dblclick.zoom", null);
    svg.on("click", () => cb.current.onSelectNode(null));

    const link = g.append("g").attr("fill", "none").selectAll<SVGLineElement, Link>("line")
      .data(links).join("line")
      .attr("stroke", (d) => payload.rel[d.rel] || "#b9bfc7")
      .attr("stroke-width", (d) => 0.6 + d.trust * 2.2)
      .attr("stroke-opacity", 0.45)
      .attr("marker-end", (d) => (DIRECTED.has(d.rel) ? `url(#arw-${d.rel})` : null))
      .style("cursor", "pointer")
      .on("click", (e, d) => {
        e.stopPropagation();
        cb.current.onSelectEdge({
          source: (d.source as Node).id ?? (d.source as string),
          target: (d.target as Node).id ?? (d.target as string),
          rel: d.rel, ev: d.ev, tier: d.tier,
        });
      });

    const node = g.append("g").selectAll<SVGCircleElement, Node>("circle")
      .data(nodes).join("circle")
      .attr("r", (d) => 3 + Math.sqrt(d.deg) * 1.6)
      .attr("fill", (d) => commColor.get(d.comm) || GREY)
      .attr("stroke", "#fff").attr("stroke-width", 0.8)
      .style("cursor", "pointer")
      .on("click", (e, d) => { e.stopPropagation(); cb.current.onSelectNode(d.id); })
      .call(d3.drag<SVGCircleElement, Node>()
        .on("start", (e, d) => { if (!e.active) sim.alphaTarget(0.2).restart(); d.fx = d.x; d.fy = d.y; })
        .on("drag", (e, d) => { d.fx = e.x; d.fy = e.y; })
        .on("end", (e, d) => { if (!e.active) sim.alphaTarget(0); d.fx = null; d.fy = null; }));
    node.append("title").text((d) => `${d.cite} — ${d.stmt}`);

    // cluster labels at centroids
    const labels = payload.legend.filter((l) => l.id >= 0);
    const lab = g.append("g").selectAll("text").data(labels).join("text")
      .text((d) => d.label).attr("font-size", 13).attr("font-weight", 600)
      .attr("fill", (d) => d.color).attr("text-anchor", "middle")
      .attr("paint-order", "stroke").attr("stroke", "#faf9f5").attr("stroke-width", 3)
      .style("pointer-events", "none").style("opacity", 0.92);

    const sim = d3.forceSimulation<Node>(nodes)
      .force("link", d3.forceLink<Node, Link>(links).id((d) => d.id).distance(42).strength(0.35))
      .force("charge", d3.forceManyBody().strength(-70))
      .force("collide", d3.forceCollide<Node>().radius((d) => 6 + Math.sqrt(d.deg)))
      .force("x", d3.forceX(width / 2).strength(0.045))
      .force("y", d3.forceY(height / 2).strength(0.045))
      .on("tick", () => {
        link.attr("x1", (d) => (d.source as Node).x!).attr("y1", (d) => (d.source as Node).y!)
          .attr("x2", (d) => (d.target as Node).x!).attr("y2", (d) => (d.target as Node).y!);
        node.attr("cx", (d) => d.x!).attr("cy", (d) => d.y!);
        lab.attr("x", (d) => centroid(nodes, d.id).x).attr("y", (d) => centroid(nodes, d.id).y);
      });

    view.current = { node, link, adj };
    return () => { sim.stop(); };
  }, [payload]);

  // selection + cluster-focus styling — no sim rebuild
  useEffect(() => {
    const { node, link, adj } = view.current;
    if (!node || !link) return;
    const near = selectedId ? adj?.get(selectedId) ?? new Set<string>() : null;
    const visible = (id: string, comm: number) =>
      (focusComm == null || comm === focusComm) &&
      (!selectedId || id === selectedId || (near?.has(id) ?? false));
    node.attr("opacity", (d) => (visible(d.id, d.comm) ? 1 : 0.12))
      .attr("stroke", (d) => (d.id === selectedId ? "#1f1e1c" : "#fff"))
      .attr("stroke-width", (d) => (d.id === selectedId ? 2.4 : 0.8));
    link.attr("stroke-opacity", (d) => {
      const s = (d.source as Node).id, t = (d.target as Node).id;
      if (selectedId) return s === selectedId || t === selectedId ? 0.85 : 0.05;
      if (focusComm != null) return 0.35;
      return 0.45;
    });
  }, [selectedId, focusComm]);

  return <svg ref={svgRef} className="graph-d3" />;
}

function centroid(nodes: Node[], _commId: number) {
  // recomputed cheaply each tick; nodes already carry comm via closure caller
  const sel = nodes.filter((n) => (n as Node).comm === _commId && n.x != null);
  if (!sel.length) return { x: -9999, y: -9999 };
  return {
    x: d3.mean(sel, (n) => n.x!) ?? 0,
    y: (d3.mean(sel, (n) => n.y!) ?? 0) - 12,
  };
}
