import { useState } from "react";
import type { Summary, Paper } from "../lib/types";
import AddPaper from "./AddPaper";
import PaperLink from "./PaperLink";

function Stat({ n, l }: { n: number; l: string }) {
  return <div className="stat"><div className="num">{n}</div><div className="lbl">{l}</div></div>;
}

export default function PapersView({
  summary, papers, collection, onIngested,
}: {
  summary: Summary | null;
  papers: Paper[];
  collection: string;
  onIngested: () => void;
}) {
  const [q, setQ] = useState("");
  const needle = q.trim().toLowerCase();
  const shown = needle
    ? papers.filter((p) => p.title.toLowerCase().includes(needle) || p.cite.toLowerCase().includes(needle))
    : papers;

  return (
    <div className="papers-view">
      <div className="pv-head">
        <div>
          <h2>Papers</h2>
          {summary?.topic && <div className="muted">{summary.topic}</div>}
        </div>
        <AddPaper onIngested={onIngested} collection={collection} />
      </div>

      {summary && (
        <div className="stats pv-stats">
          <Stat n={summary.papers} l="Papers" />
          <Stat n={summary.contributions} l="Contribs" />
          <Stat n={summary.claims} l="Claims" />
          <Stat n={summary.global_edges} l="Global ↔" />
          <Stat n={summary.local_edges} l="Local ↔" />
          {summary.citations > 0 && <Stat n={summary.citations} l="Citations" />}
        </div>
      )}

      <div className="pv-toolbar">
        <input className="pv-search" placeholder="Filter papers…" value={q}
               onChange={(e) => setQ(e.target.value)} />
        <span className="muted">{shown.length} of {papers.length}</span>
      </div>

      <div className="pv-list">
        {shown.map((p) => (
          <div key={p.id} className="pv-item">
            <PaperLink paper={p} className="pv-title">{p.title}</PaperLink>
            <div className="pv-meta">
              {p.cite}<span className="dot">·</span>{p.year}
              <span className="dot">·</span>{p.n_contributions} contrib
              <span className="dot">·</span>{p.n_claims} claims
            </div>
          </div>
        ))}
        {shown.length === 0 && <div className="muted" style={{ padding: 12 }}>no matches</div>}
      </div>
    </div>
  );
}
