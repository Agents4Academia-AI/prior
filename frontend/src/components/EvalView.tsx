import { useEffect, useState } from "react";
import { api, type EvalResults, type CalibDim, type EvalJudges } from "../lib/api";

const PCT = (v: number | null) => (v === null ? "-" : `${Math.round(v * 100)}%`);
const NUM = (v: number | null) => (v === null ? "-" : v.toFixed(2));
const KIND_LABEL: Record<string, string> = {
  contribution: "Contributions", edge: "Relations (edges)", claim: "Claims",
};

// Per-judge correctness: one column per annotator (model judge or human).
function JudgesTable({ j }: { j: EvalJudges }) {
  const labels = j.labels;
  if (!labels.length) return <div className="muted">No judges have run yet.</div>;
  return (
    <table className="ev-table">
      <thead>
        <tr><th>Dimension</th>{labels.map((l) => <th key={l}>{l}<div className="th-sub">% correct</div></th>)}</tr>
      </thead>
      <tbody>
        {j.dimensions.map((d) => (
          <tr key={d.kind}>
            <td className="ev-dim"><div className="ev-dim-name">{KIND_LABEL[d.kind] ?? d.kind}</div></td>
            {labels.map((l) => {
              const r = d.rates[l];
              return (
                <td className="ev-cell" key={l}>
                  <span className="ev-pct">{r ? PCT(r.correct) : "-"}</span>
                  <span className="ev-n">{r ? `n=${r.n}` : "no labels"}</span>
                </td>
              );
            })}
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function Agreement({ j }: { j: EvalJudges }) {
  if (!j.agreement.length) return null;
  return (
    <div className="eval-section">
      <h3>Cross-judge agreement</h3>
      <p className="muted">On items both judges labelled, the share where their verdicts match. Low agreement flags items worth a human look.</p>
      <table className="mv-table" style={{ maxWidth: 520 }}>
        <thead><tr><th>Judge A</th><th>Judge B</th><th>Co-labelled</th><th>Agree</th></tr></thead>
        <tbody>
          {j.agreement.map((a, i) => (
            <tr key={i}><td>{a.a}</td><td>{a.b}</td><td>{a.n}</td><td>{PCT(a.rate)}</td></tr>
          ))}
        </tbody>
      </table>
    </div>
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

// ── Calibration charts (inline SVG; x,y in [0,1]; viewBox scales to fill card) ───
const W = 380, H = 300, P = 50;
const sx = (v: number) => P + v * (W - 2 * P);
const sy = (v: number) => H - P - v * (H - 2 * P);
const poly = (pts: [number, number][]) =>
  pts.map(([x, y]) => `${sx(x).toFixed(1)},${sy(y).toFixed(1)}`).join(" ");
const TICKS = [0, 0.25, 0.5, 0.75, 1];
const TLABEL = (v: number) => (v === 0 ? "0" : v === 1 ? "1" : v.toFixed(2).replace(/0$/, ""));

function Axes({ xlabel, ylabel }: { xlabel: string; ylabel: string }) {
  return (
    <>
      {/* gridlines */}
      {TICKS.map((v) => (
        <g key={`g${v}`}>
          <line x1={sx(v)} y1={sy(0)} x2={sx(v)} y2={sy(1)} stroke="#2c2c34" strokeWidth={0.6} />
          <line x1={sx(0)} y1={sy(v)} x2={sx(1)} y2={sy(v)} stroke="#2c2c34" strokeWidth={0.6} />
        </g>
      ))}
      <rect x={P} y={P} width={W - 2 * P} height={H - 2 * P} fill="none" stroke="#3a3a44" strokeWidth={1} />
      {/* ticks + numbers */}
      {TICKS.map((v) => (
        <g key={`t${v}`}>
          <line x1={sx(v)} y1={H - P} x2={sx(v)} y2={H - P + 4} stroke="#6b6b78" strokeWidth={1} />
          <text x={sx(v)} y={H - P + 15} textAnchor="middle" fontSize={10} fill="#9aa0b0">{TLABEL(v)}</text>
          <line x1={P - 4} y1={sy(v)} x2={P} y2={sy(v)} stroke="#6b6b78" strokeWidth={1} />
          <text x={P - 7} y={sy(v) + 3.5} textAnchor="end" fontSize={10} fill="#9aa0b0">{TLABEL(v)}</text>
        </g>
      ))}
      <text x={(P + (W - P)) / 2} y={H - 6} textAnchor="middle" fontSize={11} fill="#c2c6d2">{xlabel}</text>
      <text x={12} y={(P + (H - P)) / 2} textAnchor="middle" fontSize={11} fill="#c2c6d2"
            transform={`rotate(-90 12 ${(P + (H - P)) / 2})`}>{ylabel}</text>
    </>
  );
}

function ReliabilityChart({ d }: { d: CalibDim }) {
  const pts = d.reliability.map((b) => [b.score, b.acc] as [number, number]);
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="calib-svg" role="img" aria-label="reliability curve">
      <Axes xlabel="score" ylabel="accuracy (judge faithful)" />
      {/* perfect-calibration diagonal */}
      <polyline points={poly([[0, 0], [1, 1]])} fill="none" stroke="#5a5a66" strokeWidth={1} strokeDasharray="4 3" />
      <polyline points={poly(pts)} fill="none" stroke="#5b8fb0" strokeWidth={2} />
      {d.reliability.map((b, i) => (
        <circle key={i} cx={sx(b.score)} cy={sy(b.acc)} r={2.5 + Math.min(5, b.n / 60)} fill="#5b8fb0" />
      ))}
    </svg>
  );
}

function ThresholdChart({ d }: { d: CalibDim }) {
  const acc = d.thresholds.filter((t) => t.accuracy !== null).map((t) => [t.t, t.accuracy as number] as [number, number]);
  const cov = d.thresholds.filter((t) => t.coverage !== null).map((t) => [t.t, t.coverage as number] as [number, number]);
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="calib-svg" role="img" aria-label="accuracy vs threshold">
      <Axes xlabel="threshold ≥ t" ylabel="rate" />
      <polyline points={poly(cov)} fill="none" stroke="#6b6b78" strokeWidth={1.4} strokeDasharray="3 2" />
      <polyline points={poly(acc)} fill="none" stroke="#7bbf6a" strokeWidth={2} />
      {acc.map(([x, y], i) => <circle key={i} cx={sx(x)} cy={sy(y)} r={2.5} fill="#7bbf6a" />)}
    </svg>
  );
}

function CalibCard({ d }: { d: CalibDim }) {
  const title = `${KIND_LABEL[d.kind] ?? d.kind} · ${d.signal}`;
  if (!d.n) return (
    <div className="calib-card">
      <h4>{title}</h4>
      <div className="muted">
        No <code>{d.signal}</code> score is stored for {KIND_LABEL[d.kind] ?? d.kind} in this
        collection, so calibration cannot be computed. (core-v0.2 was loaded from a prebuilt
        bundle whose contributions carry no confidence.) Correctness is still shown in the table above.
      </div>
    </div>
  );
  return (
    <div className="calib-card">
      <div className="calib-card-head">
        <h4>{title}</h4>
        <div className="calib-metrics">
          AUC {NUM(d.auc)} · ECE {NUM(d.ece)} · base acc {PCT(d.accuracy)} · n={d.n}
        </div>
      </div>
      <div className="calib-charts">
        <figure className="calib-cell">
          <ReliabilityChart d={d} />
          <figcaption className="muted">reliability (curve vs dashed diagonal)</figcaption>
        </figure>
        <figure className="calib-cell">
          <ThresholdChart d={d} />
          <figcaption className="muted">accuracy (green) · coverage (grey dashed)</figcaption>
        </figure>
      </div>
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

  return (
    <div className="eval">
      <div className="eval-head">
        <h2>Evaluation</h2>
        <p className="muted">Correctness per judge (each model or human annotator is its own column). Run more judges with <code>prior selfeval --model … --judge …</code>.</p>
      </div>

      <JudgesTable j={data.judges} />
      <Agreement j={data.judges} />

      {data.calibration && (
        <div className="eval-section">
          <h3>Calibration, does the stored score predict the judge's verdict?</h3>
          <p className="muted">{data.calibration.note}</p>
          <div className="calib-grid">
            {data.calibration.dimensions.map((d) => <CalibCard key={`${d.kind}/${d.signal}`} d={d} />)}
          </div>
        </div>
      )}

      <div className="eval-grid">
        <Bars data={data.distributions?.global_relations} title="Relation types" />
        <Bars data={data.distributions?.claim_types} title="Claim types" />
      </div>
    </div>
  );
}
