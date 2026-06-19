"""Orchestration: topic -> ingest -> read -> map -> saved atlas.

Each stage caches to disk so they can be run and re-run independently (ingest is
network-bound; read/map are LLM-bound and the expensive part).
"""

from __future__ import annotations

import json
from pathlib import Path

from . import cartographer, config, reader
from .atlas import Atlas
from .models import Claim, Paper
from .sources import arxiv, openalex


def _papers_path() -> Path:
    return config.RAW / "papers.jsonl"


def _claims_path() -> Path:
    return config.ATLAS / "claims.jsonl"


def expand_references(papers: list[Paper], *, hops: int = 1, cap: int = 200,
                      progress=print) -> list[Paper]:
    """Walk citation edges backward: fetch the OpenAlex works the given papers
    reference, adding them to the corpus. This is how the atlas reaches an idea's
    true origins (e.g. 1989) that keyword search — bound by current terminology —
    never surfaces. Expanded papers enrich the citation graph; those without
    abstracts are simply skipped by the Reader."""
    have: dict[str, Paper] = {p.id: p for p in papers}
    frontier = list(papers)
    for hop in range(hops):
        wanted = [ref for p in frontier for ref in p.referenced_works
                  if ref.startswith("openalex:") and ref not in have]
        wanted = list(dict.fromkeys(wanted))
        if not wanted:
            break
        room = cap - len(have)
        if room <= 0:
            break
        fetched = openalex.fetch_many(wanted[:room])
        new = [p for pid, p in fetched.items() if pid not in have]
        for p in new:
            have[p.id] = p
        progress(f"  hop {hop + 1}: +{len(new)} cited works (corpus now {len(have)})")
        frontier = new
    return list(have.values())


def ingest(topic: str, *, max_papers: int | None = None,
           use_arxiv: bool = True, cite_hops: int = 0,
           cap: int = 200, progress=print) -> list[Paper]:
    """Fetch papers for a topic from primary sources and cache them.
    `cite_hops > 0` expands backward along citations to reach origins."""
    config.ensure_dirs()
    n = max_papers or config.DEFAULT_MAX_PAPERS
    papers: dict[str, Paper] = {}
    for p in openalex.search(topic, max_papers=n):
        papers[p.id] = p
    if use_arxiv:
        for p in arxiv.search(topic, max_papers=max(4, n // 4)):
            papers.setdefault(p.id, p)
    out = list(papers.values())
    if cite_hops > 0:
        out = expand_references(out, hops=cite_hops, cap=cap, progress=progress)
    with _papers_path().open("w") as f:
        for p in out:
            f.write(json.dumps(p.to_dict()) + "\n")
    return out


def load_papers() -> list[Paper]:
    path = _papers_path()
    if not path.exists():
        return []
    return [Paper.from_dict(json.loads(line)) for line in path.read_text().splitlines() if line]


def read_all(papers: list[Paper], *, model: str | None = None,
             progress=print) -> list[Claim]:
    """Run Reader over every paper, caching claims as we go."""
    config.ensure_dirs()
    claims: list[Claim] = []
    with _claims_path().open("w") as f:
        for i, p in enumerate(papers, 1):
            try:
                cs = reader.read(p, model=model)
            except Exception as e:  # noqa: BLE001 — one bad paper shouldn't sink the run
                progress(f"  [{i}/{len(papers)}] {p.short_cite()}: ERROR {e}")
                continue
            for c in cs:
                f.write(json.dumps(c.to_dict()) + "\n")
            claims.extend(cs)
            progress(f"  [{i}/{len(papers)}] {p.short_cite()}: {len(cs)} claims")
    return claims


def _contributions_path() -> Path:
    return config.ATLAS / "contributions.json"


def extract_contributions(papers: list[Paper], *, limit: int | None = None,
                          model: str | None = None, relate: bool = True,
                          resume: bool = True, progress=print) -> list[dict]:
    """Run the Contribution agent over primary papers (reviews skipped), using
    full text. Caches to data/atlas/contributions.json.

    Resumable: each paper's result is flushed to contributions.partial.jsonl as
    it completes, and a restart skips papers already processed — so a long
    unattended run that crashes loses at most one paper, not the whole batch."""
    from . import contributor, fulltext
    from .sources import looks_like_review
    config.ensure_dirs()
    todo = [p for p in papers if not (p.is_review or looks_like_review(p.title))]
    skipped = len(papers) - len(todo)
    if limit:
        todo = todo[:limit]
    progress(f"  {len(todo)} primary papers ({skipped} reviews skipped)")

    partial = _contributions_path().parent / "contributions.partial.jsonl"
    done: dict[str, object] = {}
    if resume and partial.exists():
        for line in partial.read_text().splitlines():
            if line:
                r = json.loads(line)
                done[r["paper_id"]] = r["result"]
        progress(f"  resuming: {len(done)} papers already processed")

    out: list[dict] = []
    no_fulltext: list[str] = []
    with partial.open("a") as fh:
        for i, p in enumerate(todo, 1):
            if p.id in done:                       # already processed — reuse
                res = done[p.id]
                if res == "NO_FULLTEXT":
                    no_fulltext.append(p.id)
                else:
                    out.extend(res)                # type: ignore[arg-type]
                continue
            try:
                ft = fulltext.fetch(p)
                if not ft:                 # full-text-only: never use the abstract
                    no_fulltext.append(p.id)
                    fh.write(json.dumps({"paper_id": p.id, "result": "NO_FULLTEXT"}) + "\n")
                    fh.flush()
                    progress(f"  [{i}/{len(todo)}] {p.short_cite()}: SKIPPED (no full text)")
                    continue
                cs = contributor.extract(p, ft, model=model)
            except Exception as e:  # noqa: BLE001 — one paper shouldn't sink the run
                progress(f"  [{i}/{len(todo)}] {p.short_cite()}: ERROR {e}")
                continue                            # not flushed → retried next run
            out.extend(cs)
            fh.write(json.dumps({"paper_id": p.id, "result": cs}) + "\n")
            fh.flush()
            progress(f"  [{i}/{len(todo)}] {p.short_cite()}: {len(cs)} contributions")
    edges: list[dict] = []
    if relate:
        progress("  relating contributions across papers ...")
        edges = _relate_contribs(out, model=model)
        progress(f"  {len(edges)} cross-contribution relations")
    _contributions_path().write_text(json.dumps(
        {"contributions": out, "edges": edges, "skipped_no_fulltext": no_fulltext},
        indent=2))
    if no_fulltext:
        progress(f"  {len(no_fulltext)} papers skipped (no full text): "
                 f"{', '.join(no_fulltext)}")
    return out


def _relate_contribs(contribs: list[dict], *, model: str | None = None) -> list[dict]:
    """Typed relations between contributions across papers (reuses Cartographer).
    This is what gives the contributions graph cross-paper 'cross-talk'."""
    from . import cartographer
    claims = [Claim(id=c["id"], paper_id=c["paper_id"], text=c["statement"],
                    claim_type=c.get("kind", "other")) for c in contribs]
    return [e.to_dict() for e in cartographer.relate_claims(claims, model=model)]


def contributions_atlas() -> Atlas:
    """An atlas whose nodes are the standalone *contributions* (primary lit only)
    + their cross-paper relations — so Navigator can answer over the final
    contributions graph rather than the raw claims atlas."""
    from .models import Claim, Edge
    base = Atlas.load(config.ATLAS / "atlas.json")
    data = json.loads(_contributions_path().read_text())
    a = Atlas()
    a.topic = (base.topic or "") + " — contributions"
    for pid in {c["paper_id"] for c in data["contributions"]}:
        if pid in base.papers:
            a.add_paper(base.papers[pid])
    for c in data["contributions"]:
        a.add_claim(Claim(id=c["id"], paper_id=c["paper_id"], text=c["statement"],
                          claim_type=c.get("kind", "other"), evidence=c.get("quote", "")))
    for e in data.get("edges", []):
        a.add_edge(Edge(e["src"], e["dst"], e["relation"], e.get("evidence", ""),
                        e.get("confidence", 0.6)))
    return a


def relate_contributions(*, model: str | None = None, progress=print) -> list[dict]:
    """Add cross-contribution relations to an existing contributions.json (no
    re-extraction)."""
    data = json.loads(_contributions_path().read_text())
    edges = _relate_contribs(data.get("contributions", []), model=model)
    data["edges"] = edges
    _contributions_path().write_text(json.dumps(data, indent=2))
    progress(f"{len(edges)} cross-contribution relations")
    return edges


_RELATE_SYS = """You relate research contributions. Given a numbered list of
standalone contributions (each tagged with its source paper), find typed
relations BETWEEN contributions from DIFFERENT papers:
  supports     — one provides evidence for / agrees with another
  contradicts  — the two are incompatible
  extends      — one builds on / generalizes the other
  refines      — one adds conditions / narrows the scope of the other
Only assert relations you can defend from the statements themselves. Skip pairs
from the same paper. Refer to contributions by their numbers."""

_RELATE_SCHEMA = {
    "type": "object",
    "properties": {"relations": {"type": "array", "items": {
        "type": "object",
        "properties": {
            "a": {"type": "integer"}, "b": {"type": "integer"},
            "relation": {"type": "string",
                         "enum": ["supports", "contradicts", "extends", "refines"]},
            "reason": {"type": "string"},
        },
        "required": ["a", "b", "relation", "reason"]}}},
    "required": ["relations"],
}


def relate_contributions_fast(*, model: str | None = None, progress=print) -> list[dict]:
    """One-shot cross-contribution relations: a single LLM call over the whole
    (small) contribution set. Seconds instead of ~one call per contribution."""
    from . import llm
    data = json.loads(_contributions_path().read_text())
    cs = data.get("contributions", [])
    listing = "\n".join(f"[{i}] ({c['paper_id']}) {c['statement']}"
                        for i, c in enumerate(cs))
    out = llm.structured(
        model=model or config.CARTOGRAPHER_MODEL, system=_RELATE_SYS,
        user=f"CONTRIBUTIONS:\n{listing}", schema=_RELATE_SCHEMA,
        tool_name="emit_relations", max_tokens=4000)
    edges: list[dict] = []
    seen: set = set()
    for r in out.get("relations", []):
        a, b = r.get("a"), r.get("b")
        if not (isinstance(a, int) and isinstance(b, int)):
            continue
        if not (0 <= a < len(cs) and 0 <= b < len(cs)) or a == b:
            continue
        if cs[a]["paper_id"] == cs[b]["paper_id"]:
            continue
        key = frozenset({a, b})
        if key in seen:
            continue
        seen.add(key)
        edges.append({"src": cs[a]["id"], "dst": cs[b]["id"],
                      "relation": r["relation"], "evidence": r.get("reason", ""),
                      "confidence": 0.6})
    data["edges"] = edges
    _contributions_path().write_text(json.dumps(data, indent=2))
    progress(f"{len(edges)} cross-contribution relations (one-shot)")
    return edges


def load_claims() -> list[Claim]:
    path = _claims_path()
    if not path.exists():
        return []
    return [Claim.from_dict(json.loads(line)) for line in path.read_text().splitlines() if line]


def build(topic: str, *, max_papers: int | None = None, relate: bool = True,
          cite_hops: int = 0, progress=print) -> Atlas:
    """Full pipeline: ingest -> read (seeds only) -> expand citations -> map -> save.

    Reader runs on the seed papers only; citation expansion enriches the graph for
    origin tracing without paying to extract claims from every cited ancestor."""
    progress(f"[1/3] ingesting '{topic}' ...")
    seeds = ingest(topic, max_papers=max_papers, cite_hops=0, progress=progress)
    progress(f"      {len(seeds)} seed papers")

    progress("[2/3] reading (seed papers -> claims) ...")
    claims = read_all(seeds, progress=progress)
    progress(f"      {len(claims)} claims")

    papers = seeds
    if cite_hops > 0:
        progress(f"      expanding citations {cite_hops} hop(s) for lineage ...")
        papers = expand_references(seeds, hops=cite_hops, progress=progress)
        with _papers_path().open("w") as f:   # cache full set so `map` stays consistent
            for p in papers:
                f.write(json.dumps(p.to_dict()) + "\n")

    progress("[3/3] mapping (claims -> atlas) ...")
    atlas = cartographer.build(papers, claims, topic=topic, relate=relate,
                               model=None)
    path = atlas.save()
    progress(f"      {atlas.summary()}")
    progress(f"saved -> {path}")
    return atlas
