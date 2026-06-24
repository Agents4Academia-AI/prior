import { useEffect, useRef } from "react";
import * as d3 from "d3";
import type { PaperGraph, ClaimNode } from "../lib/types";
import { claimTypeColor, claimRelationColor } from "../lib/colors";

type N = ClaimNode & { x?: number; y?: number; fx?: number | null; fy?: number | null };
type L = { source: string | N; target: string | N; relation: string };

export default function ClaimGraph({
  graph, highlightContrib, selectedId, onSelectClaim,
}: {
  graph: PaperGraph;
  highlightContrib?: string | null;
  selectedId?: string | null;
  onSelectClaim?: (c: ClaimNode | null) => void;
}) {
  const svgRef = useRef<SVGSVGElement | null>(null);

  useEffect(() => {
    const el = svgRef.current;
    if (!el) return;
    const width = el.clientWidth || 600, height = el.clientHeight || 460;
    const nodes: N[] = graph.nodes.map((n) => ({ ...n }));
    const ids = new Set(nodes.map((n) => n.id));
    const links: L[] = graph.edges
      .filter((e) => ids.has(e.source) && ids.has(e.target))
      .map((e) => ({ source: e.source, target: e.target, relation: e.relation }));

    const svg = d3.select(el);
    svg.selectAll("*").remove();
    const g = svg.append("g");
    svg.call(d3.zoom<SVGSVGElement, unknown>().scaleExtent([0.3, 4])
      .on("zoom", (e) => g.attr("transform", e.transform.toString())));

    const link = g.append("g").selectAll("line").data(links).join("line")
      .attr("stroke", (d) => claimRelationColor[d.relation as keyof typeof claimRelationColor] || "#b9bfc7")
      .attr("stroke-width", 1.6).attr("stroke-opacity", 0.6);

    const node = g.append("g").selectAll<SVGCircleElement, N>("circle").data(nodes).join("circle")
      .attr("r", (d) => (d.id === selectedId ? 11 : 8))
      .attr("fill", (d) => claimTypeColor[d.claim_type] || "#9aa0b0")
      .attr("stroke", (d) => (d.id === selectedId ? "#1f1e1c"
        : highlightContrib && d.contribution_id === highlightContrib ? "#1f1e1c" : "#fff"))
      .attr("stroke-width", (d) => (d.id === selectedId ? 3
        : highlightContrib && d.contribution_id === highlightContrib ? 2.4 : 1))
      .attr("opacity", (d) => (highlightContrib && d.contribution_id !== highlightContrib && d.id !== selectedId ? 0.35 : 1))
      .style("cursor", "pointer")
      .on("click", (e, d) => { e.stopPropagation(); onSelectClaim?.(d); })
      .call(d3.drag<SVGCircleElement, N>()
        .on("start", (e, d) => { if (!e.active) sim.alphaTarget(0.2).restart(); d.fx = d.x; d.fy = d.y; })
        .on("drag", (e, d) => { d.fx = e.x; d.fy = e.y; })
        .on("end", (e, d) => { if (!e.active) sim.alphaTarget(0); d.fx = null; d.fy = null; }));
    node.append("title").text((d) => d.label);

    const elab = g.append("g").selectAll("text").data(links).join("text")
      .attr("class", "claim-elab").attr("text-anchor", "middle").attr("font-size", 10)
      .attr("fill", (d) => claimRelationColor[d.relation as keyof typeof claimRelationColor] || "#7a8290")
      .text((d) => d.relation);

    const trunc = (s: string, n: number) => (s.length > n ? s.slice(0, n - 1) + "…" : s);
    const lab = g.append("g").selectAll("text").data(nodes).join("text")
      .attr("class", "claim-nlab").attr("dx", 13).attr("dy", 4).attr("font-size", 11)
      .text((d) => trunc(d.label, 48));

    const sim = d3.forceSimulation<N>(nodes)
      .force("link", d3.forceLink<N, L>(links).id((d) => d.id).distance(120).strength(0.35))
      .force("charge", d3.forceManyBody().strength(-320))
      .force("center", d3.forceCenter(width / 2, height / 2))
      .force("collide", d3.forceCollide(18))
      .on("tick", () => {
        link.attr("x1", (d) => (d.source as N).x!).attr("y1", (d) => (d.source as N).y!)
          .attr("x2", (d) => (d.target as N).x!).attr("y2", (d) => (d.target as N).y!);
        node.attr("cx", (d) => d.x!).attr("cy", (d) => d.y!);
        lab.attr("x", (d) => d.x!).attr("y", (d) => d.y!);
        elab.attr("x", (d) => ((d.source as N).x! + (d.target as N).x!) / 2)
          .attr("y", (d) => ((d.source as N).y! + (d.target as N).y!) / 2);
      });
    svg.on("click", () => onSelectClaim?.(null));
    return () => { sim.stop(); };
  }, [graph, highlightContrib, selectedId]);

  if (graph.nodes.length === 0) {
    return <div className="empty">No claims extracted for this paper yet.</div>;
  }
  return (
    <div className="claimgraph">
      <svg ref={svgRef} className="claim-svg" />
      <div className="claim-legend">
        {[...new Set(graph.nodes.map((n) => n.claim_type))].map((t) => (
          <span key={t} className="cl-chip">
            <span className="dot" style={{ background: claimTypeColor[t] || "#9aa0b0" }} />{t}
          </span>
        ))}
      </div>
    </div>
  );
}
