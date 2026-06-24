import type { RContrib } from "../lib/api";
import type { EdgePick } from "./GraphD3";

export default function ContribDetails({
  contrib, edge, relColor,
}: {
  contrib: RContrib | null;
  edge: EdgePick | null;
  relColor: Record<string, string>;
}) {
  if (edge) {
    return (
      <div className="cd">
        <div className="cd-head" style={{ color: relColor[edge.rel] || "var(--text)" }}>
          {edge.rel}
        </div>
        <Field k="From" v={edge.source} mono />
        <Field k="To" v={edge.target} mono />
        {edge.tier && <Field k="Agreement" v={edge.tier} />}
        {edge.ev && <Field k="Evidence" v={edge.ev} />}
        <div className="muted hint">Use the <b>Annotate</b> tab to verify this relation.</div>
      </div>
    );
  }
  if (contrib) {
    return (
      <div className="cd">
        <div className="cd-kind">{contrib.kind || "contribution"}</div>
        <div className="cd-stmt">{contrib.stmt}</div>
        {contrib.quote && <div className="cd-quote">“{contrib.quote}”</div>}
        <Field k="Paper" v={contrib.cite} />
        <div className="muted hint">Use the <b>Annotate</b> tab to verify this contribution.</div>
      </div>
    );
  }
  return <div className="empty">Click a node or edge in the graph to see its details.</div>;
}

function Field({ k, v, mono }: { k: string; v: string; mono?: boolean }) {
  return (
    <div className="field">
      <div className="k">{k}</div>
      <div className="v" style={mono ? { fontFamily: "var(--mono)", fontSize: 12 } : undefined}>{v}</div>
    </div>
  );
}
