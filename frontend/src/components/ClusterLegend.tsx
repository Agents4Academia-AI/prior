import type { ClusterLegend as Cluster } from "../lib/api";

export default function ClusterLegend({
  legend, focusComm, onPick,
}: {
  legend: Cluster[];
  focusComm: number | null;
  onPick: (id: number) => void;
}) {
  return (
    <div className="legend cluster-legend">
      <div className="lg-title">Clusters {focusComm != null && <span className="lg-clear">· click to clear</span>}</div>
      {legend.filter((l) => l.id >= 0).map((l) => (
        <button
          key={l.id}
          className={`lg-row${focusComm === l.id ? " on" : ""}${focusComm != null && focusComm !== l.id ? " dim" : ""}`}
          onClick={() => onPick(l.id)}
        >
          <span className="chip" style={{ background: l.color }} />
          <span className="lg-label">{l.label}</span>
          <span className="lg-n">{l.n}</span>
        </button>
      ))}
    </div>
  );
}
