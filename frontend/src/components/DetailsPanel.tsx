import type { ContributionDetail, ClaimNode, PaperGraph } from "../lib/types";
import { relationColor, claimTypeColor } from "../lib/colors";

export default function DetailsPanel({
  contribution,
  contribLoading,
  contribError,
  claim,
  paperGraph,
}: {
  contribution: ContributionDetail | null;
  contribLoading: boolean;
  contribError: string | null;
  claim: ClaimNode | null;
  paperGraph: PaperGraph | null;
}) {
  if (contribLoading) {
    return (
      <div className="loading">
        <span className="spinner" /> Loading contribution…
      </div>
    );
  }
  if (contribError) {
    return <div className="err">{contribError}</div>;
  }

  // A claim was selected in the local view.
  if (claim) {
    return (
      <div>
        <Field
          k="Claim type"
          v={
            <span
              className="rel-pill"
              style={{ background: claimTypeColor[claim.claim_type] }}
            >
              {claim.claim_type}
            </span>
          }
        />
        <Field k="Claim" v={claim.label} />
        <Field k="Confidence" v={claim.confidence.toFixed(2)} />
        {claim.evidence && <Field k="Evidence" v={claim.evidence} />}
        {paperGraph && (
          <Field
            k="From paper"
            v={<span className="cite">{paperGraph.paper.cite}</span>}
          />
        )}
      </div>
    );
  }

  // A contribution node was selected in the global view.
  if (contribution) {
    return (
      <div>
        <Field k="Problem" v={contribution.problem} />
        <Field k="Method" v={contribution.method} />
        <Field k="Result" v={contribution.result} />

        {contribution.claims.length > 0 && (
          <div className="field">
            <div className="k">Claims ({contribution.claims.length})</div>
            <ul className="list-tight">
              {contribution.claims.map((c) => (
                <li key={c.id}>{c.text}</li>
              ))}
            </ul>
          </div>
        )}

        <div className="field">
          <div className="k">
            Global neighbours ({contribution.neighbours.length})
          </div>
          {contribution.neighbours.length === 0 && (
            <div className="muted">None.</div>
          )}
          {contribution.neighbours.map((nb, i) => (
            <div className="neighbour" key={i}>
              <div className="nh">
                <span
                  className="rel-pill"
                  style={{
                    background: relationColor[nb.relation] ?? "#868e96",
                  }}
                >
                  {nb.relation}
                </span>
                <span className="prov">
                  {nb.provenance === "both"
                    ? "citation-backed"
                    : "uncited / text"}
                </span>
                <span className="muted">conf {nb.confidence.toFixed(2)}</span>
              </div>
              <div className="nid">
                {nb.src === contribution.id ? "→ " : "← "}
                {nb.src === contribution.id ? nb.dst : nb.src}
              </div>
              {nb.evidence && <div className="ev">{nb.evidence}</div>}
            </div>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="empty">
      Select a contribution node (global view) or a claim node (local view) to
      see its details.
    </div>
  );
}

function Field({ k, v }: { k: string; v: React.ReactNode }) {
  return (
    <div className="field">
      <div className="k">{k}</div>
      <div className="v">{v}</div>
    </div>
  );
}
