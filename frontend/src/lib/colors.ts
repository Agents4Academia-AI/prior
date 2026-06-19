import type { GlobalRelation, ClaimType, ClaimRelation, Verdict } from "./types";

export const relationColor: Record<GlobalRelation, string> = {
  builds_on: "#6ea8fe",
  refines: "#63e6be",
  contradicts: "#ff6b6b",
  contrast: "#ffa94d",
  supports: "#b197fc",
  mentions: "#868e96",
};

export const claimTypeColor: Record<ClaimType, string> = {
  empirical: "#4dabf7",
  theoretical: "#b197fc",
  methodological: "#63e6be",
  definitional: "#ffd43b",
  background: "#868e96",
};

export const claimRelationColor: Record<ClaimRelation, string> = {
  entails: "#63e6be",
  supports: "#6ea8fe",
  contradicts: "#ff6b6b",
  depends_on: "#ffa94d",
};

export const verdictColor: Record<Verdict, string> = {
  established: "#37b24d",
  contested: "#f08c00",
  emerging: "#1c7ed6",
  not_found: "#868e96",
};
