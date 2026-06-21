// API response types for the Prior backend.

export interface Summary {
  topic: string;
  papers: number;
  contributions: number;
  claims: number;
  global_edges: number;
  local_edges: number;
  citations: number;
}

export interface Paper {
  id: string;
  title: string;
  year: number;
  authors: string[];
  cite: string;
  url: string;
  n_contributions: number;
  n_claims: number;
}

export type GlobalRelation =
  | "builds_on"
  | "refines"
  | "contradicts"
  | "contrast"
  | "supports"
  | "mentions";

export type Provenance = "both" | "text";

export interface GlobalNode {
  id: string;
  paper_id: string;
  label: string;
  problem: string;
  method: string;
  result: string;
  paper: string;
  year: number;
}

export interface GlobalEdge {
  id: string;
  source: string;
  target: string;
  relation: GlobalRelation;
  provenance: Provenance;
  confidence: number;
  evidence: string;
}

export interface GlobalGraph {
  nodes: GlobalNode[];
  edges: GlobalEdge[];
}

export type ClaimType =
  | "empirical"
  | "theoretical"
  | "methodological"
  | "definitional"
  | "background";

export type ClaimRelation = "entails" | "contradicts" | "supports" | "depends_on";

export interface PaperContribution {
  id: string;
  problem: string;
  method: string;
  result: string;
  claim_ids: string[];
}

export interface ClaimNode {
  id: string;
  label: string;
  claim_type: ClaimType;
  confidence: number;
  evidence: string;
  contribution_id: string;
}

export interface ClaimEdge {
  id: string;
  source: string;
  target: string;
  relation: ClaimRelation;
  evidence: string;
}

export interface PaperGraph {
  paper: { id: string; title: string; cite: string; url: string };
  contributions: PaperContribution[];
  nodes: ClaimNode[];
  edges: ClaimEdge[];
}

export interface Neighbour {
  src: string;
  dst: string;
  relation: GlobalRelation;
  provenance: Provenance;
  confidence: number;
  evidence: string;
}

export interface ContributionDetail {
  id: string;
  paper_id: string;
  problem: string;
  method: string;
  result: string;
  claims: { id: string; text: string; [k: string]: unknown }[];
  neighbours: Neighbour[];
}

export type Verdict = "established" | "contested" | "emerging" | "not_found";

export interface AskResponse {
  verdict: Verdict;
  answer: string;
  supporting: string[];
  contradicting: string[];
  open_questions: string[];
  closest: string | null;
  gap: string | null;
  used: { id: string; text: string; cite: string }[];
}

export interface OriginResponse {
  origin_paper: string;
  account: string;
  lineage: string[];
  caveat: string;
}
