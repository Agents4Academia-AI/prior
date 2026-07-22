"""refresolve — resolve a raw bibliography reference to a canonical identity.

Prior's boundary around citation_verification's reference resolver (edge_quality
milestone 1). We reuse Team 2's `MultiSourceResolver` — a deterministic
DOI → arXiv-id → gated-fuzzy-title match cascade over Crossref/arXiv/DBLP/S2/
OpenAlex — instead of re-implementing it. We import ONLY the frozen contract
seams (`grounding.resolver` + `schema.Resolved`/`MatchMethod`), never another
c-v module's internals, per their contract.

Why an adapter at all (rather than calling the resolver directly)?  Two reasons,
which are the two layers below:

1. **Shape.** The resolver returns a c-v `Resolved` (canonical metadata + `doi` +
   `arxiv_id` + provenance). Prior wants a small, stable, Prior-shaped value it
   can depend on even if the upstream `Resolved` grows fields. -> `ResolvedRef`.

2. **Identity.** The resolver never returns an OpenAlex `W…` id — Prior's node id
   for most papers. It gives a DOI / arXiv id / title. Turning that into an
   EXISTING Prior node id (so we can draw a `cites` edge to it) is a second,
   corpus-aware step. -> `CorpusIndex` + :func:`map_to_corpus`.

Milestone-1 scope: resolution + intra-corpus `cites` edges only. No metadata
verdicts, no support/relevance judgement (those are milestones 2–3).

Network + fail-soft: :func:`resolve_reference` hits the grounding sources and, on
ANY trouble, returns ``None`` rather than raising — a stuck reference degrades to
"unresolved" and the caller's run continues, mirroring c-v's contract.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import lru_cache
from typing import TYPE_CHECKING, Iterable, Optional

if TYPE_CHECKING:  # avoid importing models at module load; only needed for typing
    from ..models import Paper

# A well-formed single reference stays well under this; anything larger is a
# malformed record (a whole bibliography captured as one entry) — skipped, not
# guessed, to keep resolution precise. See :func:`resolve_reference`.
REFERENCE_CHAR_CAP = 5000


# ── canonical-identity helpers (shared by the resolver output and the corpus) ──
def _norm_arxiv(arxiv_id: str | None) -> str:
    """arXiv id -> version-stripped stem ('2407.00466v1' -> '2407.00466').

    Prior stores arXiv ids inconsistently (with and without the version suffix),
    so the *stem* is the reliable join key across the corpus and resolver output.
    """
    if not arxiv_id:
        return ""
    s = arxiv_id.strip().lower()
    s = re.sub(r"^arxiv:\s*", "", s)          # tolerate an 'arxiv:' prefix
    s = s.rstrip("/").rsplit("/", 1)[-1]      # tolerate a URL tail
    return s.split("v")[0]                     # drop the version suffix


def _norm_doi(doi: str | None) -> str:
    """DOI -> bare lowercase form ('https://doi.org/10.x/Y' -> '10.x/y')."""
    if not doi:
        return ""
    d = doi.strip().lower()
    d = re.sub(r"^https?://(dx\.)?doi\.org/", "", d)
    return d.rstrip(".")


def _norm_title(title: str | None) -> str:
    """Normalised title, IDENTICAL to Prior's ``Paper.key()`` collapsing, so a
    resolver title and a corpus title join on exactly the same string."""
    return " ".join(re.sub(r"[^a-z0-9]", " ", (title or "").lower()).split())


# ── LaTeX reference pre-normalisation ─────────────────────────────────────────
# Prior's mined `bibtex` field is a raw LaTeX \bibitem body — \newblock, \url{},
# \href{}{}, ~ (non-breaking space), braces — NOT a clean reference string. The
# resolver's keyless id/title extraction is defeated by this (an arXiv *URL* is
# not its `arXiv:<id>` id form; \newblock fragments hijack title-clause splitting).
# We condition the input here so the resolver stays general and Prior feeds it a
# reference string it can actually parse.
_HREF_RE = re.compile(r"\\href\{[^}]*\}\{([^}]*)\}")     # \href{url}{text} -> text
_URL_RE = re.compile(r"\\url\{([^}]*)\}")                 # \url{u} -> u
# The three arXiv-id spellings seen in the mined bibitems, unified to `arXiv:<id>`:
_ARXIV_URL_RE = re.compile(r"arxiv\.org/(?:abs|pdf)/(\d{4}\.\d{4,5}(?:v\d+)?)", re.I)   # \url{arxiv.org/abs/ID}
_ARXIV_ABS_RE = re.compile(r"\babs/(\d{4}\.\d{4,5}(?:v\d+)?)", re.I)                     # \emph{ArXiv}, abs/ID
_LATEX_CMD_RE = re.compile(r"\\[a-zA-Z]+\b")             # \newblock \emph \textbf …


def _clean_latex_reference(reference: str) -> str:
    """Turn a raw LaTeX \\bibitem body into a resolver-friendly reference string.

    Key move: rewrite every arXiv-id spelling (URL, ``abs/ID``) into the explicit
    ``arXiv:<id>`` form the resolver's exact-id tier recognises — a precise,
    keyless, single-call match.
    """
    s = _HREF_RE.sub(r" \1 ", reference)
    s = _URL_RE.sub(r" \1 ", s)
    s = _ARXIV_URL_RE.sub(lambda m: f" arXiv:{m.group(1)} ", s)
    s = _ARXIV_ABS_RE.sub(lambda m: f" arXiv:{m.group(1)} ", s)
    s = _LATEX_CMD_RE.sub(" ", s)                         # drop \newblock and friends
    s = s.replace("~", " ").replace("{", " ").replace("}", " ")
    return re.sub(r"\s+", " ", s).strip()


# ── raw BibTeX field syntax ───────────────────────────────────────────────────
# Some mined records are the entry's field body ("title={…}, author={…}, …"),
# not a formatted reference string — the resolver's title extractor can't read
# key=value syntax. Detect it and rebuild a reference string from the fields so
# the normal cascade (title search / doi / arXiv-id tier) runs.
_BIBTEX_FIELD_RE = re.compile(r"(\w+)\s*=\s*[{\"]([^{}\"]*)[}\"]")
_BIBTEX_MARKER_RE = re.compile(r"\b(?:title|author)\s*=\s*[{\"]", re.I)


def _looks_like_bibtex_fields(reference: str) -> bool:
    return bool(_BIBTEX_MARKER_RE.search(reference))


def _bibtex_fields_to_reference(reference: str) -> str:
    """Rebuild a reference string from BibTeX ``key={value}`` fields (or ``""``)."""
    fields = {k.lower(): v.strip() for k, v in _BIBTEX_FIELD_RE.findall(reference)}
    title = fields.get("title")
    if not title:
        return ""                                         # nothing to anchor a match on
    parts = []
    if fields.get("author"):
        parts.append(fields["author"])
    parts.append(title)
    venue = fields.get("journal") or fields.get("booktitle")
    if venue:
        parts.append(venue)
    if fields.get("year"):
        parts.append(fields["year"])
    ref = ". ".join(parts) + "."
    if fields.get("doi"):
        ref += f" doi:{fields['doi']}"
    eprint = fields.get("eprint") or fields.get("arxiv") or ""
    if re.match(r"\d{4}\.\d{4,5}", eprint):               # arXiv eprint id form
        ref += f" arXiv:{eprint}"
    return ref


# ── Layer 1: the reference -> canonical identity ──────────────────────────────
@dataclass
class ResolvedRef:
    """Prior's view of one resolved reference. A stable projection of the c-v
    ``Resolved``: the fields Prior joins on, plus match provenance for trust."""

    reference: str                        # the raw bibliography string we resolved
    doi: str = ""                         # canonical, bare-lowercase (may be "")
    arxiv_id: str = ""                    # canonical, version-stripped stem (may be "")
    title: str = ""
    year: Optional[int] = None
    source: str = ""                      # which grounding source matched (crossref/arxiv/…)
    match_method: str = "none"            # doi | arxiv | fuzzy_title | direct_url | none
    match_score: float = 0.0              # 0..1 confidence from the resolver

    @property
    def arxiv_prior_id(self) -> str:
        """The Prior node id implied by the arXiv stem, if any ('arxiv:2407.00466')."""
        return f"arxiv:{self.arxiv_id}" if self.arxiv_id else ""


@lru_cache(maxsize=1)
def _default_resolver():
    """A process-shared :class:`MultiSourceResolver` (built lazily, once).

    Reusing one instance keeps its internal per-source fetch cache warm across a
    run. Settings come from c-v's ``load_settings()`` so the environment / a
    gitignored ``.env`` (OPENALEX_API_KEY, CROSSREF_MAILTO, CONTACT_EMAIL, …)
    flow through and unlock the polite/keyed grounding sources; absent keys just
    fall back to the keyless Crossref+arXiv floor. ``validate_urls=False`` — for
    milestone 1 we need canonical *identity*, not URL liveness, so we skip the
    extra HEAD/GET checks.
    """
    from citation_verifier.grounding.resolver import MultiSourceResolver
    try:
        from citation_verifier.config import load_settings
        settings = load_settings()
    except Exception:  # noqa: BLE001 — keyless floor is always fine
        settings = None
    return MultiSourceResolver(settings=settings, validate_urls=False)


def resolve_reference(reference: str, *, resolver=None) -> Optional[ResolvedRef]:
    """Resolve one raw bibliography reference to a :class:`ResolvedRef`, or ``None``.

    ``reference`` is the reference as written — a bibliography line or a raw
    BibTeX entry body (e.g. ``citation_map.json``'s ``bibtex`` field). Pass a
    shared ``resolver`` to reuse a warm cache across many calls; omit it to use
    the process-shared default.

    Returns ``None`` when nothing matches OR anything goes wrong (fail-soft): the
    resolver hits the network, and a reference that cannot be grounded must not
    crash ingestion — it is simply left unresolved.
    """
    if not reference or not reference.strip():
        return None
    # A single reference is short (a few hundred chars, even with a long author
    # list). A multi-KB blob means the extractor over-captured — a whole
    # bibliography leaked into one record. Truncating and resolving the *first*
    # entry would silently return the WRONG paper, so we skip these outright
    # (unresolved) and leave them to the extractor generalisation (milestone 1
    # deferred work) rather than guess.
    if len(reference) > REFERENCE_CHAR_CAP:
        return None
    r = resolver or _default_resolver()
    raw = reference
    if _looks_like_bibtex_fields(raw):               # "title={…}, author={…}" form
        raw = _bibtex_fields_to_reference(raw) or raw
    cleaned = _clean_latex_reference(raw)            # condition LaTeX \bibitem input
    try:
        resolved = r.resolve("", cleaned)            # cite_key unused; match is by content
    except Exception:  # noqa: BLE001 — every grounding source already fails soft; belt-and-braces
        return None
    if resolved is None:
        # The full resolver abstained. But if the reference LITERALLY states an
        # arXiv id / DOI, that id is a reliable canonical join key for building an
        # intra-corpus citation graph — the resolver's title-contradiction gate is
        # tuned for fraud detection ("is this citation fabricated?"), which is
        # milestone 2's concern, not milestone 1's. Trust the stated id.
        return _resolve_from_stated_id(cleaned, reference)

    mm = getattr(resolved.match_method, "value", resolved.match_method) or "none"
    return ResolvedRef(
        reference=reference,
        doi=_norm_doi(resolved.doi),
        arxiv_id=_norm_arxiv(resolved.arxiv_id),
        title=(resolved.title or "").strip(),
        year=resolved.year,
        source=resolved.source or "",
        match_method=str(mm),
        match_score=float(resolved.match_score or 0.0),
    )


# Owned by Prior (not c-v internals): pull an explicitly-stated id from a reference.
_FIND_ARXIV_RE = re.compile(r"arxiv[:\s]*(\d{4}\.\d{4,5})(?:v\d+)?", re.I)
_FIND_DOI_RE = re.compile(r"\b(10\.\d{4,9}/[-._;()/:A-Za-z0-9]+)\b")


def _resolve_from_stated_id(cleaned: str, reference: str) -> Optional[ResolvedRef]:
    """Build a ResolvedRef from an id the reference states outright, or ``None``.

    High precision by construction: a written-out arXiv id / DOI is the citing
    author's own pointer at the work. For an arXiv id we fetch the canonical title
    (one call, via Prior's arXiv source) so a title-only corpus node — e.g. a
    non-arXiv OpenAlex work cited by its arXiv id — can still be joined by title.
    """
    m = _FIND_ARXIV_RE.search(cleaned)
    if m:
        aid = m.group(1)
        title, year = "", None
        try:
            from . import arxiv
            got = arxiv.fetch_ids([aid]) or {}
            p = next(iter(got.values()), None)
            if p:
                title, year = (p.title or ""), p.year
        except Exception:  # noqa: BLE001 — enrichment is best-effort; id alone still maps by arXiv stem
            pass
        return ResolvedRef(reference=reference, arxiv_id=_norm_arxiv(aid), title=title.strip(),
                           year=year, source="arxiv", match_method="arxiv", match_score=1.0)
    m = _FIND_DOI_RE.search(cleaned)
    if m:
        return ResolvedRef(reference=reference, doi=_norm_doi(m.group(1)),
                           source="doi", match_method="doi", match_score=1.0)
    return None


# ── Layer 2: canonical identity -> an EXISTING Prior node id ───────────────────
@dataclass
class CorpusIndex:
    """Reverse lookup from a canonical identity to a Prior node id.

    Built once from the papers Prior already holds; :meth:`match` then maps a
    :class:`ResolvedRef` onto one of those ids by the same three keys the
    resolver matches on, most-specific first: arXiv stem, then DOI, then
    normalised title. This is the join that turns a resolved reference into an
    intra-corpus ``cites`` edge.
    """

    by_arxiv: dict[str, str] = field(default_factory=dict)
    by_doi: dict[str, str] = field(default_factory=dict)
    by_title: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_papers(cls, papers: Iterable["Paper"]) -> "CorpusIndex":
        idx = cls()
        for p in papers:
            # A paper's own id may itself be an arXiv id ('arxiv:2606.08532').
            stem = _norm_arxiv(p.id[6:]) if p.id.startswith("arxiv:") else _norm_arxiv(getattr(p, "arxiv_id", ""))
            if stem:
                idx.by_arxiv.setdefault(stem, p.id)
            d = _norm_doi(p.doi)
            if d:
                idx.by_doi.setdefault(d, p.id)
            t = _norm_title(p.title)
            if len(t) >= 8:                      # mirror Paper.key(): short titles aren't a reliable join
                idx.by_title.setdefault(t, p.id)
        return idx

    def match(self, rref: ResolvedRef) -> Optional[str]:
        """Return the Prior node id this resolved reference points at, or ``None``.

        Re-normalises the reference's ids defensively, so a ``ResolvedRef`` built
        by hand (not via :func:`resolve_reference`) still joins on the same keys.
        """
        stem = _norm_arxiv(rref.arxiv_id)
        if stem and stem in self.by_arxiv:
            return self.by_arxiv[stem]
        doi = _norm_doi(rref.doi)
        if doi and doi in self.by_doi:
            return self.by_doi[doi]
        t = _norm_title(rref.title)
        if len(t) >= 8 and t in self.by_title:
            return self.by_title[t]
        return None


def map_to_corpus(rref: ResolvedRef, index: CorpusIndex) -> Optional[str]:
    """Convenience: the Prior node id for a resolved reference, or ``None``."""
    return index.match(rref)
