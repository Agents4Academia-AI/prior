#!/usr/bin/env python3
"""Local, read-only exploration toolkit over the enriched Prior atlas.

This is the GRAPH arm's environment: the tools the LLM calls to explore the
graph (the mirror of the WEB arm's WebSearch/WebFetch). Every method reads only
local JSON — zero network, zero LLM, zero subscription cost — so you can unit-
test the whole surface by running this file directly.

Inputs (all on this branch; provenance in ../edge_quality/GRAPH_STATE_AND_NEXT_TASK.md):
  • ENRICHED SEMANTIC EDGES + CONTRIBUTIONS — the canonical v12 graph:
      experiments/edge_quality/out/canonical_semantic_candidates_enriched_evidence_v12.json
      (989 relabelled contribution pairs with relation/direction/reason; 581 contributions)
  • CITATION INTENTS (mine, 809 sites / 525 edges):
      experiments/edge_quality/out/citations_intent.json          (+ citations_typed.json for support/priority)
  • CITATION INTENTS (Klara's new substrate, 294 sites / 119 new pairs):
      experiments/edge_quality/out/citations_intent_incoming_v12_new.json
  • PAPERS: data/prior-core-v0.2/papers_core.jsonl

The two citation-intent files are disjoint at the paper-pair level, so together
they are the full 1103-site / 643-pair citation layer.
"""
from __future__ import annotations

import json
import math
import re
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EQ = ROOT / "experiments" / "edge_quality" / "out"
BUNDLE = ROOT / "data" / "prior-core-v0.2"

CANONICAL = EQ / "canonical_semantic_candidates_enriched_evidence_v12.json"
INTENTS_809 = EQ / "citations_intent.json"
TYPED_809 = EQ / "citations_typed.json"
INTENTS_294 = EQ / "citations_intent_incoming_v12_new.json"
PAPERS = BUNDLE / "papers_core.jsonl"

# Typed relations we treat as "substantive" (exclude the untyped 'related'/'none').
TYPED = ("builds_on", "refines", "contradicts", "supports")
_WORD = re.compile(r"[a-z0-9]+")


def _pid(cid: str) -> str:
    return cid.split("::")[0]


def _tok(text: str) -> set[str]:
    return set(_WORD.findall((text or "").lower()))


def _count(it) -> Counter:
    return Counter(it)


# ── lean serialisation (v3) ──────────────────────────────────────────────────
# The v2 tools returned every list row as a JSON object, which re-spelled
# "title"/"year"/"intents"/"n_sites"/"paper_id" once per row: 190 characters to
# carry ~58 characters of graph. These render one row as one line instead. The
# CONTENT is identical — this is an envelope change, not a content change.

def _fmt_cite(r: dict) -> str:
    ints = ",".join(r.get("intents") or ["untagged"])
    return f"{r['title']} ({r['year']}) [{ints} x{r['n_sites']}] {r['paper_id']}"


def _fmt_rel(e: dict) -> str:
    """'<-' means the OTHER paper does this to THIS one; '->' the reverse."""
    arrow = "->" if e.get("this_paper_is") == "src" else "<-"
    return f"{arrow} {e['relation']} | {e['other_paper']} | {e['other_contribution_id']}"


class GraphAtlas:
    """Loads the enriched atlas once and exposes read-only exploration tools."""

    def __init__(self) -> None:
        canon = json.loads(CANONICAL.read_text(encoding="utf-8"))
        self.contribs: dict[str, dict] = {c["id"]: c for c in canon["contributions"]}
        self.edges: list[dict] = canon["edges"]
        self.papers: dict[str, dict] = {
            p["id"]: p for p in (json.loads(l) for l in
                                 PAPERS.read_text(encoding="utf-8").splitlines() if l.strip())}

        # contribution id -> edges touching it (either direction)
        self.edges_by_contrib: dict[str, list[dict]] = defaultdict(list)
        for e in self.edges:
            self.edges_by_contrib[e["src"]].append(e)
            self.edges_by_contrib[e["dst"]].append(e)

        # citation layer keyed by unordered paper pair -> {citing, cited, intent, sites[]}
        self.cit_by_pair: dict[frozenset, dict] = {}
        self._load_citations()

        # paper -> # citation links touching it (for the "there is structure here" teaser)
        self.cit_count_by_paper: dict[str, int] = defaultdict(int)
        for pair in self.cit_by_pair:
            for pid in pair:
                self.cit_count_by_paper[pid] += 1

        # cached token sets for search. v2: the PAPER TITLE is folded in — v1
        # indexed only the statement, so a paper whose title words never appeared in
        # its own contribution text was unfindable by name.
        self._toks = {
            cid: _tok(" ".join([c.get("statement", ""), c.get("kind", "") or "",
                                self.papers.get(c["paper_id"], {}).get("title", "") or ""]))
            for cid, c in self.contribs.items()}
        # document frequency over that index, so scoring can down-weight the
        # stopwords and boilerplate that dominated v1's raw-overlap count
        self._df: dict[str, int] = defaultdict(int)
        for toks in self._toks.values():
            for t in toks:
                self._df[t] += 1

    # ── loading ──────────────────────────────────────────────────────────────
    def _load_citations(self) -> None:
        typed = {(e["citing_id"], e["cited_id"]): e for e in
                 json.loads(TYPED_809.read_text(encoding="utf-8"))["edges"]}
        for e in json.loads(INTENTS_809.read_text(encoding="utf-8"))["edges"]:
            a, b = e["citing_id"], e["cited_id"]
            t = typed.get((a, b), {})
            self.cit_by_pair[frozenset((a, b))] = {
                "citing": a, "cited": b, "intent": e.get("intent"),
                "support": t.get("support"), "priority": t.get("priority"),
                "origin": "callum_809",
                "sites": [{"intent": s.get("intent"), "confidence": s.get("confidence"),
                           "justification": s.get("justification"), "claim": s.get("claim")}
                          for s in e.get("sites", [])]}
        for s in json.loads(INTENTS_294.read_text(encoding="utf-8"))["sites"]:
            a, b = s["citing_id"], s["cited_id"]
            rec = self.cit_by_pair.setdefault(
                frozenset((a, b)), {"citing": a, "cited": b, "intent": None,
                                    "support": None, "priority": None,
                                    "origin": "v12_new", "sites": []})
            rec["sites"].append({"intent": s.get("intent"), "confidence": s.get("confidence"),
                                 "justification": s.get("justification"), "claim": s.get("claim")})

    # ── helpers ──────────────────────────────────────────────────────────────
    def _paper_brief(self, pid: str) -> dict:
        p = self.papers.get(pid, {})
        return {"paper_id": pid, "title": p.get("title", "?"), "year": p.get("year")}

    def _rel_summary(self, cid: str) -> dict[str, int]:
        """Typed-relation breakdown around a contribution — the teaser that tells
        the agent there is structure worth traversing (not just a degree count)."""
        counts: dict[str, int] = defaultdict(int)
        for e in self.edges_by_contrib.get(cid, []):
            if e["relation"] in TYPED:
                counts[e["relation"]] += 1
        return dict(counts)

    def _citation_between(self, pid_a: str, pid_b: str) -> dict | None:
        c = self.cit_by_pair.get(frozenset((pid_a, pid_b)))
        if not c:
            return None
        intents = sorted({s["intent"] for s in c["sites"] if s.get("intent")})
        return {"citing": c["citing"], "cited": c["cited"], "intents": intents,
                "support": c.get("support"), "priority": c.get("priority"),
                "origin": c["origin"], "n_sites": len(c["sites"])}

    # ── TOOLS (this is the surface the LLM will call) ─────────────────────────
    def overview(self) -> dict:
        """High-level map: corpus size, relation-type counts, the most-connected
        contributions, and where the contradictions are."""
        rel_counts: dict[str, int] = defaultdict(int)
        for e in self.edges:
            rel_counts[e["relation"]] += 1
        degree = {cid: len(es) for cid, es in self.edges_by_contrib.items()}
        hubs = sorted(degree, key=degree.get, reverse=True)[:10]
        # a couple of examples of EACH typed relation, so no single relation type
        # (e.g. contradicts) is over-advertised as "the" thing to look for
        rel_examples: dict[str, list[dict]] = {}
        for rel in TYPED:
            exs = [e for e in self.edges if e["relation"] == rel][:2]
            rel_examples[rel] = [
                {"src": e["src"], "dst": e["dst"],
                 "src_stmt": self.contribs.get(e["src"], {}).get("statement", "")[:100],
                 "dst_stmt": self.contribs.get(e["dst"], {}).get("statement", "")[:100]}
                for e in exs]
        cit_intents: dict[str, int] = defaultdict(int)
        for c in self.cit_by_pair.values():
            for it in {s["intent"] for s in c["sites"] if s.get("intent")}:
                cit_intents[it] += 1
        return {
            "layers": ("Two coupled layers: CONTRIBUTIONS (atomic claims/methods/"
                       "findings) connected by typed semantic RELATIONS (builds_on / "
                       "refines / contradicts / supports, each with a reason), which "
                       "were derived from the CITATIONS between the papers (each tagged "
                       "with an intent + justification). Traverse edges and citations "
                       "around a topic to see how the work connects — a single "
                       "contribution's text alone carries none of that structure."),
            "papers": len(self.papers), "contributions": len(self.contribs),
            "edges_total": len(self.edges),
            "relation_counts": dict(rel_counts),
            "citation_pairs": len(self.cit_by_pair),
            "citation_intent_pair_counts": dict(cit_intents),
            "most_connected": [{**self._paper_brief(_pid(cid)), "contribution_id": cid,
                                "degree": degree[cid],
                                "statement": self.contribs[cid]["statement"][:140]}
                               for cid in hubs],
            "relation_examples": rel_examples,
        }

    def search_contributions(self, query: str, k: int = 8) -> list[dict]:
        """Keyword search over the 581 contribution statements. Returns the best
        k matches as entry points for exploration."""
        q = _tok(query)
        if not q:
            return []
        # v2 scoring: idf-weighted overlap. v1 used the raw count of shared tokens,
        # so a natural-language question ("are there disagreements about whether
        # LLMs produce novel ideas") scored partly on 'about', 'are', 'there'.
        n_docs = max(1, len(self._toks))

        def _score(cid: str) -> float:
            ov = q & self._toks[cid]
            if not ov:
                return 0.0
            return sum(math.log(1 + n_docs / (1 + self._df.get(t, 0))) for t in ov)

        scored = sorted(((_score(cid), cid) for cid in self.contribs),
                        key=lambda t: t[0], reverse=True)
        out = []
        for score, cid in scored[:k]:
            if score <= 0:
                break
            c = self.contribs[cid]
            out.append({"contribution_id": cid, **self._paper_brief(c["paper_id"]),
                        "kind": c.get("kind"), "statement": c.get("statement", ""),
                        "relations": self._rel_summary(cid),
                        "paper_citations": self.cit_count_by_paper.get(c["paper_id"], 0)})
        return out

    def get_contribution(self, contribution_id: str) -> dict | None:
        """Full detail on one contribution: statement, kind, grounding quote, paper."""
        c = self.contribs.get(contribution_id)
        if not c:
            return None
        return {"contribution_id": contribution_id, **self._paper_brief(c["paper_id"]),
                "kind": c.get("kind"), "statement": c.get("statement"),
                "grounding_quote": c.get("quote"),
                "relations": self._rel_summary(contribution_id),
                "paper_citations": self.cit_count_by_paper.get(c["paper_id"], 0),
                "hint": ("call get_edges for the typed relations + reasons, and "
                         "get_citations for why this paper's references were cited")}

    def get_paper(self, paper_id: str) -> dict | None:
        """A paper's identity + abstract + its contributions. (No full text in this
        bundle — the grounded contributions/quotes are the body-level content.)"""
        p = self.papers.get(paper_id)
        if not p:
            return None
        contribs = [{"contribution_id": cid, "kind": c.get("kind"),
                     "statement": c.get("statement")}
                    for cid, c in self.contribs.items() if c["paper_id"] == paper_id]
        return {"paper_id": paper_id, "title": p.get("title"), "year": p.get("year"),
                "authors": p.get("authors", [])[:6], "venue": p.get("venue"),
                "url": p.get("url"), "doi": p.get("doi"),
                "abstract": p.get("abstract"), "contributions": contribs}

    def get_edges(self, contribution_id: str, include_related: bool = False) -> list[dict]:
        """The typed relationships around a contribution — the heart of the graph.
        Each edge carries the relation, its direction, the LLM's `reason`
        justification, and (if the two papers cite each other) the citation intent."""
        cid = contribution_id
        if cid not in self.contribs:
            return []
        out = []
        for e in self.edges_by_contrib.get(cid, []):
            if not include_related and e["relation"] not in TYPED:
                continue
            other = e["dst"] if e["src"] == cid else e["src"]
            oc = self.contribs.get(other, {})
            out.append({
                "neighbor_id": other, **self._paper_brief(_pid(other)),
                "neighbor_statement": oc.get("statement", ""),
                "relation": e["relation"], "direction": e.get("direction"),
                "this_is": "src" if e["src"] == cid else "dst",
                "reason": e.get("reason", ""),
                "type_confidence": e.get("type_confidence"),
                "citation": self._citation_between(_pid(cid), _pid(other)),
            })
        # typed-first, strongest relations before supports
        order = {r: i for i, r in enumerate(("contradicts", "refines", "builds_on", "supports"))}
        out.sort(key=lambda x: order.get(x["relation"], 9))
        return out

    def get_neighbors(self, contribution_id: str) -> list[dict]:
        """Brief adjacency list (typed edges only) — cheaper than get_edges when
        you just want to see where you can go next."""
        return [{"neighbor_id": e["neighbor_id"], "relation": e["relation"],
                 "title": e["title"], "statement": e["neighbor_statement"][:120]}
                for e in self.get_edges(contribution_id)]

    def get_citations(self, paper_id: str) -> dict | None:
        """Every citation link touching a paper — what it CITES and what CITES IT,
        each with the citation intent(s) (background / uses_extends / compares_contrasts),
        support, priority and #sites. This is the raw citation layer the semantic edges
        were built from; use it to walk the citation graph and see *why* papers reference
        each other, independent of the contribution edges."""
        if paper_id not in self.papers:
            return None
        cites, cited_by = [], []
        for pair, c in self.cit_by_pair.items():
            if paper_id not in pair:
                continue
            other = c["cited"] if c["citing"] == paper_id else c["citing"]
            intents = sorted({s["intent"] for s in c["sites"] if s.get("intent")})
            rec = {**self._paper_brief(other), "intents": intents,
                   "support": c.get("support"), "priority": c.get("priority"),
                   "n_sites": len(c["sites"])}
            (cites if c["citing"] == paper_id else cited_by).append(rec)
        return {"paper_id": paper_id, "title": self.papers[paper_id].get("title"),
                "cites": cites, "cited_by": cited_by}

    def citations_between(self, paper_id_a: str, paper_id_b: str) -> dict | None:
        """Full citation-intent detail between two papers (site justifications +
        passages), merging my 809 sites and the 294 new-substrate sites."""
        c = self.cit_by_pair.get(frozenset((paper_id_a, paper_id_b)))
        if not c:
            return None
        return {"citing": c["citing"], "cited": c["cited"], "origin": c["origin"],
                "support": c.get("support"), "priority": c.get("priority"),
                "sites": c["sites"]}


    # ── PAPER-LEVEL TOOLS (v2) ───────────────────────────────────────────────
    # Added 2026-08-21. The v1 surface was entirely contribution-level while every
    # research question is paper-level ("which papers build on X?"), so the agent
    # burned turns reassembling paper facts the atlas already holds. These do the
    # aggregation here, where it is free, instead of in the model's context.

    def find_paper(self, query: str, k: int = 5, min_coverage: float = 0.34) -> list[dict]:
        """Look a paper up BY NAME (title / author / venue). The v1 surface had no
        way to do this at all — an agent asked about 'The AI Scientist (Lu et al.)'
        had to hope a keyword search over contribution statements surfaced it.

        Scoring has to do three things a raw overlap count does not:
          • weight by idf, so 'hypothesis' and 'generation' do not swamp the rare
            token that actually identifies the paper;
          • penalise long titles, or 'Improving Scientific Hypothesis Generation
            with Knowledge Grounded LLMs' outranks the plain 'Hypothesis Generation
            with Large Language Models' the user actually named;
          • REFUSE to answer below `min_coverage`. Returning the nearest thing in a
            152-paper corpus for an out-of-scope query is exactly the failure the
            c01 control exists to detect, and the tool should not manufacture it.
        """
        q = _tok(query)
        if not q:
            return []
        n_docs = max(1, len(self._toks))

        def idf(t: str) -> float:
            return math.log(1 + n_docs / (1 + self._df.get(t, 0)))

        q_mass = sum(idf(t) for t in q) or 1.0
        qn = " ".join(sorted(q))
        scored = []
        for pid, p in self.papers.items():
            title = p.get("title", "") or ""
            t_toks = _tok(title)
            hay = t_toks | _tok(" ".join(
                [p.get("venue", "") or "",
                 " ".join(a if isinstance(a, str) else str(a)
                          for a in (p.get("authors") or [])[:8])]))
            ov = q & hay
            if not ov:
                continue
            coverage = sum(idf(t) for t in ov) / q_mass
            if coverage < min_coverage:
                continue
            # penalise titles that pad the match out with unrelated words
            score = coverage / (1 + 0.04 * max(0, len(t_toks) - len(ov)))
            if t_toks and t_toks <= q:            # title fully named in the query
                score += 0.5
            if qn == " ".join(sorted(t_toks)):    # exact title
                score += 1.0
            scored.append((score, pid))
        scored.sort(reverse=True)
        out = []
        for _s, pid in scored[:k]:
            n_contrib = sum(1 for c in self.contribs.values() if c["paper_id"] == pid)
            out.append({**self._paper_brief(pid), "n_contributions": n_contrib,
                        "citation_links": self.cit_count_by_paper.get(pid, 0),
                        "match_score": round(_s, 3),
                        "hint": "call paper_neighbourhood for how it connects"})
        return out

    def paper_neighbourhood(self, paper_id: str, max_items: int = 40,
                            relation: str | None = None, intent: str | None = None,
                            verbose: bool = False) -> dict | None:
        """How one paper connects: its contributions, the typed relations touching
        them, and its citations ranked by intent, with all counts precomputed.

        v3 (lean) is the default and follows four rules fixed from the data model,
        BEFORE measuring anything (see PLAN.md 2a):

          1. The envelope is not data - list rows are one line, not a JSON object
             with the same five keys re-spelled on every row.
          2. Abstracts are not part of the graph - the contribution statements are
             the distilled claim, so shipping both pays twice for one thing. The
             abstract is still one `get_paper` call away.
          3. Edges carry LABELS here; their justification prose is fetched by
             `edge_reasons`, batched, only for the edges the model actually wants.
             This is also what makes an exploration trace meaningful: the edges
             whose reasons were requested are the ones it genuinely read.
          4. Counts before lists - every count below covers ALL links. Only the
             ENUMERATION of routine `background` citations is deferred (ask for it
             with intent='background'); nothing is hidden, and the number is here.

        `relation` / `intent` filter the listings - a filter ARGUMENT rather than a
        question-shaped tool like `papers_building_on`, so 'what contradicts X' and
        'what refines X' are served by the same surface.

        `verbose=True` reproduces the v2 payload, so the two tool surfaces can be
        measured against each other on the same questions.
        """
        p = self.papers.get(paper_id)
        if not p:
            return None
        rank = {"uses_extends": 0, "compares_contrasts": 1, "background": 2}

        def roll(items: list[dict]) -> list[dict]:
            out = [{"title": c["title"], "year": c["year"], "intents": c["intents"],
                    "n_sites": c["n_sites"], "paper_id": c["paper_id"]} for c in items]
            out.sort(key=lambda r: (min([rank.get(i, 3) for i in r["intents"]] or [3]),
                                    -r["n_sites"]))
            return out

        cits = self.get_citations(paper_id) or {"cites": [], "cited_by": []}
        mine = [cid for cid, c in self.contribs.items() if c["paper_id"] == paper_id]
        edges, seen = [], set()
        for cid in mine:
            for e in self.get_edges(cid):
                key = (e["neighbor_id"], e["relation"])
                if key in seen:
                    continue
                seen.add(key)
                edges.append({"relation": e["relation"], "direction": e.get("direction"),
                              "this_paper_is": e["this_is"],
                              "other_paper": e["title"],
                              "other_paper_id": _pid(e["neighbor_id"]),
                              "other_contribution_id": e["neighbor_id"],
                              "other_statement": e["neighbor_statement"][:220],
                              "reason": (e.get("reason") or "")[:320]})
        order = {r: i for i, r in enumerate(TYPED)}
        edges.sort(key=lambda e: order.get(e["relation"], 9))
        cb, ct = roll(cits["cited_by"]), roll(cits["cites"])

        counts = {
            "n_cited_by": len(cits["cited_by"]), "n_cites": len(cits["cites"]),
            "n_typed_relations": len(edges),
            "cited_by_intents": dict(_count(i for c in cits["cited_by"]
                                            for i in (c["intents"] or ["untagged"]))),
            "cites_intents": dict(_count(i for c in cits["cites"]
                                         for i in (c["intents"] or ["untagged"]))),
            "relations": dict(_count(e["relation"] for e in edges)),
        }

        if verbose:                     # -- v2 payload, kept for the comparison --
            counts["truncated"] = max(0, max(len(edges), len(cb), len(ct)) - max_items)
            return {
                "paper": {"paper_id": paper_id, "title": p.get("title"),
                          "year": p.get("year"), "authors": (p.get("authors") or [])[:6],
                          "abstract": p.get("abstract")},
                "contributions": [{"contribution_id": c,
                                   "kind": self.contribs[c].get("kind"),
                                   "statement": self.contribs[c]["statement"]}
                                  for c in mine],
                "typed_relations": edges[:max_items],
                "cited_by": cb[:max_items], "cites": ct[:max_items],
                "counts": counts,
                "note": ("Counts cover ALL links; the lists above are capped at "
                         f"{max_items} and ranked so the substantive ones come first."),
            }

        # -- v3 lean ---------------------------------------------------------
        if relation:
            edges = [e for e in edges if e["relation"] == relation]
        if intent:
            cb = [r for r in cb if intent in (r["intents"] or [])]
            ct = [r for r in ct if intent in (r["intents"] or [])]
            deferred = 0
        else:
            # rule 4: enumerate the substantive citations, defer the routine ones
            sub = [r for r in cb if any(i != "background" for i in (r["intents"] or []))]
            deferred = len(cb) - len(sub)
            cb = sub

        shown_cb, shown_ct, shown_e = cb[:max_items], ct[:max_items], edges[:max_items]
        counts["not_listed"] = {
            "background_citations": deferred,
            "over_max_items": max(0, max(len(edges) - len(shown_e),
                                         len(cb) - len(shown_cb),
                                         len(ct) - len(shown_ct))),
        }
        note = ("Counts cover ALL links. cited_by lists the substantive citations; "
                f"{deferred} routine `background` citations are counted but not "
                "listed (pass intent='background' to enumerate them). Edge "
                "justifications are not included here - call "
                "edge_reasons(paper_id, others=[...]) for the ones you want. "
                "'<-' = the other paper does this to THIS paper.")
        return {
            "paper": {"paper_id": paper_id, "title": p.get("title"),
                      "year": p.get("year"), "authors": (p.get("authors") or [])[:6]},
            "contributions": [{"contribution_id": c,
                               "kind": self.contribs[c].get("kind"),
                               "statement": self.contribs[c]["statement"]} for c in mine],
            "typed_relations": [_fmt_rel(e) for e in shown_e],
            "cited_by": [_fmt_cite(r) for r in shown_cb],
            "cites": [_fmt_cite(r) for r in shown_ct],
            "counts": counts,
            "note": note,
        }

    def edge_reasons(self, paper_id: str, others: list[str] | None = None,
                     relation: str | None = None, max_items: int = 6) -> dict | None:
        """The justification prose behind specific edges - BATCHED, so asking for
        six reasons costs one call, not six.

        `paper_neighbourhood` deliberately returns edge labels without their
        reasons; this is where the evidence lives. `others` accepts paper_ids or
        contribution_ids as printed in that listing. With neither `others` nor
        `relation`, returns the first `max_items` edges' reasons. Reasons come
        back in FULL (median ~1,100 chars) - v2 truncated every reason to 320
        chars and shipped them all whether wanted or not; this ships the whole
        justification for the few edges that were asked for.

        Splitting labels from justifications is also what keeps the exploration
        trace honest: a paper that merely appeared in a list was delivered to the
        model, whereas an edge whose reason was pulled here was deliberately read.
        """
        if paper_id not in self.papers:
            return None
        want = {o.split("::")[0] for o in (others or [])}
        mine = [cid for cid, c in self.contribs.items() if c["paper_id"] == paper_id]
        out, seen = [], set()
        for cid in mine:
            for e in self.get_edges(cid):
                key = (e["neighbor_id"], e["relation"])
                if key in seen:
                    continue
                if relation and e["relation"] != relation:
                    continue
                if want and _pid(e["neighbor_id"]) not in want:
                    continue
                seen.add(key)
                out.append({
                    "relation": e["relation"],
                    "this_paper_is": e["this_is"],
                    "other_paper": e["title"],
                    "other_paper_id": _pid(e["neighbor_id"]),
                    "other_contribution_id": e["neighbor_id"],
                    "other_statement": e["neighbor_statement"],
                    "reason": e.get("reason") or "",
                })
        order = {r: i for i, r in enumerate(TYPED)}
        out.sort(key=lambda e: order.get(e["relation"], 9))
        missing = sorted(want - {e["other_paper_id"] for e in out}) if want else []
        return {"paper_id": paper_id, "n_returned": len(out[:max_items]),
                "n_matched": len(out), "reasons": out[:max_items],
                "no_edge_to": missing,
                "note": ("Full justification text as recorded on the edge. "
                         "`no_edge_to` lists requested papers that share no typed "
                         "relation with this one - they may still cite it.")}

    def topic_structure(self, query: str, k: int = 5, max_edges: int = 6,
                        verbose: bool = False) -> dict:
        """The topic-shaped counterpart of paper_neighbourhood: search for a topic
        and return the typed relations around the best hits IN THE SAME CALL, so
        'is there disagreement about X?' costs one call rather than a search plus
        one get_edges per hit.

        Same v3 rules as paper_neighbourhood: relations come back as labels, and
        their justification prose is fetched on request by `edge_reasons`.
        `verbose=True` reproduces the v2 payload for the surface comparison.
        """
        hits = self.search_contributions(query, k=k)
        out = []
        for h in hits:
            es = self.get_edges(h["contribution_id"])
            if verbose:
                rels = [{"relation": e["relation"], "direction": e.get("direction"),
                         "other_paper": e["title"],
                         "other_contribution_id": e["neighbor_id"],
                         "other_statement": e["neighbor_statement"][:180],
                         "reason": (e.get("reason") or "")[:280]}
                        for e in es[:max_edges]]
            else:
                rels = [_fmt_rel({"relation": e["relation"],
                                  "this_paper_is": e["this_is"],
                                  "other_paper": e["title"],
                                  "other_contribution_id": e["neighbor_id"]})
                        for e in es[:max_edges]]
            out.append({
                "contribution_id": h["contribution_id"], "title": h["title"],
                "year": h["year"], "kind": h["kind"], "statement": h["statement"],
                "relations": rels, "n_relations_total": len(es),
            })
        if verbose:
            agg = _count(r["relation"] for h in out for r in h["relations"])
        else:
            agg = _count(r.split(" | ")[0].split(" ", 1)[1]
                         for h in out for r in h["relations"])
        return {"query": query, "hits": out, "relation_mix": dict(agg),
                "note": ("relation_mix aggregates the relations shown. contradicts/"
                         "refines indicate live disagreement; supports indicates "
                         "corroboration. Justifications are not included - call "
                         "edge_reasons on a paper_id for the ones you want. "
                         "'<-' = the other paper does this to the hit."
                         if not verbose else
                         "relation_mix aggregates the relations shown. contradicts/"
                         "refines indicate live disagreement; supports indicates "
                         "corroboration. Drill in with get_edges on any "
                         "contribution_id for the full set.")}


# ── self-test (zero LLM / subscription cost) ─────────────────────────────────
if __name__ == "__main__":
    g = GraphAtlas()
    ov = g.overview()
    print("== OVERVIEW ==")
    print(f"papers={ov['papers']} contributions={ov['contributions']} "
          f"edges={ov['edges_total']} citation_pairs={ov['citation_pairs']}")
    print("relation_counts:", ov["relation_counts"])
    print("relation_examples:", {k: len(v) for k, v in ov["relation_examples"].items()})
    print("\ntop hub:", ov["most_connected"][0]["title"],
          "| degree", ov["most_connected"][0]["degree"])
    hub_cid = ov["most_connected"][0]["contribution_id"]

    print("citation intent pair counts:", ov["citation_intent_pair_counts"])

    print("\n== SEARCH 'autonomous research agent' ==")
    for r in g.search_contributions("autonomous research agent", k=3):
        print(f"  {r['contribution_id']}  [{r['kind']}] rels={r['relations']} "
              f"paper_cites={r['paper_citations']}  {r['statement'][:80]}")

    print(f"\n== EDGES around hub {hub_cid} ==")
    for e in g.get_edges(hub_cid)[:4]:
        cit = e["citation"]
        cit_s = f" | citation intents={cit['intents']}" if cit else ""
        print(f"  --{e['relation']}--> {e['neighbor_id']}{cit_s}")
        print(f"      reason: {e['reason'][:140]}")

    hub_pid = _pid(hub_cid)
    print(f"\n== CITATIONS touching {hub_pid} ==")
    gc = g.get_citations(hub_pid)
    print(f"  cites {len(gc['cites'])} papers, cited_by {len(gc['cited_by'])} papers")
    for r in (gc["cites"] + gc["cited_by"])[:4]:
        print(f"    {r['paper_id']}  intents={r['intents']} support={r['support']}")
