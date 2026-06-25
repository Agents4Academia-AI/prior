import type {
  Summary,
  Paper,
  GlobalGraph,
  PaperGraph,
  ContributionDetail,
  AskResponse,
  OriginResponse,
} from "./types";

const API_BASE =
  import.meta.env.VITE_API_BASE?.replace(/\/$/, "") || "http://127.0.0.1:8077";

// ── identity (username + password) kept in localStorage, sent as headers ───────
export type Identity = { user: string; password: string };

export function getIdentity(): Identity | null {
  try {
    const raw = localStorage.getItem("prior_identity");
    return raw ? (JSON.parse(raw) as Identity) : null;
  } catch {
    return null;
  }
}
export function setIdentity(id: Identity | null) {
  if (id) localStorage.setItem("prior_identity", JSON.stringify(id));
  else localStorage.removeItem("prior_identity");
}
function authHeaders(): Record<string, string> {
  const id = getIdentity();
  return id
    ? { "X-Prior-User": id.user, "X-Prior-Password": id.password }
    : {};
}

async function getJSON<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { ...authHeaders(), ...(init?.headers ?? {}) },
  });
  if (!res.ok) {
    let detail = "";
    try {
      detail = await res.text();
    } catch {
      /* ignore */
    }
    throw new Error(
      `Request failed (${res.status} ${res.statusText})${
        detail ? `: ${detail.slice(0, 200)}` : ""
      }`,
    );
  }
  return (await res.json()) as T;
}

function postJSON<T>(path: string, body: unknown): Promise<T> {
  return getJSON<T>(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export const api = {
  base: API_BASE,
  collections: () => getJSON<CollectionsResp>("/api/collections"),
  summary: (collection?: string) =>
    getJSON<Summary>(`/api/summary${collection ? `?collection=${encodeURIComponent(collection)}` : ""}`),
  papers: (collection?: string) =>
    getJSON<Paper[]>(`/api/papers${collection ? `?collection=${encodeURIComponent(collection)}` : ""}`),
  renderGlobal: (collection: string, opts?: { minTrust?: number; maxNodes?: number; yearMax?: number }) => {
    const q = new URLSearchParams({ collection });
    if (opts?.minTrust) q.set("min_trust", String(opts.minTrust));
    if (opts?.maxNodes) q.set("max_nodes", String(opts.maxNodes));
    if (opts?.yearMax) q.set("year_max", String(opts.yearMax));
    return getJSON<RenderPayload>(`/api/render/global?${q.toString()}`);
  },
  globalGraph: () => getJSON<GlobalGraph>("/api/graph/global"),
  // paper_id contains a colon; encode it so it survives the URL safely.
  paperGraph: (paperId: string) =>
    getJSON<PaperGraph>(`/api/graph/paper/${encodeURIComponent(paperId)}`),
  contribution: (contribId: string) =>
    getJSON<ContributionDetail>(
      `/api/contribution/${encodeURIComponent(contribId)}`,
    ),
  ask: (question: string) => postJSON<AskResponse>("/api/ask", { question }),
  // Send the new user turn + session id; the server owns history and context.
  askChat: (message: string, sessionId?: string, backend?: string, collection?: string) =>
    postJSON<AskChatResponse>("/api/ask_chat", {
      message, session_id: sessionId, backend, collection,
    }),
  // Streaming chat over SSE: tokens arrive as they generate, so the UI never
  // sits frozen on one long request.
  askChatStream: async (
    message: string,
    opts: { sessionId?: string; backend?: string; collection?: string; apiKey?: string },
    on: {
      session?: (id: string) => void;
      trace?: (t: AskChatTrace[]) => void;
      delta?: (s: string) => void;
      done?: (t: AskChatTrace[]) => void;
      error?: (e: string) => void;
    },
    signal?: AbortSignal,
  ): Promise<void> => {
    // Safety net: if no bytes arrive for IDLE_MS, abort instead of spinning forever.
    // The watchdog is reset on every chunk, so a slow-but-alive stream is fine.
    const IDLE_MS = 90_000;
    const ctrl = new AbortController();
    if (signal) signal.addEventListener("abort", () => ctrl.abort(), { once: true });
    let timedOut = false;
    let idle: ReturnType<typeof setTimeout> | undefined;
    const bump = () => {
      if (idle) clearTimeout(idle);
      idle = setTimeout(() => { timedOut = true; ctrl.abort(); }, IDLE_MS);
    };
    const stop = () => { if (idle) clearTimeout(idle); };

    bump();
    let res: Response;
    try {
      res = await fetch(`${API_BASE}/api/ask_chat_stream`, {
        method: "POST",
        headers: {
          ...authHeaders(), "Content-Type": "application/json",
          ...(opts.apiKey ? { "X-Anthropic-Key": opts.apiKey } : {}),
        },
        body: JSON.stringify({
          message, session_id: opts.sessionId, backend: opts.backend, collection: opts.collection,
        }),
        signal: ctrl.signal,
      });
    } catch (e) {
      stop();
      if (timedOut) throw new Error("The model took too long to respond (timed out). Please try again.");
      throw e;
    }
    if (!res.ok || !res.body) {
      stop();
      const detail = await res.text().catch(() => "");
      throw new Error(`Request failed (${res.status} ${res.statusText})${detail ? `: ${detail.slice(0, 200)}` : ""}`);
    }
    const reader = res.body.getReader();
    const dec = new TextDecoder();
    let buf = "";
    let returned = false;
    // Parse whatever complete `data: ...` events sit in `buf`. Returns true if a
    // terminal (done/error) event was handled. `final` flushes a trailing event that
    // never got its closing \n\n before the socket closed.
    const drain = (final: boolean): boolean => {
      const parts = buf.split("\n\n");
      buf = final ? "" : (parts.pop() || "");
      for (const part of parts) {
        const line = part.trim();
        if (!line.startsWith("data:")) continue;
        const json = line.slice(5).trim();
        if (!json) continue;
        let ev: { type: string; [k: string]: unknown };
        try { ev = JSON.parse(json); } catch { continue; }
        if (ev.type === "session") on.session?.(ev.session_id as string);
        else if (ev.type === "trace") on.trace?.(ev.trace as AskChatTrace[]);
        else if (ev.type === "delta") on.delta?.(ev.text as string);
        else if (ev.type === "done") {
          on.done?.((ev.trace as AskChatTrace[]) || []);
          returned = true;
          reader.cancel().catch(() => {});   // fire-and-forget — awaiting can hang on keep-alive
          return true;
        } else if (ev.type === "error") {
          on.error?.(ev.error as string);
          returned = true;
          reader.cancel().catch(() => {});
          return true;
        }
      }
      return false;
    };
    // The `done`/`error` event is the completion signal — return the instant it
    // arrives. Do NOT wait for the socket to close (claude-p lags before exiting and
    // HTTP keep-alive can delay EOF, which would leave the UI stuck on "Thinking…").
    try {
      for (;;) {
        const { value, done } = await reader.read();
        if (done) {
          if (!returned) drain(true);             // EOF: flush a trailing event that lacked \n\n
          break;
        }
        bump();                                   // got data → reset the watchdog
        buf += dec.decode(value, { stream: true });
        if (drain(false)) return;
      }
    } catch (e) {
      if (timedOut) throw new Error("The model stalled mid-answer (timed out). Please try again.");
      throw e;
    } finally {
      stop();
    }
  },
  // Durable, per-user chat history (server-side).
  chatsList: () => getJSON<ChatListResp>("/api/chats"),
  chatGet: (sid: string) => getJSON<ChatSessionFull>(`/api/chats/${encodeURIComponent(sid)}`),
  chatRename: (sid: string, title: string) =>
    postJSON<{ ok: boolean }>(`/api/chats/${encodeURIComponent(sid)}/rename`, { title }),
  chatDelete: (sid: string) =>
    getJSON<{ ok: boolean }>(`/api/chats/${encodeURIComponent(sid)}`, { method: "DELETE" }),
  origin: (concept: string) =>
    postJSON<OriginResponse>("/api/origin", { concept }),
  eval: () => getJSON<EvalResults>("/api/eval"),
  whoami: () => getJSON<WhoAmI>("/api/whoami"),
  annotate: (b: {
    target_kind: string;
    target_key: string;
    faithful: string;
    issues?: string[];
    soundness?: string;
    note?: string;
  }) => postJSON<{ ok: boolean; annotated: number }>("/api/annotate", b),
  annotations: (targetKey: string) =>
    getJSON<AnnotationRow[]>(
      `/api/annotations?target_key=${encodeURIComponent(targetKey)}`,
    ),
  ingest: async (kind: string, value: string, file: File | null, force = false, collection?: string) => {
    const fd = new FormData();
    fd.append("kind", kind);
    if (value) fd.append("value", value);
    if (force) fd.append("force", "true");
    if (collection) fd.append("collection", collection);
    if (file) fd.append("file", file);
    const res = await fetch(`${API_BASE}/api/ingest`, {
      method: "POST",
      headers: authHeaders(), // multipart: let the browser set Content-Type
      body: fd,
    });
    if (!res.ok) throw new Error((await res.text()).slice(0, 200) || `HTTP ${res.status}`);
    return (await res.json()) as { job_id: string };
  },
  ingestStatus: (jobId: string) => getJSON<IngestJob>(`/api/ingest/${jobId}`),
};

export type IngestJob = {
  id: string;
  kind: string;
  label: string;
  status:
    | "queued" | "fetching" | "extracting" | "relating" | "done" | "failed" | "duplicate";
  message: string;
  paper_id: string | null;
  title: string | null;
  result: { contribs?: number; claims?: number; edges?: number };
  duplicate_of: { kind: string; id: string; title: string } | null;
  error: string | null;
};

export type CollectionInfo = {
  name: string;
  papers: number;
  topic: string;
  source: string;
  created_at: string | null;
};
export type CollectionsResp = { collections: CollectionInfo[]; default: string };

export type RContrib = {
  id: string;
  comm: number;
  kind: string;
  stmt: string;
  quote: string;
  deg: number;
  year: number | null;
  cite: string;
};
export type RLink = {
  source: string;
  target: string;
  rel: string;
  ev: string;
  trust: number;
  tier: string;
};
export type ClusterLegend = { id: number; label: string; color: string; n: number };
export type RenderPayload = {
  collection: string;
  topic: string;
  legend: ClusterLegend[];
  rel: Record<string, string>;
  contribs: RContrib[];
  contribLinks: RLink[];
  n_contribs: number;
  n_links: number;
  capped?: boolean;
  total_contribs?: number;
};

export type WhoAmI = {
  signed_in: boolean;
  user?: string;
  is_admin?: boolean;
  open_mode?: boolean;
  shared?: boolean;
  annotated?: number;
};
export type AnnotationRow = {
  annotator: string;
  faithful: string;
  issues: string[];
  soundness: string;
  note: string;
  created_at: string;
};
export type AnnSummary = {
  n: number;
  correct: number;
  incorrect: number;
  unsure: number;
  mine: string | null;
};

export type EvalRate = { n: number; correct: number | null };
export type EvalDim = {
  kind: string;
  gate_label: string;
  threshold: number;
  gate: "pass" | "warn" | "pending";
  self_eval: EvalRate;
  human: EvalRate;
  aggregated: EvalRate;
  agreement: { n: number; rate: number | null };
};
export type CalibBin = { lo: number; hi: number; n: number; score: number; acc: number };
export type CalibThreshold = { t: number; kept: number; coverage: number | null; accuracy: number | null };
export type CalibDim = {
  kind: string;
  signal: string;
  n: number;
  auc: number | null;
  accuracy: number | null;
  mean_score: number | null;
  ece: number | null;
  reliability: CalibBin[];
  thresholds: CalibThreshold[];
};
// ── agentic Ask chat ───────────────────────────────────────────────────────────
export type ChatRole = "user" | "assistant" | "system";
export type ChatMessage = { role: ChatRole; content: string };
export type AskChatTrace = {
  tool: string;
  args?: Record<string, unknown>;
  n?: number | null;
  error?: string | null;
  thought?: string;
};
export type AskChatResponse = {
  answer: string;
  used: { id?: string; text?: string; title?: string }[];
  trace: AskChatTrace[];
  session_id: string;
};
export type ChatSessionSummary = {
  id: string;
  title: string;
  n: number;
  created_at: string;
  updated_at: string;
};
export type ChatListResp = { user: string; sessions: ChatSessionSummary[] };
export type ChatStoredMessage = {
  role: ChatRole;
  content: string;
  trace?: AskChatTrace[];
  created_at: string;
};
export type ChatSessionFull = {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
  messages: ChatStoredMessage[];
};

export type JudgeRate = { n: number; correct: number | null };
export type JudgesDim = { kind: string; rates: Record<string, JudgeRate> };
export type JudgeAgreement = { a: string; b: string; n: number; rate: number };
export type EvalJudges = { labels: string[]; dimensions: JudgesDim[]; agreement: JudgeAgreement[] };
export type EvalResults = {
  summary: Record<string, number>;
  scorecard: { dimensions: EvalDim[]; gates: Record<string, string>; note: string };
  judges: EvalJudges;
  calibration: { dimensions: CalibDim[]; note: string };
  distributions: {
    provenance: Record<string, number>;
    global_relations: Record<string, number>;
    local_relations: Record<string, number>;
    claim_types: Record<string, number>;
  };
};
