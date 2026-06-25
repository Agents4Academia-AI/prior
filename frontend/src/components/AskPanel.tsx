import { useEffect, useRef, useState } from "react";
import { api } from "../lib/api";
import type { ChatMessage, AskChatResponse } from "../lib/api";
import Markdown from "./Markdown";

// Agentic Ask: a multi-turn chat. The model queries the Neo4j knowledge graph
// (read-only Cypher + semantic search) and answers, mixing in general knowledge
// only when it says so. Chats are saved to localStorage so users can resume them.

type Turn = ChatMessage & { trace?: AskChatResponse["trace"] };
type Session = { id: string; title: string; ts: number; messages: Turn[] };

const KEY = "prior_chats";
const loadAll = (): Session[] => {
  try { return JSON.parse(localStorage.getItem(KEY) || "[]") as Session[]; } catch { return []; }
};
const saveAll = (s: Session[]) => {
  try { localStorage.setItem(KEY, JSON.stringify(s.slice(0, 50))); } catch { /* quota */ }
};
const newId = () => `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 7)}`;

export default function AskPanel() {
  const [sessions, setSessions] = useState<Session[]>(() => loadAll());
  const [sid, setSid] = useState<string>(() => loadAll()[0]?.id ?? newId());
  const [messages, setMessages] = useState<Turn[]>(() => loadAll()[0]?.messages ?? []);
  const [draft, setDraft] = useState("");
  const [sending, setSending] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const endRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => { endRef.current?.scrollIntoView({ behavior: "smooth" }); }, [messages, sending]);

  // Persist the current chat whenever it changes.
  useEffect(() => {
    if (messages.length === 0) return;
    setSessions((prev) => {
      const title = (messages.find((m) => m.role === "user")?.content || "New chat").slice(0, 60);
      const updated = [{ id: sid, title, ts: Date.now(), messages }, ...prev.filter((s) => s.id !== sid)];
      saveAll(updated);
      return updated;
    });
  }, [messages, sid]);

  function newChat() { setSid(newId()); setMessages([]); setErr(null); setDraft(""); }
  function openChat(id: string) {
    const s = sessions.find((x) => x.id === id);
    if (!s) return;
    setSid(id); setMessages(s.messages); setErr(null);
  }
  function deleteChat() {
    setSessions((prev) => { const u = prev.filter((s) => s.id !== sid); saveAll(u); return u; });
    newChat();
  }

  async function send() {
    const text = draft.trim();
    if (!text || sending) return;
    const history: ChatMessage[] = [
      ...messages.map((m) => ({ role: m.role, content: m.content })),
      { role: "user", content: text },
    ];
    setMessages((m) => [...m, { role: "user", content: text }]);
    setDraft(""); setErr(null); setSending(true);
    try {
      const res = await api.askChat(history);
      setMessages((m) => [...m, { role: "assistant", content: res.answer, trace: res.trace }]);
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setSending(false);
    }
  }

  function onKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); }
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
      <div className="ask-bar">
        <select className="ask-sessions" value={sid} onChange={(e) => openChat(e.target.value)} title="Saved chats">
          {!sessions.some((s) => s.id === sid) && <option value={sid}>New chat</option>}
          {sessions.map((s) => <option key={s.id} value={s.id}>{s.title || "Untitled"}</option>)}
        </select>
        <button className="btn secondary sm" onClick={newChat} title="Start a new chat">+ New</button>
        {messages.length > 0 && (
          <button className="btn secondary sm" onClick={deleteChat} title="Delete this chat">Delete</button>
        )}
      </div>
      <div className="field" style={{ margin: "8px 0" }}>
        <div className="muted" style={{ fontSize: 12 }}>
          A grounded chat: the assistant queries the knowledge graph and cites papers. It flags anything from general knowledge.
        </div>
      </div>

      <div style={{ flex: 1, overflowY: "auto", display: "flex", flexDirection: "column", gap: 10, padding: "4px 2px", minHeight: 160 }}>
        {messages.length === 0 && (
          <div className="muted" style={{ fontSize: 13, padding: "8px 2px" }}>
            e.g. "What methods reduce hallucination in research agents, and do any papers here contradict each other?"
          </div>
        )}
        {messages.map((m, i) => <Bubble key={i} turn={m} />)}
        {sending && <div className="loading"><span className="spinner" /> Querying the graph and reasoning…</div>}
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
    </div>
  );
}

function Bubble({ turn }: { turn: Turn }) {
  const mine = turn.role === "user";
  return (
    <div className={`ask-bubble ${mine ? "mine" : "theirs"}`}>
      <div className="muted ask-role">{mine ? "You" : "Assistant"}</div>
      {mine
        ? <div style={{ whiteSpace: "pre-wrap", lineHeight: 1.45 }}>{turn.content}</div>
        : <Markdown text={turn.content} />}
      {turn.trace && turn.trace.length > 0 && <TraceBlock trace={turn.trace} />}
    </div>
  );
}

function TraceBlock({ trace }: { trace: NonNullable<Turn["trace"]> }) {
  const [open, setOpen] = useState(false);
  const calls = trace.filter((t) => t.tool !== "answer");
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
