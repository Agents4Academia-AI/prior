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
from dataclasses import dataclass
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
_PAREN_MARKER_RE = re.compile(r"(?m)^\s*\((\d{1,4})\)\s+")
# A citation marker at the very start of one entry — stripped so the entry begins
# at the author (the blank-line fallback doesn't consume markers the way the
# marker-split paths do).
_LEADING_MARKER_RE = re.compile(r"^\s*(?:\[\d{1,4}\]|\(\d{1,4}\)|\d{1,4}[.)])\s+")
# A 4-digit year — a cheap "does this look like a real reference?" test.
_YEAR_RE = re.compile(r"\b(19|20)\d{2}\b")
# The start of a BibTeX entry: "@article{key," / "@inproceedings{". Mega-records
# (a whole bibliography captured as one field) are concatenated BibTeX entries.
_BIBTEX_ENTRY_RE = re.compile(r"@[a-zA-Z]+\s*\{")
# A LaTeX \bibitem marker (the .bbl form a leading chunk sometimes carries).
_BIBITEM_RE = re.compile(r"\\bibitem\b")


@dataclass(frozen=True)
class ReferenceEntry:
    """A bibliography entry plus the marker needed to find its body citation."""

    raw: str
    label: str = ""
    marker_style: str = "unmarked"


_INLINE_BIB_HEADING_RE = re.compile(r"\b(references|bibliography|works\s+cited)\b", re.I)
_FLEX_BRACKET_MARKER_RE = re.compile(r"\[\s*(\d{1,4})\s*\]")
_FLEX_PAREN_MARKER_RE = re.compile(r"(?:^|\n)\s*\(\s*(\d{1,4})\s*\)\s*", re.M)
_AUTHOR_YEAR_START_RE = re.compile(
    r"(?<!\w)([A-Z][A-Za-z'’\-]{1,40}(?:\s+et\s+al\.?)?)\s*[([]\s*((?:19|20)\d{2}[a-z]?)\s*[)\]]"
)
_POST_BIB_SECTION_RE = re.compile(
    r"(?im)^\s*(?:appendix(?:\s+[A-Z0-9].*)?|supplementary(?:\s+(?:material|information).*)?)\s*$"
)
_NAVIGATION_RE = re.compile(
    r"(?:purchase details|change username|show more references|"
    r"references is not available|conversion report|report an issue|"
    r"view original on arxiv|copyright privacy policy)",
    re.I,
)


def _bibliography_block(text: str) -> str:
    """Return the text following the last References/Bibliography heading, or ""."""
    if not text:
        return ""
    headings = list(_BIB_HEADING_RE.finditer(text))
    last = None
    # Prefer a heading followed by repeated reference-entry signals. This avoids
    # a later appendix/prompt headed "References" displacing the real list.
    for m in reversed(headings):
        tail = text[m.end():m.end() + 2000]
        signals = (len(_FLEX_BRACKET_MARKER_RE.findall(tail))
                   + len(_FLEX_PAREN_MARKER_RE.findall(tail))
                   + len(_AUTHOR_YEAR_START_RE.findall(tail)))
        if signals >= 2:
            last = m
            break
    if last is None and headings:
        last = headings[-1]
    if last is None:
        # HTML-to-text extractors often flatten the entire document to one line.
        # Accept only late headings followed promptly by a reference-like start;
        # this avoids treating ordinary prose such as "cross references" as a
        # bibliography boundary.
        floor = int(len(text) * 0.35)
        for m in _INLINE_BIB_HEADING_RE.finditer(text, floor):
            tail = text[m.end():m.end() + 240]
            if (_FLEX_BRACKET_MARKER_RE.search(tail)
                    or _FLEX_PAREN_MARKER_RE.search(tail)
                    or _AUTHOR_YEAR_START_RE.search(tail)
                    or re.search(r"\b(?:19|20)\d{2}\b", tail)):
                last = m
        if last is None:
            return ""
    block = text[last.end():]
    # Many papers put appendices after References. Without this boundary, body
    # citations in a long appendix become apparent bibliography markers and the
    # final real reference swallows tens of thousands of characters.
    if end := _POST_BIB_SECTION_RE.search(block):
        block = block[:end.start()]
    return block


def _entry_records(block: str) -> list[ReferenceEntry]:
    """Segment common numbered and author-year bibliographies, including flat HTML."""
    # Prefer a convincing small, increasing numeric sequence before author-year.
    # Otherwise a wrapped title ending in "Discovery (2025)" can be mistaken for
    # an author/year boundary and swallow several real [n] entries (QUASAR case).
    numeric = list(_FLEX_BRACKET_MARKER_RE.finditer(block))
    if len(numeric) < 2 or numeric[0].start() >= 300:
        numeric = list(_FLEX_PAREN_MARKER_RE.finditer(block))
    nums = [int(m.group(1)) for m in numeric]
    convincing_numeric = (len(nums) >= 3 and nums[0] <= 5
                           and sum(b > a for a, b in zip(nums, nums[1:]))
                           >= len(nums) - 2)
    if convincing_numeric:
        out = []
        for i, m in enumerate(numeric):
            end = numeric[i + 1].start() if i + 1 < len(numeric) else len(block)
            raw = " ".join(block[m.end():end].split())
            if _looks_like_marked_reference(raw):
                out.append(ReferenceEntry(raw, m.group(1), "numeric"))
        if len(out) >= 2:
            return out

    starts = list(_AUTHOR_YEAR_START_RE.finditer(block))
    if len(starts) >= 2 and starts[0].start() < 300:
        out = []
        for i, m in enumerate(starts):
            end = starts[i + 1].start() if i + 1 < len(starts) else len(block)
            raw = " ".join(block[m.start():end].split())
            if _looks_like_marked_reference(raw):
                out.append(ReferenceEntry(raw, f"{m.group(1)}|{m.group(2)}", "author_year"))
        if len(out) >= 2:
            return out

    marker_style = "numeric"
    markers = numeric
    if len(markers) < 2 or markers[0].start() >= 300:
        markers = list(_FLEX_PAREN_MARKER_RE.finditer(block))
    # A numeric bibliography should start near the block boundary and contain an
    # increasing run. This rejects bracketed years and incidental body citations.
    if len(markers) >= 2 and markers[0].start() < 300:
        nums = [int(m.group(1)) for m in markers]
        run = sum(b > a for a, b in zip(nums, nums[1:]))
        if run >= min(2, len(nums) - 1):
            out = []
            for i, m in enumerate(markers):
                end = markers[i + 1].start() if i + 1 < len(markers) else len(block)
                raw = " ".join(block[m.end():end].split())
                if _looks_like_marked_reference(raw):
                    out.append(ReferenceEntry(raw, m.group(1), marker_style))
            if len(out) >= 2:
                return out

    return [ReferenceEntry(raw) for raw in _split_generic(block)]


def reference_entries(text: str) -> list[ReferenceEntry]:
    """Extract structured bibliography entries from arbitrary cached full text."""
    block = _bibliography_block(text)
    return _entry_records(block)[:_MAX_REFERENCES] if block else []


def bibliography_status(text: str) -> str:
    """Machine-readable reason a bibliography is or is not usable.

    This lets acquisition retry another representation instead of silently
    treating an abstract, truncated PDF, or unsupported layout as zero refs.
    """
    if not text:
        return "text_unavailable"
    entries = reference_entries(text)
    if entries and any(not _NAVIGATION_RE.search(entry.raw) for entry in entries):
        return "parsed"
    if len(text) < 10_000:
        return "short_or_stub"
    if not _INLINE_BIB_HEADING_RE.search(text):
        return "heading_absent"
    if not _bibliography_block(text):
        return "heading_without_reference_block"
    return "reference_block_unsegmented"


def _looks_like_reference(entry: str) -> bool:
    """A conservative filter: long enough, and carries a year (almost every real
    reference has a publication year). Cheap, and it drops page-footer noise."""
    entry = entry.strip()
    return len(entry) >= _MIN_REFERENCE_CHARS and bool(_YEAR_RE.search(entry))


def _looks_like_marked_reference(entry: str) -> bool:
    """Marked lists provide segmentation evidence, so yearless entries are safe.

    Require prose-like alphabetic content and punctuation/identifier structure to
    reject page numbers, table fragments, and navigation labels.
    """
    entry = entry.strip()
    letters = len(re.findall(r"[A-Za-z]", entry))
    return (len(entry) >= _MIN_REFERENCE_CHARS and letters >= 12
            and bool(re.search(r"[.?!:]|\b(?:doi|arxiv|https?)\b", entry, re.I)))


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
        entries = _split_marked(block, _PAREN_MARKER_RE)
    if not entries:
        # Unnumbered list: blank line between references is the common convention.
        entries = [" ".join(chunk.split())
                   for chunk in re.split(r"\n\s*\n", block)]
    entries = [_LEADING_MARKER_RE.sub("", e) for e in entries]
    return [e for e in entries if _looks_like_reference(e)]


def _segment_bibliography(text: str) -> list[str]:
    """Best-effort split of a full-text bibliography (found via its heading) into
    individual references."""
    return [entry.raw for entry in reference_entries(text)]


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
