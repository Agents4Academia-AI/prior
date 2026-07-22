"""Tests for prior.citelinks — resolver-derived `cites` edges on the atlas.

Offline by default: a fake resolver (the same ``resolver=`` seam refresolve
exposes) stands in for the network cascade, so the stage's edge logic — mapping,
dedup against link_citations, provenance tagging, self/unmapped skipping, and the
missing-dependency no-op — is tested deterministically. One opt-in test hits the
live resolver over the citation_map fixture and is skipped unless
``PRIOR_RESOLVE_NETWORK_TEST=1``.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from prior import citelinks
from prior.atlas import Atlas
from prior.models import Paper
from prior.sources import refresolve as R


def _paper(pid, title, source="openalex", doi=None):
    # The arXiv join key comes from an `arxiv:` id prefix; Paper has no arxiv_id.
    return Paper(id=pid, source=source, title=title, abstract="", url="", doi=doi)


def _resolver(mapping):
    """Fake MultiSourceResolver: return the first resolved whose key substring is
    in the (cleaned) reference, else None — mirrors a content match."""
    def resolve(cite_key, ref):
        for needle, resolved in mapping.items():
            if needle in ref:
                return resolved
        return None
    return SimpleNamespace(resolve=resolve)


def _resolved(title="", arxiv_id="", doi="", method="title", score=0.9):
    return SimpleNamespace(match_method=method, doi=doi, arxiv_id=arxiv_id,
                           title=title, year=2024, source="openalex", match_score=score)


def _atlas(*papers):
    a = Atlas()
    for p in papers:
        a.add_paper(p)
    return a


# ── the happy path: a mined reference becomes a provenance-tagged edge ─────────
def test_resolve_and_link_adds_edge_with_provenance():
    citing = _paper("arxiv:2401.00001", "The Citing Paper", source="arxiv")
    target = _paper("openalex:W123", "A Target Paper About Agents")
    atlas = _atlas(citing, target)

    resolver = _resolver({"Target Paper About Agents":
                          _resolved(title="A Target Paper About Agents", score=0.88)})
    extra = {"arxiv:2401.00001": ["Someone. A Target Paper About Agents. 2024."]}

    n = citelinks.resolve_and_link(atlas, extra_refs=extra, resolver=resolver,
                                   progress=lambda *_: None)
    assert n == 1
    e = next(e for e in atlas.edges if e.relation == "cites")
    assert (e.src, e.dst) == ("arxiv:2401.00001", "openalex:W123")
    assert e.evidence == "resolved:title" and e.source == "citation"
    assert e.confidence == pytest.approx(0.88)


def test_resolve_and_link_dedups_against_referenced_works():
    citing = _paper("arxiv:2401.00001", "The Citing Paper", source="arxiv")
    target = _paper("openalex:W123", "A Target Paper About Agents")
    citing.referenced_works = ["openalex:W123"]
    atlas = _atlas(citing, target)
    atlas.link_citations()                       # draws the hard edge first
    assert sum(1 for e in atlas.edges if e.relation == "cites") == 1

    resolver = _resolver({"Target Paper About Agents":
                          _resolved(title="A Target Paper About Agents")})
    extra = {"arxiv:2401.00001": ["Someone. A Target Paper About Agents. 2024."]}
    n = citelinks.resolve_and_link(atlas, extra_refs=extra, resolver=resolver,
                                   progress=lambda *_: None)
    assert n == 0                                # same pair already present
    assert sum(1 for e in atlas.edges if e.relation == "cites") == 1


def test_resolve_and_link_skips_self_and_unmapped():
    citing = _paper("arxiv:2401.00001", "The Citing Paper About Agents",
                    source="arxiv")
    atlas = _atlas(citing)
    resolver = _resolver({
        "self": _resolved(title="The Citing Paper About Agents"),   # maps back to itself
        "ghost": _resolved(title="A Paper Not In The Corpus"),      # maps to nothing
    })
    extra = {"arxiv:2401.00001": ["ref about self here 2024",
                                  "ref about a ghost paper 2024"]}
    n = citelinks.resolve_and_link(atlas, extra_refs=extra, resolver=resolver,
                                   progress=lambda *_: None)
    assert n == 0
    assert not [e for e in atlas.edges if e.relation == "cites"]


def test_resolve_and_link_noop_when_dependency_missing(monkeypatch):
    # Simulate .[resolve] not installed: the default-resolver build raises, and the
    # stage must degrade to a no-op (return 0) rather than propagate.
    def boom():
        raise ImportError("No module named 'citation_verifier'")
    monkeypatch.setattr(R, "_default_resolver", boom)
    atlas = _atlas(_paper("openalex:W1", "Some Paper Title Here"))
    assert citelinks.resolve_and_link(atlas, progress=lambda *_: None) == 0
    assert not atlas.edges


# ── opt-in: live resolution over the mined fixture reconnects real orphans ──────
_FIXTURE = Path("experiments/edge_quality/out/citation_map.json")
_PAPERS = Path("data/prior-core-v0.2/papers_core.jsonl")


@pytest.mark.skipif(not os.environ.get("PRIOR_RESOLVE_NETWORK_TEST"),
                    reason="network test; set PRIOR_RESOLVE_NETWORK_TEST=1 to run")
def test_network_stage_reconnects_orphans_over_fixture():
    papers = [Paper.from_dict(json.loads(l))
              for l in _PAPERS.read_text(encoding="utf-8").splitlines() if l.strip()]
    atlas = Atlas()
    for p in papers:
        atlas.add_paper(p)
    before = sum(1 for e in atlas.edges if e.relation == "cites")

    # Group the fixture's raw bibtex by citing paper -> extra_refs channel.
    extra: dict[str, list[str]] = {}
    for rec in json.loads(_FIXTURE.read_text(encoding="utf-8")):
        extra.setdefault(rec["citing_id"], []).append(rec["bibtex"])

    added = citelinks.resolve_and_link(atlas, extra_refs=extra)
    assert added > 50                             # 250-record run resolved ~200; floor well under
    resolved = [e for e in atlas.edges if e.relation == "cites"][before:]
    # The payoff: non-arXiv OpenAlex nodes gaining an incoming citation edge.
    assert any(e.dst.startswith("openalex:") for e in resolved)
