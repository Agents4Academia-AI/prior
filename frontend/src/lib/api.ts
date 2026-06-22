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

async function getJSON<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, init);
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
  summary: () => getJSON<Summary>("/api/summary"),
  papers: () => getJSON<Paper[]>("/api/papers"),
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
};

export type EvalMetric = {
  id: string;
  name: string;
  group: string;
  value: number | null;
  threshold: number;
  higher_better: boolean;
  unit: string;
  status: "pass" | "warn" | "pending";
  kind: string;
  detail: string;
};

export type EvalResults = {
  graph: Record<string, number>;
  distributions: {
    provenance: Record<string, number>;
    global_relations: Record<string, number>;
    local_relations: Record<string, number>;
    claim_types: Record<string, number>;
  };
  metrics: EvalMetric[];
  gates: Record<string, string>;
  note?: string;
};
