"""Evaluation suite — the scorecard, computed over the live graph + cached reading.

Produces a structured result the /eval dashboard renders. Three gates
(see docs/EVAL.md):
  FAITHFUL — extraction/edges grounded, no hallucination
  HONEST   — abstains when it should, doesn't over-abstain
  USEFUL   — the headline task (novelty) + beats baselines

Key-free metrics run instantly; LLM metrics run on small samples (credit-free
claude-cli, ~30s/call) so the suite stays runnable. Each metric reports a status
(pass / warn / pending) against a target. Writes data/eval/results.json.

CLI:  prior eval [--data DIR] [--no-llm] [--sample N]
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from . import config, graph

_WORD = re.compile(r"[a-z0-9]+")


def _toks(s: str) -> list[str]:
    return _WORD.findall((s or "").lower())


def _overlap(span: str, source: str) -> float:
    st, so = _toks(span), set(_toks(source))
    return sum(1 for t in st if t in so) / len(st) if st else 0.0


def _metric(id, name, group, value, threshold, *, kind, detail="",
            higher_better=True, unit="rate") -> dict:
    if value is None:
        status = "pending"
    else:
        ok = (value >= threshold) if higher_better else (value <= threshold)
        status = "pass" if ok else "warn"
    return {"id": id, "name": name, "group": group, "value": value,
            "threshold": threshold, "higher_better": higher_better, "unit": unit,
            "status": status, "kind": kind, "detail": detail}


# ── key-free: graph distributions (live, for the dashboard charts) ──────────────
def graph_distributions() -> dict:
    with graph.session() as s:
        def counts(q):
            return {r[0].lower(): r[1] for r in s.run(q)}
        prov = counts("MATCH (:Contribution)-[r]->(:Contribution) "
                      "RETURN coalesce(r.source,'text') AS k, count(*) ORDER BY k")
        glob = counts("MATCH (:Contribution)-[r]->(:Contribution) "
                      "RETURN type(r) AS k, count(*) ORDER BY k")
        loc = counts("MATCH (:Claim)-[r]->(:Claim) RETURN type(r) AS k, count(*) ORDER BY k")
        ctypes = counts("MATCH (c:Claim) RETURN coalesce(c.claim_type,'?') AS k, count(*) ORDER BY k")
    return {"provenance": prov, "global_relations": glob,
            "local_relations": loc, "claim_types": ctypes}


# ── FAITHFUL ────────────────────────────────────────────────────────────────────
def faithfulness(data_dir: str) -> dict:
    """% claims whose evidence span appears in the source text (key-free)."""
    d = Path(data_dir)
    papers_f, claims_f = d / "raw" / "papers.jsonl", d / "atlas" / "claims.jsonl"
    if not (papers_f.exists() and claims_f.exists()):
        return _metric("faithfulness", "Extraction faithfulness", "faithful",
                       None, 0.95, kind="key-free",
                       detail="no cached reading at " + str(d))
    papers = {p["id"]: p for p in (json.loads(l) for l in papers_f.read_text().splitlines() if l)}
    claims = [json.loads(l) for l in claims_f.read_text().splitlines() if l]
    if not claims:
        return _metric("faithfulness", "Extraction faithfulness", "faithful", None,
                       0.95, kind="key-free", detail="no claims")
    grounded = 0
    for c in claims:
        p = papers.get(c["paper_id"], {})
        src = (p.get("full_text") or "") + " " + (p.get("abstract") or "")
        if _overlap(c.get("evidence", ""), src) >= 0.8:
            grounded += 1
    rate = grounded / len(claims)
    return _metric("faithfulness", "Extraction faithfulness", "faithful", round(rate, 3),
                   0.95, kind="key-free",
                   detail=f"{grounded}/{len(claims)} claims grounded (evidence span in source)")


def edge_precision(sample: int = 10, *, with_llm=True) -> dict:
    """LLM-judge a sample of global edges: does the labelled relation hold?"""
    if not with_llm:
        return _metric("edge_precision", "Global-edge precision", "faithful", None,
                       0.80, kind="llm", detail="skipped (--no-llm)")
    from . import llm
    with graph.session() as s:
        # Random sample across relation types (LIMIT-only skews to the dominant
        # 'mentions'); rand() gives a fairer mix of builds_on/refines/contradicts/…
        rows = s.run(
            """MATCH (a:Contribution)-[r]->(b:Contribution)
               WITH a, b, r ORDER BY rand() LIMIT $n
               RETURN type(r) AS rel, a.method AS am, a.result AS ar,
                      b.method AS bm, b.result AS br""", n=sample).data()
    if not rows:
        return _metric("edge_precision", "Global-edge precision", "faithful", None,
                       0.80, kind="llm", detail="no global edges")
    schema = {"type": "object", "properties": {"holds": {"type": "boolean"}},
              "required": ["holds"]}
    ok = 0
    for r in rows:
        out = llm.structured(
            model=config.CARTOGRAPHER_MODEL,
            system="You verify a knowledge-graph edge between two research "
                   "contributions. Given the labelled relation and both contributions, "
                   "decide whether the label is a DEFENSIBLE characterization of how "
                   "FROM relates to TO (a reader would accept it). Relations: builds_on, "
                   "refines, contradicts, contrast (alternative approach), supports, "
                   "mentions (related, no stronger link). holds=true if defensible.",
            user=(f"LABEL: {r['rel']}\nFROM: {r['am']} → {r['ar']}\n"
                  f"TO: {r['bm']} → {r['br']}"),
            schema=schema, tool_name="judge", timeout=90)
        ok += bool(out.get("holds"))
    rate = ok / len(rows)
    mix = {}
    for r in rows:
        mix[r["rel"].lower()] = mix.get(r["rel"].lower(), 0) + 1
    return _metric("edge_precision", "Global-edge precision", "faithful", round(rate, 3),
                   0.80, kind="llm",
                   detail=f"{ok}/{len(rows)} sampled edges defensible (mix: {mix})")


# ── HONEST ──────────────────────────────────────────────────────────────────────
_OFFTOPIC = ["What is the optimal interest rate for mortgage lending?",
             "How do tardigrades survive in space vacuum?",
             "What causes the aurora borealis?"]


def abstention(*, with_llm=True) -> dict:
    if not with_llm:
        return _metric("abstention", "Abstention (off-topic → not_found)", "honest",
                       None, 0.95, kind="llm", detail="skipped (--no-llm)")
    from . import agent
    ab = sum(agent.ask(q).verdict == "not_found" for q in _OFFTOPIC)
    return _metric("abstention", "Abstention (off-topic → not_found)", "honest",
                   round(ab / len(_OFFTOPIC), 3), 0.95, kind="llm",
                   detail=f"{ab}/{len(_OFFTOPIC)} off-topic questions correctly abstained")


def answer_coverage(sample: int = 4, *, with_llm=True) -> dict:
    """In-scope questions (built from real contributions) should NOT be falsely
    not_found — i.e. the system doesn't over-abstain."""
    if not with_llm:
        return _metric("answer_coverage", "In-scope coverage (not over-abstaining)",
                       "honest", None, 0.90, kind="llm", detail="skipped (--no-llm)")
    from . import agent
    nodes = graph.global_graph()["nodes"][:sample]
    if not nodes:
        return _metric("answer_coverage", "In-scope coverage (not over-abstaining)",
                       "honest", None, 0.90, kind="llm", detail="empty graph")
    answered = 0
    for k in nodes:
        q = f"What is known about: {k.get('problem') or k.get('method')}?"
        if agent.ask(q).verdict != "not_found":
            answered += 1
    return _metric("answer_coverage", "In-scope coverage (not over-abstaining)", "honest",
                   round(answered / len(nodes), 3), 0.90, kind="llm",
                   detail=f"{answered}/{len(nodes)} in-scope questions answered (not abstained)")


def hallucination(sample: int = 4, *, with_llm=True) -> dict:
    """Every cited claim in an answer must be a real node in the graph."""
    if not with_llm:
        return _metric("hallucination", "Grounding (cited ids are real)", "faithful",
                       None, 1.0, kind="llm", detail="skipped (--no-llm)")
    from . import agent
    nodes = graph.global_graph()["nodes"][:sample]
    total = real = 0
    for k in nodes:
        a = agent.ask(f"What is known about: {k.get('problem') or k.get('method')}?")
        for u in a.used:
            total += 1
            real += graph.get(u["id"]) is not None
    rate = (real / total) if total else 1.0
    return _metric("hallucination", "Grounding (cited ids are real)", "faithful",
                   round(rate, 3), 1.0, kind="llm",
                   detail=f"{real}/{total} cited claim ids exist in the graph")


# ── USEFUL ──────────────────────────────────────────────────────────────────────
def novelty_recall(sample: int = 5, *, with_llm=True) -> dict:
    """Recall proxy: for sampled contributions, has_been_solved must surface related
    work (never falsely 'not_addressed' when sibling work exists)."""
    if not with_llm:
        return _metric("novelty_recall", "Novelty recall (finds related work)", "useful",
                       None, 0.8, kind="llm", detail="skipped (--no-llm)")
    from . import agent
    nodes = graph.global_graph()["nodes"][:sample]
    hits = 0
    for k in nodes:
        res = agent.has_been_solved(k.get("problem") or k.get("method") or "")
        hits += res.verdict != "not_addressed" and bool(res.addressed_by)
    return _metric("novelty_recall", "Novelty recall (finds related work)", "useful",
                   round(hits / (len(nodes) or 1), 3), 0.8, kind="llm",
                   detail=f"{hits}/{len(nodes)} sampled problems linked to related contributions")


def temporal_holdout() -> dict:
    """Placeholder for the headline eval — build a graph from papers before year Y,
    ask whether a known contribution's problem was solved, ground truth from
    chronology + citations. Runnable offline; not run inline (expensive)."""
    return _metric("temporal_holdout", "Novelty vs temporal holdout", "useful", None,
                   0.7, kind="llm", detail="harness in evals/temporal_holdout.py (run offline)")


def calibration() -> dict:
    return _metric("calibration", "Verdict calibration (ECE)", "honest", None, 0.1,
                   kind="llm", higher_better=False, unit="ece",
                   detail="needs holdout truth + confidences (pending)")


# ── runner ──────────────────────────────────────────────────────────────────────
GATES = {"faithful": "Faithful", "honest": "Honest", "useful": "Useful"}


def run(*, data_dir: str | None = None, with_llm: bool = True, sample: int = 6,
        progress=print) -> dict:
    graph.setup_schema()
    data_dir = data_dir or str(config.DATA)
    progress("graph distributions ...")
    dist = graph_distributions()
    metrics = []
    progress("faithfulness (key-free) ..."); metrics.append(faithfulness(data_dir))
    progress("edge precision ..."); metrics.append(edge_precision(min(sample, 10), with_llm=with_llm))
    progress("hallucination ..."); metrics.append(hallucination(min(sample, 4), with_llm=with_llm))
    progress("abstention ..."); metrics.append(abstention(with_llm=with_llm))
    progress("answer coverage ..."); metrics.append(answer_coverage(min(sample, 4), with_llm=with_llm))
    progress("novelty recall ..."); metrics.append(novelty_recall(min(sample, 5), with_llm=with_llm))
    metrics.append(temporal_holdout())
    metrics.append(calibration())

    result = {"graph": graph.summary(), "distributions": dist, "metrics": metrics,
              "gates": GATES}
    out = config.DATA / "eval" / "results.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2))
    progress(f"wrote {out}")
    return result
