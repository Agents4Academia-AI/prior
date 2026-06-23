import { useEffect, useState } from "react";
import { api, type AnnotationRow } from "../lib/api";

export type AnnotationTarget = {
  kind: "claim" | "contribution" | "edge";
  key: string;
  heading: string;
  fields: { label: string; value: string }[];
  source?: string;
};

const FAITHFUL = [
  { v: "correct", l: "Correct" },
  { v: "incorrect", l: "Incorrect" },
  { v: "unsure", l: "Unsure" },
];

const ISSUES: Record<string, { v: string; l: string }[]> = {
  contribution: [
    { v: "problem", l: "problem wrong" },
    { v: "method", l: "method wrong" },
    { v: "result", l: "result wrong" },
    { v: "not_contribution", l: "not a real contribution" },
    { v: "hallucinated", l: "not stated in the paper" },
  ],
  claim: [
    { v: "unfaithful", l: "not faithful to the source" },
    { v: "wrong_evidence", l: "evidence doesn’t support it" },
    { v: "wrong_type", l: "wrong claim type" },
    { v: "not_atomic", l: "not atomic / self-contained" },
  ],
  edge: [
    { v: "wrong_type", l: "wrong relation type" },
    { v: "reversed", l: "direction reversed" },
    { v: "no_relation", l: "no real relation" },
  ],
};

const SOUNDNESS = [
  { v: "sound", l: "Sound / plausible" },
  { v: "doubtful", l: "Doubtful" },
  { v: "implausible", l: "Implausible" },
  { v: "contested", l: "Contested" },
  { v: "na", l: "N/A" },
];

export default function AnnotatePanel({
  target,
  signedIn,
  onAnnotated,
}: {
  target: AnnotationTarget | null;
  signedIn: boolean;
  onAnnotated: () => void;
}) {
  const [faithful, setFaithful] = useState("");
  const [issues, setIssues] = useState<Set<string>>(new Set());
  const [soundness, setSoundness] = useState("");
  const [note, setNote] = useState("");
  const [rows, setRows] = useState<AnnotationRow[]>([]);
  const [busy, setBusy] = useState(false);
  const [saved, setSaved] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    setFaithful(""); setIssues(new Set()); setSoundness(""); setNote("");
    setSaved(false); setErr(null); setRows([]);
    if (!target || !signedIn) return;
    api.annotations(target.key).then((r) => {
      setRows(r);
      const me = r[0]; // own is always first/returned
      if (me) {
        setFaithful(me.faithful ?? "");
        setIssues(new Set(me.issues ?? []));
        setSoundness(me.soundness ?? "");
        setNote(me.note ?? "");
      }
    }).catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [target?.key, signedIn]);

  if (!target) {
    return <div className="empty">Select a contribution, claim, or edge (click a node or edge in the graph) to annotate it.</div>;
  }
  if (!signedIn) {
    return <div className="empty">Sign in (top-left) to annotate.</div>;
  }

  const toggleIssue = (v: string) => {
    const next = new Set(issues);
    next.has(v) ? next.delete(v) : next.add(v);
    setIssues(next);
  };

  const save = async () => {
    if (!faithful) { setErr("Pick a faithfulness verdict (A) first."); return; }
    setBusy(true); setErr(null);
    try {
      await api.annotate({
        target_kind: target.kind, target_key: target.key, faithful,
        issues: faithful === "incorrect" ? [...issues] : [],
        soundness, note,
      });
      setSaved(true);
      onAnnotated();
      const r = await api.annotations(target.key);
      setRows(r);
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="annotate-panel">
      <div className="ann-instructions">
        <b>Two questions.</b>
        <div><b>A. Faithful?</b> Did the system extract this <i>correctly from the paper</i> — about the pipeline, not the science.</div>
        <div><b>B. Sound?</b> Is the claim itself <i>credible</i> — about the science. Optional; skip if outside your expertise.</div>
      </div>

      {/* what you're judging */}
      <div className="ann-target">
        <div className="at-head">{target.heading}</div>
        {target.fields.map((f, i) => (
          <div className="at-field" key={i}>
            <span className="atf-k">{f.label}</span>
            <span className="atf-v">{f.value}</span>
          </div>
        ))}
        {target.source && <div className="at-source">source: {target.source}</div>}
      </div>

      {/* A. faithfulness */}
      <div className="ann-section">
        <div className="ann-q">A. Faithful to the paper?</div>
        <div className="seg">
          {FAITHFUL.map((o) => (
            <button key={o.v} className={`seg-btn ${o.v} ${faithful === o.v ? "on" : ""}`}
                    onClick={() => setFaithful(o.v)}>{o.l}</button>
          ))}
        </div>
        {faithful === "incorrect" && (
          <div className="ann-sub">
            <div className="ann-sub-q">What’s wrong? (select all)</div>
            <div className="chips">
              {ISSUES[target.kind].map((o) => (
                <button key={o.v} className={`chip-btn ${issues.has(o.v) ? "on" : ""}`}
                        onClick={() => toggleIssue(o.v)}>{o.l}</button>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* B. soundness */}
      <div className="ann-section">
        <div className="ann-q">B. Does it hold up? <span className="opt">(optional)</span></div>
        <div className="seg wrap">
          {SOUNDNESS.map((o) => (
            <button key={o.v} className={`seg-btn ${soundness === o.v ? "on" : ""}`}
                    onClick={() => setSoundness(soundness === o.v ? "" : o.v)}>{o.l}</button>
          ))}
        </div>
      </div>

      <textarea className="ann-note" placeholder="notes / suggested fix (optional)"
                value={note} onChange={(e) => setNote(e.target.value)} />

      {err && <div className="err">{err}</div>}
      <div className="ann-actions">
        <button className="btn-primary" onClick={save} disabled={busy}>
          {busy ? "Saving…" : saved ? "Saved ✓ — update" : "Save annotation"}
        </button>
      </div>

      {rows.length > 0 && (
        <div className="ann-existing">
          <div className="k">Verdicts ({rows.length})</div>
          {rows.map((r, i) => (
            <div className="ann-row" key={i}>
              <span className={`vpill ${r.faithful}`}>{r.faithful}</span>
              <span className="who">{r.annotator}</span>
              {r.soundness && r.soundness !== "na" && <span className="snd">{r.soundness}</span>}
              {r.issues?.length > 0 && <span className="iss">{r.issues.join(", ")}</span>}
              {r.note && <span className="ann-note-txt">{r.note}</span>}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
