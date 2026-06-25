import type { WhoAmI, CollectionInfo } from "../lib/api";
import SignIn from "./SignIn";

type NavMode = "graph" | "papers" | "eval" | "report";
const NAV: { mode: NavMode; icon: string; label: string }[] = [
  { mode: "graph", icon: "🕸", label: "Graph" },
  { mode: "papers", icon: "📄", label: "Papers" },
  { mode: "eval", icon: "📊", label: "Eval" },
  { mode: "report", icon: "📋", label: "Report" },
];

export default function NavRail({
  mode, onNavigate, open, onToggle,
  collections, collection, onSwitchCollection,
  who, onIdentityChange, onAskPrior,
}: {
  mode: string;
  onNavigate: (m: NavMode) => void;
  open: boolean;
  onToggle: () => void;
  collections: CollectionInfo[];
  collection: string;
  onSwitchCollection: (name: string) => void;
  who: WhoAmI | null;
  onIdentityChange: () => void;
  onAskPrior?: () => void;
}) {
  return (
    <div className={`navrail${open ? " open" : ""}`}>
      <div className="nr-top">
        <button className="nr-brand" onClick={onToggle} title={open ? "Collapse" : "Expand"}>
          <img className="nr-logo" src="/icon.svg" alt="Prior" width={28} height={28} />
          {open && <span className="nr-brandname">Prior</span>}
        </button>

        <nav className="nr-nav">
          {who?.signed_in && onAskPrior && (
            <button className="nr-item nr-ask" onClick={onAskPrior} title="Ask Prior">
              <span className="nr-icon">💬</span>
              {open && <span className="nr-label">Ask Prior</span>}
            </button>
          )}
          {NAV.map((n) => (
            <button
              key={n.mode}
              className={`nr-item${mode === n.mode ? " on" : ""}`}
              onClick={() => onNavigate(n.mode)}
              title={n.label}
            >
              <span className="nr-icon">{n.icon}</span>
              {open && <span className="nr-label">{n.label}</span>}
            </button>
          ))}
        </nav>
      </div>

      <div className="nr-bottom">
        {open && collections.length > 0 && (
          <div className="nr-collection">
            <label>Collection</label>
            <select value={collection} onChange={(e) => onSwitchCollection(e.target.value)}>
              {collections.map((c) => (
                <option key={c.name} value={c.name}>{c.name} ({c.papers})</option>
              ))}
            </select>
          </div>
        )}
        {open ? (
          <SignIn who={who} onChange={onIdentityChange} />
        ) : (
          <button className="nr-item" title={who?.signed_in ? who.user ?? "account" : "Sign in"}
                  onClick={onToggle}>
            <span className="nr-icon">{who?.signed_in ? "🟢" : "👤"}</span>
          </button>
        )}
      </div>
    </div>
  );
}
