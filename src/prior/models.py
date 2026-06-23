"""Core data types and (de)serialisation. Plain dataclasses + JSON, no ORM."""

from __future__ import annotations

import re
from dataclasses import dataclass, field, asdict
from typing import Optional

CLAIM_TYPES = ("empirical", "theoretical", "methodological", "definitional")
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
        # only pass present keys so new fields fall back to their defaults
        return cls(**{k: d[k] for k in cls.__dataclass_fields__ if k in d})  # type: ignore[attr-defined]


@dataclass
class Claim:
    """An atomic, verifiable statement extracted from one paper."""

    id: str                  # "<paper_id>::c<NN>"
    paper_id: str
    text: str                # self-contained claim, no dangling pronouns
    claim_type: str          # one of CLAIM_TYPES
    evidence: str = ""       # short quote / span from the source supporting it
    location: str = "abstract"
    confidence: float = 0.5  # the Reader's confidence it is a genuine claim

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Claim":
        return cls(**{k: d.get(k) for k in cls.__dataclass_fields__})  # type: ignore[attr-defined]


@dataclass
class Edge:
    """A typed, directed relation in the atlas. `evidence` records *why*."""

    src: str
    dst: str
    relation: str            # RELATIONS, or "stated_in" / "cites"
    evidence: str = ""
    confidence: float = 0.5

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Edge":
        return cls(**{k: d.get(k) for k in cls.__dataclass_fields__})  # type: ignore[attr-defined]
