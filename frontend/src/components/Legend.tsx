import { relationColor, claimTypeColor } from "../lib/colors";

export default function Legend({
  mode,
  activeRelation,
  onPickRelation,
}: {
  mode: "global" | "local";
  activeRelation?: string | null;
  onPickRelation?: (rel: string | null) => void;
}) {
  if (mode === "global") {
    const clickable = !!onPickRelation;
    return (
      <div className="legend">
        <div className="lg-title">
          Edge relation {clickable && <span className="lg-hint">(click to filter)</span>}
        </div>
        {clickable && (
          <button
            className={`lg-row lg-btn${!activeRelation ? " on" : ""}`}
            onClick={() => onPickRelation?.(null)}
          >
            <span className="swatch" style={{ borderColor: "#9aa7b4" }} />
            <span>all relations</span>
          </button>
        )}
        {Object.entries(relationColor).map(([rel, c]) =>
          clickable ? (
            <button
              key={rel}
              className={`lg-row lg-btn${activeRelation === rel ? " on" : ""}`}
              onClick={() => onPickRelation?.(activeRelation === rel ? null : rel)}
            >
              <span className="swatch" style={{ borderColor: c }} />
              <span>{rel}</span>
            </button>
          ) : (
            <div className="lg-row" key={rel}>
              <span className="swatch" style={{ borderColor: c }} />
              <span>{rel}</span>
            </div>
          ),
        )}
        <div className="lg-title" style={{ marginTop: 8 }}>
          Provenance
        </div>
        <div className="lg-row">
          <span className="swatch" style={{ borderColor: "#9aa7b4" }} />
          <span>both — citation-backed</span>
        </div>
        <div className="lg-row">
          <span
            className="swatch dashed"
            style={{ borderColor: "#9aa7b4" }}
          />
          <span>text — uncited parallel work</span>
        </div>
      </div>
    );
  }
  return (
    <div className="legend">
      <div className="lg-title">Claim type</div>
      {Object.entries(claimTypeColor).map(([t, c]) => (
        <div className="lg-row" key={t}>
          <span className="chip" style={{ background: c }} />
          <span>{t}</span>
        </div>
      ))}
    </div>
  );
}
