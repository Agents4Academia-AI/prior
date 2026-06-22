import { relationColor, claimTypeColor } from "../lib/colors";

export default function Legend({ mode }: { mode: "global" | "local" }) {
  if (mode === "global") {
    return (
      <div className="legend">
        <div className="lg-title">Edge relation</div>
        {Object.entries(relationColor).map(([rel, c]) => (
          <div className="lg-row" key={rel}>
            <span className="swatch" style={{ borderColor: c }} />
            <span>{rel}</span>
          </div>
        ))}
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
