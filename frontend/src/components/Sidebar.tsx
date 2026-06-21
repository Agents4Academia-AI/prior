import type { Summary, Paper } from "../lib/types";

export default function Sidebar({
  summary,
  papers,
  selectedPaperId,
  onSelectPaper,
}: {
  summary: Summary | null;
  papers: Paper[];
  selectedPaperId: string | null;
  onSelectPaper: (p: Paper) => void;
}) {
  return (
    <div className="panel sidebar">
      <div className="brand">
        <h1>Prior</h1>
        <div className="tag">Literature knowledge graph</div>
        {summary && <div className="topic">{summary.topic}</div>}
      </div>

      {summary && (
        <div className="stats">
          <Stat n={summary.papers} l="Papers" />
          <Stat n={summary.contributions} l="Contribs" />
          <Stat n={summary.claims} l="Claims" />
          <Stat n={summary.global_edges} l="Global ↔" />
          <Stat n={summary.local_edges} l="Local ↔" />
          <Stat n={summary.citations} l="Citations" />
        </div>
      )}

      <div className="section-title">Papers ({papers.length})</div>
      <div className="papers">
        {papers.map((p) => (
          <button
            key={p.id}
            className={`paper-item${
              p.id === selectedPaperId ? " active" : ""
            }`}
            onClick={() => onSelectPaper(p)}
          >
            <span className="pt">{p.title}</span>
            <span className="pm">
              {p.cite}
              <span className="dot">·</span>
              {p.n_contributions} contrib
              <span className="dot">·</span>
              {p.n_claims} claims
            </span>
          </button>
        ))}
      </div>
    </div>
  );
}

function Stat({ n, l }: { n: number; l: string }) {
  return (
    <div className="stat">
      <div className="num">{n}</div>
      <div className="lbl">{l}</div>
    </div>
  );
}
