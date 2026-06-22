import { useEffect, useState } from "react";
import { api, type AnnotationRow } from "../lib/api";

const BASE = ["correct", "incorrect", "unsure"];
const EDGE_EXTRA = ["wrong_type", "wrong_direction"];

export default function AnnotateControls({
  targetKind,
  targetKey,
  signedIn,
  onSaved,
}: {
  targetKind: "claim" | "contribution" | "edge";
  targetKey: string;
  signedIn: boolean;
  onSaved?: () => void;
}) {
  const [rows, setRows] = useState<AnnotationRow[]>([]);
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const verdicts = targetKind === "edge" ? [...BASE, ...EDGE_EXTRA] : BASE;

  const load = () => {
    if (!signedIn) return;
    api
      .annotations(targetKey)
      .then((r) => {
        setRows(r);
        const mine = r.find((x) => x); // own is always returned; pick note
        if (mine && !note) setNote(mine.note ?? "");
      })
      .catch(() => setRows([]));
  };
  // reload whenever the target changes
  useEffect(() => {
    setNote("");
    setRows([]);
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [targetKey, signedIn]);

  const save = async (verdict: string) => {
    setBusy(true);
    setErr(null);
    try {
      await api.annotate({ target_kind: targetKind, target_key: targetKey, verdict, note });
      load();
      onSaved?.();
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  if (!signedIn) {
    return (
      <div className="annotate muted">Sign in (left) to verify this item.</div>
    );
  }

  return (
    <div className="annotate">
      <div className="k">Your verdict</div>
      <div className="verdicts">
        {verdicts.map((v) => (
          <button
            key={v}
            className={`vbtn ${v}`}
            disabled={busy}
            onClick={() => save(v)}
          >
            {v.replace("_", " ")}
          </button>
        ))}
      </div>
      <textarea
        className="ann-note"
        placeholder="note / suggested fix (optional)"
        value={note}
        onChange={(e) => setNote(e.target.value)}
      />
      {err && <div className="err">{err}</div>}
      {rows.length > 0 && (
        <div className="ann-rows">
          {rows.map((r, i) => (
            <div className="ann-row" key={i}>
              <span className={`vpill ${r.verdict}`}>{r.verdict.replace("_", " ")}</span>
              <span className="who">{r.annotator}</span>
              {r.note && <span className="ann-note-txt">{r.note}</span>}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
