"""citelinks — resolve papers' references into intra-corpus ``cites`` edges.

The live-ingestion stage of the edge_quality milestone. It *complements*
:meth:`prior.atlas.Atlas.link_citations`, which only draws a ``cites`` edge when
OpenAlex already handed us a ``referenced_works`` id that happens to be in the
corpus. That channel is silent for the papers OpenAlex under-populates (arXiv
preprints carry 0 references; ~2/3 of this corpus's papers have none) — so this
stage recovers those edges from the reference *text* instead:

    paper's references ──refextract──▶ raw strings ──refresolve──▶ canonical id
                                                    ──map_to_corpus──▶ Prior node id
                                                                       └─▶ `cites` edge

Two properties matter for trust:

* **Additive, never destructive.** We only ADD edges, and only to nodes the
  atlas already holds. Every resolved edge is deduped against the edges
  ``link_citations`` already drew, so turning this stage on can only grow the
  citation graph, never rewrite it.
* **Provenance-tagged.** A ``referenced_works`` edge is a hard fact
  (``confidence=1.0``); a resolved edge is softer and carries *how* it was
  matched — ``evidence="resolved:<method>"`` and ``confidence=<resolver score>``
  — so a downstream consumer can weight or filter the resolved tier.

Fail-soft: the resolver hits the network and needs the optional ``[resolve]``
dependency. If it isn't installed (or anything else goes wrong) the stage logs a
line and returns 0 — a build without ``[resolve]`` behaves exactly as before.

Known limitation (tracked, corpus-side fix): when two corpus nodes share a
normalized title (a duplicate that slipped into the corpus), a title-only match
can attach to the wrong twin. The fix is corpus dedup, not an adapter hack; until
then this stage inherits ``CorpusIndex``'s first-writer-wins choice. See
``PORTING_HANDOVER.md`` §edge-cases.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from .models import Edge
from .sources import openalex, refextract, semanticscholar
from .sources.refresolve import CorpusIndex, map_to_corpus, resolve_reference

if TYPE_CHECKING:
    from .atlas import Atlas


def _build_default_resolver(progress) -> Optional[object]:
    """The shared network resolver, or ``None`` if ``[resolve]`` isn't installed.

    Built once here (not per reference) so a missing dependency degrades the
    whole stage to a no-op instead of raising on the first reference.
    """
    try:
        from .sources.refresolve import _default_resolver
        return _default_resolver()
    except Exception as e:  # noqa: BLE001 — optional dep / settings; degrade to no-op
        progress(f"      citelinks: resolver unavailable ({e}); skipping "
                 f"(install .[resolve] to enable)")
        return None


def resolve_and_link(atlas: "Atlas", *, extra_refs: Optional[dict[str, list[str]]] = None,
                     resolver=None, progress=print) -> int:
    """Add resolver-derived ``cites`` edges to ``atlas``. Returns the count added.

    For each held paper we gather its reference strings (from ``extra_refs`` when
    the caller mined them, else the paper's full-text bibliography — see
    :func:`refextract.references_for`), resolve each to a canonical identity, and
    map it onto an existing corpus node. New, non-self, not-already-present edges
    are appended in place.

    ``extra_refs`` maps a paper id to pre-harvested reference strings (e.g. the
    ``citation_map.json`` ``bibtex`` lines keyed by citing id) — the channel used
    on corpora that ship without full text. Pass a warm ``resolver`` to reuse its
    per-source cache across the run; omit it to build the process-shared default.
    """
    extra_refs = extra_refs or {}
    r = resolver or _build_default_resolver(progress)
    if r is None:
        return 0

    index = CorpusIndex.from_papers(atlas.papers.values())
    # Seed the dedup set with the edges link_citations already drew, so the two
    # channels never double-count the same (citing, cited) pair.
    seen: set[tuple[str, str]] = {
        (e.src, e.dst) for e in atlas.edges if e.relation == "cites"
    }

    added = 0
    for pid, paper in list(atlas.papers.items()):
        refs = refextract.references_for(paper, mined=extra_refs.get(pid))
        here = 0
        for ref in refs:
            rref = resolve_reference(ref, resolver=r)
            if rref is None:
                continue
            dst = map_to_corpus(rref, index)
            if not dst or dst == pid:                 # unmapped, or a self-citation
                continue
            pair = (pid, dst)
            if pair in seen:
                continue
            seen.add(pair)
            atlas.add_edge(Edge(
                src=pid, dst=dst, relation="cites",
                evidence=f"resolved:{rref.match_method}",
                confidence=float(rref.match_score),
                source="citation", level="meta",
            ))
            here += 1
        added += here
        if here:
            progress(f"  citelinks: {paper.short_cite()}: +{here} resolved edges")
    progress(f"      citelinks: added {added} resolved cites edges")
    return added


def reconcile_incoming(atlas: "Atlas", *, max_results: int = 500, progress=print) -> int:
    """Recover edges when a citing paper's outgoing list is absent/incomplete.

    Query each canonical work's incoming OpenAlex/S2 citations, map returned
    records onto held works using Scoper's manifestation-aware matcher, and add
    only exact work-level intersections. S2 traffic remains inside its centralized
    adapter, including pacing and Retry-After handling.
    """
    from .scoper import _same_work
    papers = list(atlas.papers.values())
    seen = {(e.src, e.dst) for e in atlas.edges if e.relation == "cites"}
    added = 0
    for target in papers:
        returned: list[tuple[str, "Paper"]] = []
        oa_ids, s2_ids = [], []
        for record in target.all_manifestations():
            rid = str(record.get("id") or "")
            if rid.startswith("openalex:"):
                oa_ids.append(rid)
            if rid.startswith("arxiv:"):
                s2_ids.append("ARXIV:" + rid.split(":", 1)[1].split("v")[0])
        if not s2_ids and target.doi:
            s2_ids.append("DOI:" + target.doi.replace("https://doi.org/", ""))
        for oid in dict.fromkeys(oa_ids):
            returned.extend(("openalex", p) for p in openalex.cited_by(oid, max_results=max_results))
        for sid in dict.fromkeys(s2_ids):
            returned.extend(("semanticscholar", p)
                            for p in semanticscholar.citations(sid, max_results=max_results))
        for source, candidate in returned:
            matches = [p for p in papers if p.id != target.id and _same_work(candidate, p)]
            if len(matches) != 1:
                continue
            pair = matches[0].id, target.id
            if pair in seen:
                continue
            seen.add(pair)
            atlas.add_edge(Edge(src=pair[0], dst=pair[1], relation="cites",
                                evidence=f"incoming:{source}", confidence=1.0,
                                source="citation", level="meta"))
            added += 1
    progress(f"      citelinks: added {added} incoming-API cites edges")
    return added
