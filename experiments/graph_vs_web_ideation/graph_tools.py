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
import re
from collections import defaultdict
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

        # cached token sets for search
        self._toks = {cid: _tok(c.get("statement", "") + " " + c.get("kind", ""))
                      for cid, c in self.contribs.items()}

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
        scored = sorted(
            ((len(q & self._toks[cid]), cid) for cid in self.contribs),
            key=lambda t: t[0], reverse=True)
        out = []
        for score, cid in scored[:k]:
            if score == 0:
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
