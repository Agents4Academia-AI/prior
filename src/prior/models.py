"""Core data types and (de)serialisation. Plain dataclasses + JSON, no ORM."""

from __future__ import annotations

import re
from dataclasses import dataclass, field, asdict
from typing import Optional

CLAIM_TYPES = ("empirical", "theoretical", "methodological", "definitional", "background")

# Local graph: relations between claims WITHIN one paper (internal coherence/story).
LOCAL_RELATIONS = ("entails", "contradicts", "supports", "depends_on")
# Global graph: relations between CONTRIBUTIONS across papers.
GLOBAL_RELATIONS = ("builds_on", "refines", "contradicts", "contrast", "supports", "mentions")
# Where a global edge's signal came from (see docs/design.md).
EDGE_SOURCES = ("citation", "text", "both")

# Legacy relation set (pre two-level). Kept so older modules/tests still import it.
RELATIONS = ("supports", "contradicts", "refines", "extends")


@dataclass
class Paper:
    """A primary source. `referenced_works` are the IDs this paper cites —
    that citation structure is what lets Navigator trace origins backward."""

    id: str                              # canonical id, e.g. "openalex:W123" / "arxiv:2401.00001"
    source: str                          # "openalex" | "arxiv"
    title: str
    abstract: str
    url: str
    year: Optional[int] = None
    authors: list[str] = field(default_factory=list)
    venue: Optional[str] = None
    doi: Optional[str] = None
    referenced_works: list[str] = field(default_factory=list)
    cited_by_count: int = 0
    full_text: str = ""        # body text when available (else abstract-only)
    pdf_url: str = ""          # open-access full-text PDF, when known
    type: str = ""             # OpenAlex work type: article/review/letter/editorial/
                               # book-chapter/preprint/... — a free non-primary veto
    is_review: bool = False    # survey/review — excluded as non-primary literature

    def short_cite(self) -> str:
        first = self.authors[0].split()[-1] if self.authors else "Anon"
        etal = " et al." if len(self.authors) > 1 else ""
        return f"{first}{etal} ({self.year or 'n.d.'})"

    def key(self) -> str:
        """Canonical cross-source identity. OpenAlex (W-ids), arXiv (arxiv:…) and
        Semantic Scholar (s2:…) key the SAME paper differently; the normalised
        title is the one identifier every source shares, so it's the reliable
        join for dedup and for the snowball's membership/overlap checks. Falls
        back to the raw id when the title is too short to trust."""
        t = " ".join(re.sub(r"[^a-z0-9]", " ", (self.title or "").lower()).split())
        return f"title:{t}" if len(t) >= 8 else self.id

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Paper":
        return cls(**{k: d[k] for k in cls.__dataclass_fields__ if k in d})  # type: ignore[attr-defined]


@dataclass
class Contribution:
    """A GLOBAL-graph node: one research contribution of a paper, ORKG-style
    (problem + method + result). Cross-paper edges (builds_on / refines /
    contradicts …) connect contributions; `claim_ids` are the LOCAL claims in
    this same paper that support it (the bridge between the two levels)."""

    id: str                   # "<paper_id>::contrib<N>"
    paper_id: str
    problem: str
    method: str
    result: str
    claim_ids: list[str] = field(default_factory=list)
    confidence: float = 0.5

    def summary(self) -> str:
        return f"{self.method} → {self.result} (for: {self.problem})"

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Contribution":
        return cls(**{k: d[k] for k in cls.__dataclass_fields__ if k in d})  # type: ignore[attr-defined]


@dataclass
class Contribution:
    """A GLOBAL-graph node: one research contribution of a paper, ORKG-style
    (problem + method + result). Cross-paper edges (builds_on / refines /
    contradicts …) connect contributions; `claim_ids` are the LOCAL claims in
    this same paper that support it (the bridge between the two levels)."""

    id: str                   # "<paper_id>::contrib<N>"
    paper_id: str
    problem: str
    method: str
    result: str
    claim_ids: list[str] = field(default_factory=list)
    confidence: float = 0.5

    def summary(self) -> str:
        return f"{self.method} → {self.result} (for: {self.problem})"

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Contribution":
        return cls(**{k: d.get(k) for k in cls.__dataclass_fields__})  # type: ignore[attr-defined]


@dataclass
class Claim:
    """A LOCAL-graph node: an atomic, verifiable statement extracted from one
    paper. `contribution_id` links it up to the contribution it supports."""

    id: str                  # "<paper_id>::c<NN>"
    paper_id: str
    text: str                # self-contained claim, no dangling pronouns
    claim_type: str          # one of CLAIM_TYPES
    evidence: str = ""       # short quote / span from the source supporting it
    location: str = "abstract"
    confidence: float = 0.5  # the Reader's confidence it is a genuine claim
    contribution_id: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Claim":
        return cls(**{k: d[k] for k in cls.__dataclass_fields__ if k in d})  # type: ignore[attr-defined]


@dataclass
class Edge:
    """A typed, directed relation in the atlas. `evidence` records *why*;
    `source` records the provenance of a global edge (citation / text / both)."""

    src: str
    dst: str
    relation: str            # LOCAL_/GLOBAL_RELATIONS, or "stated_in"/"cites"/"supports_contrib"
    evidence: str = ""
    confidence: float = 0.5
    source: str = "text"     # one of EDGE_SOURCES (meaningful for global edges)
    level: str = "meta"      # "local" (claim↔claim) | "global" (contrib↔contrib) | "meta"

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Edge":
        return cls(**{k: d[k] for k in cls.__dataclass_fields__ if k in d})  # type: ignore[attr-defined]
