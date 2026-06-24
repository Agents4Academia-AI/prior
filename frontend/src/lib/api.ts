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
export type EvalResults = {
  summary: Record<string, number>;
  scorecard: { dimensions: EvalDim[]; gates: Record<string, string>; note: string };
  distributions: {
    provenance: Record<string, number>;
    global_relations: Record<string, number>;
    local_relations: Record<string, number>;
    claim_types: Record<string, number>;
  };
};
