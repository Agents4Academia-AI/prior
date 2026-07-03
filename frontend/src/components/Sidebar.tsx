import type { Summary, Paper } from "../lib/types";
import type { WhoAmI, CollectionInfo } from "../lib/api";
import SignIn from "./SignIn";
import AddPaper from "./AddPaper";

export default function Sidebar({
  summary,
  papers,
  collections,
  collection,
  onSwitchCollection,
  who,
  onIdentityChange,
  onIngested,
}: {
  summary: Summary | null;
  papers: Paper[];
  collections: CollectionInfo[];
  collection: string;
  onSwitchCollection: (name: string) => void;
  who: WhoAmI | null;
  onIdentityChange: () => void;
  onIngested: () => void;
}) {
  return (
    <div className="panel sidebar">
      <div className="brand">
        <h1>Prior</h1>
        <div className="tag">Literature knowledge graph</div>
        {summary && <div className="topic">{summary.topic}</div>}
      </div>

      {collections.length > 0 && (
        <div className="collection-switch">
          <label>Collection</label>
          <select value={collection} onChange={(e) => onSwitchCollection(e.target.value)}>
            {collections.map((c) => (
              <option key={c.name} value={c.name}>
                {c.name} ({c.papers})
              </option>
            ))}
          </select>
        </div>
      )}

      <SignIn who={who} onChange={onIdentityChange} />

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

      <div className="papers-head">
        <span className="section-title">Papers ({papers.length})</span>
        <AddPaper onIngested={onIngested} collection={collection} />
      </div>
      <div className="papers">
        {papers.map((p) => (
          <div key={p.id} className="paper-item static">
            <span className="pt">{p.title}</span>
            <span className="pm">
              {p.cite}
              <span className="dot">·</span>
              {p.n_contributions} contrib
            </span>
          </div>
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
