import { useEffect, useState } from "react";
import { api, type EvalResults, type EvalRate, type EvalDim } from "../lib/api";

const PCT = (v: number | null) => (v === null ? "—" : `${Math.round(v * 100)}%`);
const KIND_LABEL: Record<string, string> = {
  contribution: "Contributions", edge: "Relations (edges)", claim: "Claims",
};

function Cell({ r, accent }: { r: EvalRate; accent?: boolean }) {
  return (
    <td className={`ev-cell${accent ? " accent" : ""}`}>
      <span className="ev-pct">{PCT(r.correct)}</span>
      <span className="ev-n">{r.n ? `n=${r.n}` : "no labels"}</span>
    </td>
  );
}

function DimRow({ d }: { d: EvalDim }) {
  return (
    <tr>
      <td className="ev-dim">
        <span className={`gate ${d.gate}`}>{d.gate}</span>
        <div>
          <div className="ev-dim-name">{KIND_LABEL[d.kind] ?? d.kind}</div>
          <div className="ev-dim-gate">{d.gate_label} · target {PCT(d.threshold)}</div>
        </div>
      </td>
      <Cell r={d.self_eval} />
      <Cell r={d.human} />
      <Cell r={d.aggregated} accent />
      <td className="ev-cell">
        <span className="ev-pct">{PCT(d.agreement.rate)}</span>
        <span className="ev-n">{d.agreement.n ? `n=${d.agreement.n}` : "—"}</span>
      </td>
    </tr>
  );
}

function Bars({ data, title }: { data: Record<string, number>; title: string }) {
  const entries = Object.entries(data || {}).sort((a, b) => b[1] - a[1]);
  const max = Math.max(1, ...entries.map(([, n]) => n));
  return (
    <div className="eval-chart">
      <h4>{title}</h4>
      {entries.length === 0 && <div className="muted">none</div>}
      {entries.map(([k, n]) => (
        <div className="bar-row" key={k}>
          <span className="bar-label">{k}</span>
          <span className="bar-track"><span className="bar-fill" style={{ width: `${(n / max) * 100}%` }} /></span>
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
  if (!data) return <div className="center-fill"><span className="spinner" /> Loading eval…</div>;

  const sc = data.scorecard;
  return (
    <div className="eval">
      <div className="eval-head">
        <h2>Evaluation</h2>
        <p className="muted">{sc.note}</p>
      </div>

      <table className="ev-table">
        <thead>
          <tr>
            <th>Dimension</th>
            <th>Self-eval<div className="th-sub">Claude</div></th>
            <th>Human<div className="th-sub">annotators</div></th>
            <th className="accent">Aggregated<div className="th-sub">human ∪ Claude</div></th>
            <th>Judge↔human<div className="th-sub">agreement</div></th>
          </tr>
        </thead>
        <tbody>
          {sc.dimensions.map((d) => <DimRow key={d.kind} d={d} />)}
        </tbody>
      </table>

      <div className="eval-grid">
        <Bars data={data.distributions?.global_relations} title="Relation types" />
        <Bars data={data.distributions?.claim_types} title="Claim types" />
      </div>
    </div>
  );
}
