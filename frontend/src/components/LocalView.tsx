import { useMemo } from "react";
import {
  ReactFlow,
  Background,
  Controls,
  MarkerType,
  type Node,
  type Edge,
} from "@xyflow/react";
import type { PaperGraph, ClaimEdge } from "../lib/types";
import { claimTypeColor, claimRelationColor } from "../lib/colors";
import { forceLayout } from "../lib/layout";
import GraphNode, { type GraphNodeData } from "./GraphNode";

const nodeTypes = { prior: GraphNode };

export default function LocalView({
  graph,
  selectedId,
  onSelectNode,
  onSelectEdge,
}: {
  graph: PaperGraph;
  selectedId: string | null;
  onSelectNode: (id: string) => void;
  onSelectEdge?: (e: ClaimEdge) => void;
}) {
  const { nodes, edges } = useMemo(() => {
    const pos = forceLayout(
      graph.nodes.map((n) => ({ id: n.id })),
      graph.edges,
      { width: 1000, height: 720, iterations: 350 },
    );

    const rfNodes: Node<GraphNodeData>[] = graph.nodes.map((n) => ({
      id: n.id,
      type: "prior",
      position: pos[n.id] ?? { x: 0, y: 0 },
      selected: n.id === selectedId,
      data: {
        head: n.claim_type,
        body: n.label,
        meta: `confidence ${n.confidence.toFixed(2)}`,
        color: claimTypeColor[n.claim_type] ?? "#868e96",
      },
    }));

    const rfEdges: Edge[] = graph.edges.map((e) => {
      const color = claimRelationColor[e.relation] ?? "#868e96";
      return {
        id: e.id,
        source: e.source,
        target: e.target,
        label: e.relation,
        animated: e.relation === "contradicts",
        style: { stroke: color, strokeWidth: 1.6 },
        labelStyle: { fill: color, fontSize: 14, fontWeight: 600 },
        labelBgStyle: { fill: "#0e1117", fillOpacity: 0.85 },
        markerEnd: {
          type: MarkerType.ArrowClosed,
          color,
          width: 14,
          height: 14,
        },
      };
    });

    return { nodes: rfNodes, edges: rfEdges };
  }, [graph, selectedId]);

  return (
    <>
      <div className="contrib-strip">
        {graph.contributions.map((c, i) => (
          <div className="contrib-card" key={c.id}>
            <div className="cc-h">Contribution {i + 1}</div>
            <div>{c.problem}</div>
          </div>
        ))}
      </div>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        onNodeClick={(_, node) => onSelectNode(node.id)}
        onEdgeClick={(_, ed) => {
          const orig = graph.edges.find((x) => x.id === ed.id);
          if (orig) onSelectEdge?.(orig);
        }}
        fitView
        fitViewOptions={{ padding: 0.2 }}
        minZoom={0.15}
        proOptions={{ hideAttribution: true }}
      >
        <Background color="#1c2330" gap={22} />
        <Controls showInteractive={false} />
      </ReactFlow>
    </>
  );
}
