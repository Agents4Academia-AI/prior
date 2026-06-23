import { useMemo } from "react";
import {
  ReactFlow,
  Background,
  Controls,
  MarkerType,
  type Node,
  type Edge,
} from "@xyflow/react";
import type { GlobalGraph } from "../lib/types";
import { relationColor } from "../lib/colors";
import { forceLayout } from "../lib/layout";
import GraphNode, { type GraphNodeData } from "./GraphNode";

const nodeTypes = { prior: GraphNode };

export default function GlobalView({
  graph,
  selectedId,
  onSelectNode,
}: {
  graph: GlobalGraph;
  selectedId: string | null;
  onSelectNode: (id: string) => void;
}) {
  const { nodes, edges } = useMemo(() => {
    const pos = forceLayout(
      graph.nodes.map((n) => ({ id: n.id })),
      graph.edges,
      { width: 1100, height: 760, iterations: 350 },
    );

    const rfNodes: Node<GraphNodeData>[] = graph.nodes.map((n) => ({
      id: n.id,
      type: "prior",
      position: pos[n.id] ?? { x: 0, y: 0 },
      selected: n.id === selectedId,
      data: {
        head: n.paper,
        body: n.label,
        meta: `${n.year}`,
        color: "#6ea8fe",
      },
    }));

    const rfEdges: Edge[] = graph.edges.map((e) => {
      const color = relationColor[e.relation] ?? "#868e96";
      const dashed = e.provenance === "text";
      return {
        id: e.id,
        source: e.source,
        target: e.target,
        label: e.relation,
        animated: e.relation === "contradicts",
        style: {
          stroke: color,
          strokeWidth: 1.6,
          strokeDasharray: dashed ? "5 4" : undefined,
        },
        labelStyle: { fill: color, fontSize: 9, fontWeight: 600 },
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
    <ReactFlow
      nodes={nodes}
      edges={edges}
      nodeTypes={nodeTypes}
      onNodeClick={(_, node) => onSelectNode(node.id)}
      fitView
      fitViewOptions={{ padding: 0.18 }}
      minZoom={0.15}
      proOptions={{ hideAttribution: true }}
    >
      <Background color="#1c2330" gap={22} />
      <Controls showInteractive={false} />
    </ReactFlow>
  );
}
