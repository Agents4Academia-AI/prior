import { useEffect, useRef, useState } from "react";
import { api } from "../lib/api";
import type { AskChatResponse, ChatSessionSummary } from "../lib/api";
import Markdown from "./Markdown";

// Agentic Ask: a multi-turn chat. The model decides whether it can answer from
// context + its own knowledge, and only queries the Neo4j graph when it needs
// corpus facts. Chats are stored SERVER-SIDE, owned by the signed-in user, so they
// survive the browser and are retrievable from any device (see chat_store.py).

type Turn = { role: "user" | "assistant"; content: string; trace?: AskChatResponse["trace"] };

// Local model served by Ollama (configured server-side via PRIOR_LOCAL_MODEL); shown
// in the picker so it's clear which open-weight model answers on the local option.
const OLLAMA_MODEL = "qwen3:14b";

export default function AskPanel() {
  const [sessions, setSessions] = useState<ChatSessionSummary[]>([]);
  const [sid, setSid] = useState<string | null>(null);   // null = unsaved new chat
  const [messages, setMessages] = useState<Turn[]>([]);
  const [draft, setDraft] = useState("");
  const [sending, setSending] = useState(false);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [backend, setBackend] = useState<string>(() => localStorage.getItem("prior_chat_backend") || "claude");
  // Per-user Anthropic key for the "api" backend (bring-your-own-key). Asked once,
  // kept in localStorage, sent per request. Cleared + re-asked if the server rejects it.
  const [apiKey, setApiKey] = useState<string>(() => localStorage.getItem("prior_anthropic_key") || "");
  const [keyDraft, setKeyDraft] = useState("");
  const endRef = useRef<HTMLDivElement | null>(null);
  // Streaming deltas land here and get flushed to React state once per animation
  // frame (not per token) — otherwise hundreds of synchronous re-renders freeze
  // the tab. The bubble renders plain text while streaming; Markdown only at the end.
  const accRef = useRef("");
  const rafRef = useRef<number | null>(null);
  function pickBackend(b: string) { setBackend(b); try { localStorage.setItem("prior_chat_backend", b); } catch { /* */ } }
  function saveApiKey(k: string) {
    const v = k.trim();
    setApiKey(v);
    try { v ? localStorage.setItem("prior_anthropic_key", v) : localStorage.removeItem("prior_anthropic_key"); } catch { /* */ }
  }

  function cancelFlush() {
    if (rafRef.current != null) { cancelAnimationFrame(rafRef.current); rafRef.current = null; }
  }
  function scheduleFlush() {
    if (rafRef.current != null) return;          // a flush is already queued for this frame
    rafRef.current = requestAnimationFrame(() => {
      rafRef.current = null;
      patchLast({ content: accRef.current });
    });
  }
  useEffect(() => () => cancelFlush(), []);       // clean up on unmount

  // Instant scroll (not smooth) — smooth scroll on every frame thrashes the main thread.
  useEffect(() => { endRef.current?.scrollIntoView({ behavior: "auto" }); }, [messages, sending]);

  // Load this user's saved chats from the server on mount.
  async function refreshSessions() {
    try { setSessions((await api.chatsList()).sessions); } catch { /* offline: leave as is */ }
  }
  useEffect(() => { refreshSessions(); }, []);

  function newChat() { setSid(null); setMessages([]); setErr(null); setDraft(""); }

  async function openChat(id: string) {
    if (id === sid) return;
    setErr(null); setLoading(true);
    try {
      const s = await api.chatGet(id);
      setSid(s.id);
      setMessages(s.messages.map((m) => ({ role: m.role as Turn["role"], content: m.content, trace: m.trace })));
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }

  async function deleteChat() {
    if (!sid) { newChat(); return; }
    try { await api.chatDelete(sid); } catch { /* */ }
    newChat();
    refreshSessions();
  }

  // ── Export ────────────────────────────────────────────────────────────────
  function chatTitle(): string {
    const fromSession = sessions.find((s) => s.id === sid)?.title;
    if (fromSession) return fromSession;
    const firstUser = messages.find((m) => m.role === "user")?.content;
    return (firstUser || "Prior chat").slice(0, 80);
  }
  function slugify(s: string): string {
    return s.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "").slice(0, 60) || "prior-chat";
  }
  // Raw Markdown download.
  function exportMd() {
    const out = [`# ${chatTitle()}`, ""];
    for (const m of messages) {
      if (!m.content) continue;
      out.push(m.role === "user" ? "## You" : "## Prior", "", m.content.trim(), "");
    }
    const blob = new Blob([out.join("\n")], { type: "text/markdown;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url; a.download = `${slugify(chatTitle())}.md`;
    document.body.appendChild(a); a.click(); a.remove();
    URL.revokeObjectURL(url);
  }
  // PDF of the rendered Markdown — uses the browser's print-to-PDF on the
  // print-only `.chat-print` view (below), so it matches how the chat looks in the UI.
  function exportPdf() {
    const prev = document.title;
    document.title = slugify(chatTitle());   // browsers use this as the default PDF filename
    window.print();
    window.setTimeout(() => { document.title = prev; }, 500);
  }

  // Update the last (assistant) bubble in place as tokens stream in.
  function patchLast(patch: Partial<Turn>) {
    setMessages((m) => {
      const c = [...m];
      const last = c[c.length - 1];
      if (last && last.role === "assistant") c[c.length - 1] = { ...last, ...patch };
      return c;
    });
  }

  async function send() {
    const text = draft.trim();
    if (!text || sending) return;
    if (backend === "api" && !apiKey) {   // can't call the API without a key
      setErr("Enter your Anthropic API key above to use the Anthropic API model.");
      return;
    }
    // Add the user turn + an empty assistant bubble we'll fill as tokens arrive.
    setMessages((m) => [...m, { role: "user", content: text }, { role: "assistant", content: "" }]);
    setDraft(""); setErr(null); setSending(true);
    accRef.current = "";
    try {
      await api.askChatStream(text, {
        sessionId: sid ?? undefined, backend,
        apiKey: backend === "api" ? apiKey : undefined,
      }, {
        session: (id) => setSid(id),
        delta: (chunk) => { accRef.current += chunk; scheduleFlush(); },   // batched to one render/frame
        trace: (t) => patchLast({ trace: t }),
        // Completion is driven by the event, not by the stream finishing teardown —
        // so the UI unsticks the instant `done` arrives, even if cancel/EOF lags.
        done: (t) => { cancelFlush(); patchLast({ content: accRef.current, trace: t }); setSending(false); },
        error: (e) => {
          setErr(e); setSending(false);
          // Bad/expired key → drop it so the field reappears and the user can re-enter.
          if (backend === "api" && /api key|authoriz|authentication|x-api-key|401|invalid.*key/i.test(e)) saveApiKey("");
        },
      });
      refreshSessions();   // pick up the (possibly new) session + title
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
      patchLast({ content: accRef.current || "_(failed)_" });
    } finally {
      cancelFlush();
      setSending(false);
    }
  }

  function onKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); }
  }

  const curId = sid ?? "__new__";

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
      <div className="ask-bar">
        <select className="ask-sessions" value={curId}
          onChange={(e) => (e.target.value === "__new__" ? newChat() : openChat(e.target.value))}
          title="Saved chats (stored on the server)">
          {!sid && <option value="__new__">New chat</option>}
          {sessions.map((s) => <option key={s.id} value={s.id}>{s.title || "Untitled"}</option>)}
        </select>
        <button className="btn secondary sm" onClick={newChat} title="Start a new chat">+ New</button>
        {sid && (
          <button className="btn secondary sm" onClick={deleteChat} title="Delete this chat">Delete</button>
        )}
        {messages.length > 0 && (
          <>
            <button className="btn secondary sm" onClick={exportMd} title="Download as Markdown (.md)">Export .md</button>
            <button className="btn secondary sm" onClick={exportPdf} title="Save as PDF (rendered, via print)">Export PDF</button>
          </>
        )}
      </div>
      <div className="ask-bar" style={{ marginTop: 6 }}>
        <label className="muted" style={{ fontSize: 12 }}>Model</label>
        <select className="ask-sessions" value={backend} onChange={(e) => pickBackend(e.target.value)} title="Which model answers">
          <option value="claude">Claude (Max subscription, free)</option>
          <option value="api">Anthropic API (your key, fast, paid)</option>
          <option value="ollama">Local: Ollama ({OLLAMA_MODEL})</option>
        </select>
      </div>
      {backend === "api" && (
        <div className="ask-bar" style={{ marginTop: 6 }}>
          {apiKey ? (
            <>
              <span className="muted" style={{ fontSize: 12 }}>Anthropic key saved ✓</span>
              <button className="btn secondary sm" onClick={() => { saveApiKey(""); setKeyDraft(""); }}
                      title="Forget this key and enter a new one">Change key</button>
            </>
          ) : (
            <>
              <input className="ask-sessions" type="password" placeholder="Paste your Anthropic API key (sk-ant-…)"
                value={keyDraft} onChange={(e) => setKeyDraft(e.target.value)}
                onKeyDown={(e) => { if (e.key === "Enter") { saveApiKey(keyDraft); setKeyDraft(""); } }}
                style={{ flex: 1, minWidth: 180 }} />
              <button className="btn secondary sm" disabled={!keyDraft.trim()}
                onClick={() => { saveApiKey(keyDraft); setKeyDraft(""); }}>Save key</button>
            </>
          )}
        </div>
      )}
      <div className="field" style={{ margin: "6px 0 8px" }}>
        <div className="muted" style={{ fontSize: 12 }}>
          Answers from reasoning when it can; queries the graph only when it needs corpus facts.
          Chats are saved to your account on the server. "Claude" uses your subscription (API key scrubbed, never billed per-token);
          "Anthropic API" uses your own key (stored only in this browser); "Local" runs {OLLAMA_MODEL} on-box via Ollama (free).
        </div>
      </div>

      <div style={{ flex: 1, overflowY: "auto", display: "flex", flexDirection: "column", gap: 10, padding: "4px 2px", minHeight: 160 }}>
        {loading && <div className="loading"><span className="spinner" /> Loading chat…</div>}
        {!loading && messages.length === 0 && (
          <div className="muted" style={{ fontSize: 13, padding: "8px 2px" }}>
            e.g. "What methods reduce hallucination in research agents, and do any papers here contradict each other?"
          </div>
        )}
        {messages.map((m, i) => (
          <Bubble key={i} turn={m} />
        ))}
        {sending && messages[messages.length - 1]?.content === "" && (
          <div className="loading"><span className="spinner" /> Thinking…</div>
        )}
        <div ref={endRef} />
      </div>

      {err && <div className="err">{err}</div>}

      <div className="field" style={{ marginTop: 8 }}>
        <textarea rows={3} placeholder="Ask a question. Enter to send, Shift+Enter for a new line."
          value={draft} onChange={(e) => setDraft(e.target.value)} onKeyDown={onKeyDown} />
        <div className="row">
          <button className="btn" onClick={send} disabled={sending}>{sending ? "Thinking…" : "Send"}</button>
        </div>
      </div>

      {/* Print-only view for "Export PDF": hidden on screen, captured by print-to-PDF
          with the Markdown rendered exactly as in the chat. */}
      <div className="chat-print" aria-hidden>
        <h1>{chatTitle()}</h1>
        {messages.filter((m) => m.content).map((m, i) => (
          <div className="print-turn" key={i}>
            <div className="print-role">{m.role === "user" ? "You" : "Prior"}</div>
            {m.role === "user"
              ? <div style={{ whiteSpace: "pre-wrap" }}>{m.content}</div>
              : <Markdown text={m.content} />}
          </div>
        ))}
      </div>
    </div>
  );
}

function Bubble({ turn }: { turn: Turn }) {
  const mine = turn.role === "user";
  // Don't render the empty assistant placeholder; the "Thinking…" spinner covers it.
  if (!mine && !turn.content) return null;
  return (
    <div className={`ask-bubble ${mine ? "mine" : "theirs"}`}>
      <div className="muted ask-role">{mine ? "You" : "Prior"}</div>
      {/* Assistant answers render as Markdown live as they stream — parsing is sub-ms,
          so there's no "convert at the end" delay; user messages stay plain text. */}
      {mine
        ? <div style={{ whiteSpace: "pre-wrap", lineHeight: 1.45 }}>{turn.content}</div>
        : <Markdown text={turn.content} />}
      {turn.trace && turn.trace.length > 0 && <TraceBlock trace={turn.trace} />}
    </div>
  );
}

function TraceBlock({ trace }: { trace: NonNullable<Turn["trace"]> }) {
  const [open, setOpen] = useState(false);
  const calls = trace.filter((t) => t.tool !== "answer" && t.tool !== "direct");
  if (calls.length === 0) return null;
  return (
    <div style={{ marginTop: 8 }}>
      <button className="btn secondary" style={{ fontSize: 11, padding: "2px 8px" }} onClick={() => setOpen((o) => !o)}>
        {open ? "Hide" : "Show"} graph queries ({calls.length})
      </button>
      {open && (
        <ul className="list-tight" style={{ marginTop: 6, fontSize: 12 }}>
          {calls.map((t, i) => (
            <li key={i}>
              <span className="cite">{t.tool}</span>
              {t.args?.query ? ` "${String(t.args.query)}"` : ""}
              {t.args?.cypher ? `: ${String(t.args.cypher)}` : ""}
              {t.args?.id ? ` ${String(t.args.id)}` : ""}
              {typeof t.n === "number" ? ` → ${t.n} result(s)` : ""}
              {t.error ? ` (${t.error})` : ""}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
