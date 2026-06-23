import { useEffect, useState } from "react";
import { api, type EvalResults, type EvalMetric } from "../lib/api";

const PCT = (v: number) => `${Math.round(v * 100)}%`;

function fmt(m: EvalMetric): string {
  if (m.value === null) return "—";
  return m.unit === "rate" ? PCT(m.value) : String(m.value);
}

function Bars({ data, title }: { data: Record<string, number>; title: string }) {
  const entries = Object.entries(data).sort((a, b) => b[1] - a[1]);
  const max = Math.max(1, ...entries.map(([, n]) => n));
  return (
    <div className="eval-chart">
      <h4>{title}</h4>
      {entries.length === 0 && <div className="muted">none</div>}
      {entries.map(([k, n]) => (
        <div className="bar-row" key={k}>
          <span className="bar-label">{k}</span>
          <span className="bar-track">
            <span className="bar-fill" style={{ width: `${(n / max) * 100}%` }} />
          </span>
          <span className="bar-val">{n}</span>
        </div>
      ))}
    </div>
  );
}

export default function EvalView() {
  const [data, setData] = useState<EvalResults | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    api.eval().then(setData).catch((e) => setErr(String(e)));
  }, []);

  if (err) return <div className="center-fill"><div className="err">{err}</div></div>;
  if (!data) return <div className="center-fill"><span className="spinner" />Loading eval…</div>;

  const byGroup = (g: string) => data.metrics.filter((m) => m.group === g);
  const gateStatus = (g: string) => {
    const ms = byGroup(g).filter((m) => m.value !== null);
    if (ms.length === 0) return "pending";
    return ms.every((m) => m.status === "pass") ? "pass" : "warn";
  };
  const d = data.distributions;
  const prov = d.provenance || {};
  const textEdges = prov.text || 0;
  const bothEdges = prov.both || 0;

  return (
    <div className="eval">
      <div className="eval-head">
        <h2>Evaluation scorecard</h2>
        <div className="muted">
          {data.graph.papers} papers · {data.graph.contributions} contributions ·{" "}
          {data.graph.claims} claims · {data.graph.global_edges} global edges
        </div>
        {data.note && <div className="eval-note">{data.note}</div>}
      </div>

      {/* the three gates */}
      <div className="gates">
        {Object.entries(data.gates).map(([g, label]) => (
          <div className={`gate ${gateStatus(g)}`} key={g}>
            <div className="gate-name">{label}</div>
            <div className="gate-status">{gateStatus(g).toUpperCase()}</div>
          </div>
        ))}
      </div>

      {/* scorecard grouped by gate */}
      {Object.entries(data.gates).map(([g, label]) => (
        <div className="eval-group" key={g}>
          <h3>{label}</h3>
          <table className="scorecard">
            <thead>
              <tr><th>Metric</th><th>Value</th><th>Target</th><th>Status</th><th>Kind</th></tr>
            </thead>
            <tbody>
              {byGroup(g).map((m) => (
                <tr key={m.id}>
                  <td>
                    <div className="m-name">{m.name}</div>
                    <div className="m-detail">{m.detail}</div>
                  </td>
                  <td className="m-val">{fmt(m)}</td>
                  <td className="muted">
                    {m.higher_better ? "≥" : "≤"} {m.unit === "rate" ? PCT(m.threshold) : m.threshold}
                  </td>
                  <td><span className={`pill ${m.status}`}>{m.status}</span></td>
                  <td className="muted">{m.kind}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ))}

      {/* the value-add headline number */}
      <div className="eval-callout">
        <b>{textEdges}</b> uncited-parallel-work edges (text-inferred) vs{" "}
        <b>{bothEdges}</b> citation-backed — links citation-only tools can't find.
      </div>

      {/* distributions */}
      <div className="eval-charts">
        <Bars data={d.provenance} title="Global-edge provenance" />
        <Bars data={d.global_relations} title="Global relations" />
        <Bars data={d.local_relations} title="Local relations" />
        <Bars data={d.claim_types} title="Claim types" />
      </div>
    </div>
  );
}
