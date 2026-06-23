import { Handle, Position } from "@xyflow/react";

export interface GraphNodeData {
  head: string;
  body: string;
  meta?: string;
  color: string;
  [key: string]: unknown;
}

export default function GraphNode({
  data,
  selected,
}: {
  data: GraphNodeData;
  selected?: boolean;
}) {
  return (
    <div
      className={`rf-node${selected ? " selected" : ""}`}
      style={{ borderLeft: `4px solid ${data.color}` }}
    >
      <Handle type="target" position={Position.Top} />
      <div className="rf-head" style={{ color: data.color }}>
        {data.head}
      </div>
      <div className="rf-body">{data.body}</div>
      {data.meta && <div className="rf-meta">{data.meta}</div>}
      <Handle type="source" position={Position.Bottom} />
    </div>
  );
}
