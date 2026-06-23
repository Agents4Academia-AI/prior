import { useState } from "react";
import { api } from "../lib/api";
import type { AskResponse, OriginResponse } from "../lib/types";
import { verdictColor } from "../lib/colors";

export default function AskPanel() {
  const [question, setQuestion] = useState("");
  const [asking, setAsking] = useState(false);
  const [askErr, setAskErr] = useState<string | null>(null);
  const [answer, setAnswer] = useState<AskResponse | null>(null);

  const [concept, setConcept] = useState("");
  const [tracing, setTracing] = useState(false);
  const [originErr, setOriginErr] = useState<string | null>(null);
  const [origin, setOrigin] = useState<OriginResponse | null>(null);

  async function ask() {
    if (!question.trim() || asking) return;
    setAsking(true);
    setAskErr(null);
    setAnswer(null);
    try {
      setAnswer(await api.ask(question.trim()));
    } catch (e) {
      setAskErr(e instanceof Error ? e.message : String(e));
    } finally {
      setAsking(false);
    }
  }

  async function trace() {
    if (!concept.trim() || tracing) return;
    setTracing(true);
    setOriginErr(null);
    setOrigin(null);
    try {
      setOrigin(await api.origin(concept.trim()));
    } catch (e) {
      setOriginErr(e instanceof Error ? e.message : String(e));
    } finally {
      setTracing(false);
    }
  }

  return (
    <div>
      <div className="field">
        <div className="k">Ask the literature</div>
        <textarea
          rows={3}
          placeholder="e.g. Does rehearsal reliably prevent catastrophic forgetting?"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
        />
        <div className="row">
          <button className="btn" onClick={ask} disabled={asking}>
            {asking ? "Asking…" : "Ask"}
          </button>
          {asking && (
            <span className="muted" style={{ alignSelf: "center" }}>
              running LLM, ~30s
            </span>
          )}
        </div>
      </div>

      {asking && (
        <div className="loading">
          <span className="spinner" /> Synthesising an answer from the claim
          graph…
        </div>
      )}
      {askErr && <div className="err">{askErr}</div>}

      {answer && (
        <div>
          <div className="field">
            <span
              className="badge"
              style={{ background: verdictColor[answer.verdict] }}
            >
              {answer.verdict.replace("_", " ")}
            </span>
          </div>
          <Field k="Answer" v={answer.answer} />
          <ListField title="Supporting" items={answer.supporting} />
          <ListField title="Contradicting" items={answer.contradicting} />
          <ListField title="Open questions" items={answer.open_questions} />
          {answer.closest && <Field k="Closest" v={answer.closest} />}
          {answer.gap && <Field k="Gap" v={answer.gap} />}
          {answer.used.length > 0 && (
            <div className="field">
              <div className="k">Cited claims ({answer.used.length})</div>
              {answer.used.map((u) => (
                <div className="neighbour" key={u.id}>
                  <div className="cite">{u.cite}</div>
                  <div className="ev">{u.text}</div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      <hr className="divider" />

      <div className="field">
        <div className="k">Trace origin of a concept</div>
        <input
          className="text"
          placeholder="e.g. elastic weight consolidation"
          value={concept}
          onChange={(e) => setConcept(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && trace()}
        />
        <div className="row">
          <button
            className="btn secondary"
            onClick={trace}
            disabled={tracing}
          >
            {tracing ? "Tracing…" : "Trace origin"}
          </button>
          {tracing && (
            <span className="muted" style={{ alignSelf: "center" }}>
              ~30s
            </span>
          )}
        </div>
      </div>

      {tracing && (
        <div className="loading">
          <span className="spinner" /> Tracing lineage…
        </div>
      )}
      {originErr && <div className="err">{originErr}</div>}

      {origin && (
        <div>
          <Field
            k="Origin paper"
            v={<span className="cite">{origin.origin_paper}</span>}
          />
          <Field k="Account" v={origin.account} />
          <ListField title="Lineage" items={origin.lineage} />
          {origin.caveat && <Field k="Caveat" v={origin.caveat} />}
        </div>
      )}
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

function ListField({ title, items }: { title: string; items: string[] }) {
  if (!items || items.length === 0) return null;
  return (
    <div className="field">
      <div className="k">{title}</div>
      <ul className="list-tight">
        {items.map((it, i) => (
          <li key={i}>{it}</li>
        ))}
      </ul>
    </div>
  );
}
