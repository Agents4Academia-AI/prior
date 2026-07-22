"""refextract — get the raw reference strings a paper cites.

The companion to :mod:`prior.sources.refresolve`. ``refresolve`` turns *one*
reference string into a canonical identity; this module answers the prior
question: **what are a paper's reference strings in the first place?**

Why a separate stage — and why it's the "extractor generalization" of the
edge_quality milestone. The mined citation inputs (``citation_map.json``) only
exist for the arXiv papers, because they were harvested from arXiv LaTeX ``.bbl``
sources. A non-arXiv paper has no LaTeX source, so it never got a mined
bibliography and its citations are invisible — that is exactly why those papers
are graph orphans. The general channel that works for *any* paper is its own
full text: locate the bibliography and segment it into individual references.

So :func:`references_for` is a channel cascade, most-trusted first:

1. **Mined references** handed in by the caller (raw ``bibtex`` lines keyed by
   citing paper id) — used as-is when present.
2. **Full-text bibliography** — find the References/Bibliography section in
   ``paper.full_text`` and split it into entries. This is the generalization:
   it reconnects non-arXiv papers the moment their text is available.
3. Nothing — an honest empty list (the paper is left unresolved, never guessed).

Segmentation is deliberately conservative: a wrong split invents a reference
that resolves to the wrong paper, so we prefer to yield fewer, cleaner entries.
Anything the downstream resolver would refuse anyway (over
:data:`~prior.sources.refresolve.REFERENCE_CHAR_CAP`) is dropped here too.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Optional

from .refresolve import REFERENCE_CHAR_CAP

if TYPE_CHECKING:  # only needed for typing; avoid importing models at load
    from ..models import Paper

# A reference shorter than this is noise (a stray line, a section number), not a
# citation we can resolve. Long enough to carry an author + a title fragment.
_MIN_REFERENCE_CHARS = 20
# Guard against a runaway split turning one blob into thousands of "entries".
_MAX_REFERENCES = 500

# The bibliography heading, on its own line (optionally numbered / uppercased).
# We take the text AFTER the last such heading — appendices occasionally repeat
# the word, and the real reference list is the final one.
_BIB_HEADING_RE = re.compile(
    r"^[\s0-9.]*(references|bibliography|works\s+cited|references\s+cited)\s*$",
    re.I | re.M,
)
# Bracketed numeric markers: "[1] Foo. ... [2] Bar. ..." — the cleanest signal.
_BRACKET_MARKER_RE = re.compile(r"(?m)^\s*\[(\d{1,4})\]\s+")
# Leading-number markers: "1. Foo ..." / "12  Bar ..." at line start.
_NUMBER_MARKER_RE = re.compile(r"(?m)^\s*(\d{1,4})[.)]\s+")
# A citation marker at the very start of one entry — stripped so the entry begins
# at the author (the blank-line fallback doesn't consume markers the way the
# marker-split paths do).
_LEADING_MARKER_RE = re.compile(r"^\s*(?:\[\d{1,4}\]|\d{1,4}[.)])\s+")
# A 4-digit year — a cheap "does this look like a real reference?" test.
_YEAR_RE = re.compile(r"\b(19|20)\d{2}\b")
# The start of a BibTeX entry: "@article{key," / "@inproceedings{". Mega-records
# (a whole bibliography captured as one field) are concatenated BibTeX entries.
_BIBTEX_ENTRY_RE = re.compile(r"@[a-zA-Z]+\s*\{")
# A LaTeX \bibitem marker (the .bbl form a leading chunk sometimes carries).
_BIBITEM_RE = re.compile(r"\\bibitem\b")


def _bibliography_block(text: str) -> str:
    """Return the text following the last References/Bibliography heading, or ""."""
    if not text:
        return ""
    last = None
    for m in _BIB_HEADING_RE.finditer(text):
        last = m
    if last is None:
        return ""
    return text[last.end():]


def _looks_like_reference(entry: str) -> bool:
    """A conservative filter: long enough, and carries a year (almost every real
    reference has a publication year). Cheap, and it drops page-footer noise."""
    entry = entry.strip()
    return len(entry) >= _MIN_REFERENCE_CHARS and bool(_YEAR_RE.search(entry))


def _split_marked(block: str, marker_re: re.Pattern[str]) -> list[str]:
    """Split a block on citation markers, keeping the text between successive
    markers as one entry (the marker itself is dropped)."""
    starts = [m.start() for m in marker_re.finditer(block)]
    if len(starts) < 2:                       # need at least two to trust the scheme
        return []
    bounds = starts + [len(block)]
    out = []
    for i in range(len(starts)):
        seg = marker_re.sub(" ", block[bounds[i]:bounds[i + 1]], count=1)
        out.append(" ".join(seg.split()))     # collapse the intra-entry line breaks
    return out


def _split_generic(block: str) -> list[str]:
    """Split a reference block by the marker schemes, most reliable first:
    bracketed ``[n]`` → leading ``n.`` → blank line. Only entries that *look* like
    references (length + a year) survive."""
    entries = _split_marked(block, _BRACKET_MARKER_RE)
    if not entries:
        entries = _split_marked(block, _NUMBER_MARKER_RE)
    if not entries:
        # Unnumbered list: blank line between references is the common convention.
        entries = [" ".join(chunk.split())
                   for chunk in re.split(r"\n\s*\n", block)]
    entries = [_LEADING_MARKER_RE.sub("", e) for e in entries]
    return [e for e in entries if _looks_like_reference(e)]


def _segment_bibliography(text: str) -> list[str]:
    """Best-effort split of a full-text bibliography (found via its heading) into
    individual references."""
    block = _bibliography_block(text)
    return _split_generic(block) if block else []


def _split_blob(blob: str) -> list[str]:
    """Segment a *whole-bibliography blob* — a mega-record where the extractor
    captured many references as ONE field — into individual references.

    These blobs are concatenated **BibTeX entries** (``@article{…}@inproceedings{…}``)
    that often begin with a leading LaTeX ``\\bibitem`` / ``\\end{thebibliography}``
    chunk. So we split on BibTeX entry starts, further split any ``\\bibitem``
    section, and fall back to the marker/blank-line schemes when the blob is
    neither. Each surviving entry is a reference string the resolver can read
    (``refresolve`` already parses raw ``@type{title={…}, …}`` field syntax)."""
    entries: list[str] = []
    if _BIBTEX_ENTRY_RE.search(blob):
        for part in re.split(r"(?=@[a-zA-Z]+\s*\{)", blob):
            pieces = _BIBITEM_RE.split(part) if _BIBITEM_RE.search(part) else [part]
            entries.extend(" ".join(p.split()) for p in pieces)
    elif _BIBITEM_RE.search(blob):
        entries = [" ".join(p.split()) for p in _BIBITEM_RE.split(blob)]
    entries = [_LEADING_MARKER_RE.sub("", e) for e in entries]
    good = [e for e in entries if _looks_like_reference(e)]
    # Trust the BibTeX/\bibitem split only if it actually split; otherwise the blob
    # is marker- or blank-line-delimited — hand it to the generic schemes.
    return good if len(good) >= 2 else _split_generic(blob)


def references_for(paper: "Paper", *, mined: Optional[list[str]] = None) -> list[str]:
    """The raw reference strings for ``paper``, from the best channel available.

    ``mined`` is the caller's pre-harvested references for this paper (e.g. the
    ``bibtex`` lines from ``citation_map.json``, keyed by citing id). When given
    and non-empty they are used directly; otherwise we segment the paper's own
    ``full_text`` bibliography. An entry over the resolver's char cap is not a
    reference — it is a *whole bibliography* captured as one field (a mega-record),
    so instead of dropping it we **segment it into its individual references**
    (:func:`_split_blob`) and resolve those. The list is deduped and capped so a
    pathological input can't explode the resolve stage.
    """
    if mined:
        refs = list(dict.fromkeys(r.strip() for r in mined if r and r.strip()))
    else:
        refs = _segment_bibliography(getattr(paper, "full_text", "") or "")
    out: list[str] = []
    for r in refs:
        if len(r) <= REFERENCE_CHAR_CAP:
            out.append(r)
        else:
            out.extend(_split_blob(r))         # expand a whole-bibliography blob
    out = list(dict.fromkeys(r for r in out if r and len(r) <= REFERENCE_CHAR_CAP))
    return out[:_MAX_REFERENCES]
