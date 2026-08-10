#!/usr/bin/env python3
"""Compare the enriched CITATION graph against the Cartographer's SEMANTIC graph.

Two graphs over the same corpus answer different questions:
  * citation graph (paper->paper FACTS): who cites whom, stamped with intent /
    support / priority  (experiments/edge_quality/out/citations_*.json)
  * semantic graph (contribution->contribution ASSERTIONS): supports / builds_on /
    refines / contradicts  (data/prior-core-v0.2/contributions_core_consensus.json)

We roll the semantic graph up to paper pairs and intersect with the citation
pairs, then cross-tab citation intent/support against the semantic relation on
the overlap. Writes:
  * out/graph_overlap.md    — the human-readable report
  * out/graph_overlap.json  — rolled-up semantic paper-edges (reused by gen_intent_view.py)

Zero LLM cost — pure set arithmetic. Usage: python experiments/edge_quality/graph_overlap.py
"""
from __future__ import annotations
import json
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EQ = ROOT / "experiments" / "edge_quality" / "out"
BUNDLE = ROOT / "data" / "prior-core-v0.2"

SEM_REL = ["supports", "builds_on", "refines", "contradicts"]
INTENTS = ["background", "uses_extends", "compares_contrasts"]
SUPPORTS = ["supports", "partial", "inconclusive", "does_not"]


def pid(cid: str) -> str:
    return cid.split("::")[0]


# Representative relation for a paper-pair when a SINGLE label is unavoidable
# (the viz's one dashed line): pick by SEVERITY, not frequency, so a rare
# high-value relation (contradicts) is never outvoted by a pile of `supports`,
# and there is no arbitrary frequency tiebreak. Lower rank wins.
RANK = {"contradicts": 0, "refines": 1, "builds_on": 2, "supports": 3}


def rep(cnt: Counter) -> str:
    return min(cnt, key=lambda r: (RANK.get(r, 9), -cnt[r]))


# ── load ────────────────────────────────────────────────────────────────────
sem = json.loads((BUNDLE / "contributions_core_consensus.json").read_text(encoding="utf-8"))["edges"]
cit = json.loads((EQ / "citations_intent.json").read_text(encoding="utf-8"))["edges"]
typ = {(e["citing_id"], e["cited_id"]): e
       for e in json.loads((EQ / "citations_typed.json").read_text(encoding="utf-8"))["edges"]}

# ── roll semantic contribution-edges up to paper pairs ───────────────────────
sem_pairs: dict[frozenset, Counter] = defaultdict(Counter)   # unordered pair -> relation counts
sem_dir: dict[tuple, Counter] = defaultdict(Counter)         # directed pair -> relation counts
sem_meta: dict[frozenset, dict] = defaultdict(lambda: {"trust": [], "evidence": []})
for e in sem:
    a, b = pid(e["src"]), pid(e["dst"])
    if a == b:
        continue
    fp = frozenset((a, b))
    sem_pairs[fp][e["relation"]] += 1
    sem_dir[(a, b)][e["relation"]] += 1
    sem_meta[fp]["trust"].append(e.get("trust", 0.5))
    if e.get("evidence"):
        sem_meta[fp]["evidence"].append((e["relation"], e["evidence"]))

# ── citation paper edges (directed + enriched) ───────────────────────────────
cit_dir: dict[tuple, dict] = {}
cit_pairs: dict[frozenset, dict] = {}
for e in cit:
    a, b = e["citing_id"], e["cited_id"]
    t = typ.get((a, b), {})
    rec = {"intent": e["intent"], "support": t.get("support", ""), "priority": t.get("priority", "")}
    cit_dir[(a, b)] = rec
    cit_pairs[frozenset((a, b))] = rec

S, C = set(sem_pairs), set(cit_pairs)
both = S & C

# ── cross-tabs on the overlap ────────────────────────────────────────────────
# PRESENCE-based: a pair counts toward EVERY relation it carries (not a single
# collapsed label), so mixed pairs — e.g. a contradicts hiding under supports —
# are never washed out. Row totals count distinct pairs; a pair with k relation
# types adds to k cells, so cells can sum past the row total (that's the point).
ct_intent = defaultdict(Counter)       # presence: intent -> {relation: #pairs carrying it}
ct_support = defaultdict(Counter)
crow_pairs = defaultdict(int)          # intent -> distinct pairs (row total)
srow_pairs = defaultdict(int)
for fp in both:
    it = cit_pairs[fp]["intent"]
    sv = cit_pairs[fp]["support"]
    crow_pairs[it] += 1
    if sv:
        srow_pairs[sv] += 1
    for rel in sem_pairs[fp]:          # each DISTINCT relation type present
        ct_intent[it][rel] += 1
        if sv:
            ct_support[sv][rel] += 1


# ── collapse-loss diagnostics (how much a single-label rollup would hide) ─────
def dom_freq(cnt: Counter) -> str:
    return cnt.most_common(1)[0][0]


def diag(keys):
    nedges = [sum(sem_pairs[k].values()) for k in keys]
    ntypes = [len(sem_pairs[k]) for k in keys]
    ties = sum(1 for k in keys
               for c in [sem_pairs[k].most_common()]
               if len(c) > 1 and c[0][1] == c[1][1])
    return {"n": len(keys), "mean_edges": sum(nedges) / len(keys), "max_edges": max(nedges),
            "multi_edge": sum(1 for n in nedges if n > 1), "multi_type": sum(1 for t in ntypes if t > 1),
            "freq_ties": ties, "dist": dict(sorted(Counter(nedges).items()))}


diag_all = diag(list(sem_pairs))
diag_ov = diag(list(both))
# the pairs where a single collapsed label would actually mislead (>1 distinct type)
mixed = sorted(((cit_pairs[fp]["intent"], dict(sem_pairs[fp])) for fp in both
                if len(sem_pairs[fp]) > 1), key=lambda x: x[0])
# high-value: pairs carrying a contradicts that a FREQUENCY-dominant would bury under supports
contra_hidden = [(cit_pairs[fp]["intent"], dict(sem_pairs[fp])) for fp in both
                 if "contradicts" in sem_pairs[fp] and dom_freq(sem_pairs[fp]) != "contradicts"]

# ── direction agreement on the overlap ───────────────────────────────────────
dir_match = dir_rev = 0
for fp in both:
    a, b = tuple(fp)
    cd = (a, b) if (a, b) in cit_dir else (b, a)
    fwd = sum(sem_dir[cd].values())
    rev = sum(sem_dir[(cd[1], cd[0])].values())
    if fwd >= rev:
        dir_match += 1
    else:
        dir_rev += 1


def table(rowlabels, rows: dict, row_pairs: dict, cols=SEM_REL) -> str:
    """Presence cross-tab: cell = # pairs (of this intent/support) carrying ≥1
    edge of that relation; % is of the row's distinct-pair count. A pair with
    multiple relation types appears in multiple cells, so cells may sum > pairs."""
    head = "| rows ↓ / cols → | " + " | ".join(cols) + " | pairs |"
    sep = "|" + "---|" * (len(cols) + 2)
    out = [head, sep]
    for r in rowlabels:
        cnts = rows.get(r, Counter())
        base = row_pairs.get(r, 0)
        cells = []
        for c in cols:
            n = cnts.get(c, 0)
            pct = f" ({n/base:.0%})" if base else ""
            cells.append(f"{n}{pct}")
        out.append(f"| **{r}** | " + " | ".join(cells) + f" | {base} |")
    return "\n".join(out)


# ── feasibility numbers for the stamped/unstamped judge task ──────────────────
sem_cross = [e for e in sem if pid(e["src"]) != pid(e["dst"])]
stamped = sum(1 for e in sem_cross if frozenset((pid(e["src"]), pid(e["dst"]))) in C)
contra_edges = [e for e in sem_cross if e["relation"] == "contradicts"]
contra_stamped = sum(1 for e in contra_edges if frozenset((pid(e["src"]), pid(e["dst"]))) in C)
contra_pairs = {fp for fp, cnt in sem_pairs.items() if "contradicts" in cnt}

rel_counts = Counter(e["relation"] for e in sem_cross)

# ── report ───────────────────────────────────────────────────────────────────
md = f"""# Citation graph vs. semantic graph — overlap analysis

*Generated by `experiments/edge_quality/graph_overlap.py` (zero LLM cost).*

Prior holds two graphs over the same 152-paper corpus that answer different questions:

| | citation graph (this work) | semantic graph (Cartographer) |
|---|---|---|
| unit | paper → paper | contribution → contribution |
| nature | **fact** — X cites Y (mined from arXiv `.bbl`/OpenAlex) | **assertion** — LLM's reading of how two ideas relate |
| labels | intent · support · priority | {" · ".join(SEM_REL)} |
| source | `out/citations_*.json` | `data/prior-core-v0.2/contributions_core_consensus.json` |

Method: split each contribution id on `::` to roll the {len(sem_cross)} cross-paper
semantic edges up to **{len(sem_pairs)} paper-pairs**, then intersect with the
**{len(cit_pairs)} citation paper-pairs**. A paper-pair can carry several
contribution→contribution edges, so the cross-tabs below are **presence-based**:
a pair counts toward *every* relation type it carries — nothing is collapsed to a
single "dominant" label that could bury a rare relation (§4 quantifies why this
matters). **Naming trap:** citation *support* ("does the citee's abstract back the
local claim?") ≠ semantic *supports* ("these two contributions corroborate each
other?") — same word, different question.

## 1. Overlap (unordered paper-pairs)

| region | pairs |
|---|---|
| semantic only | {len(S - C)} |
| citation only | {len(C - S)} |
| **both** | **{len(both)}** |

The graphs are **largely complementary** — only {len(both)} pairs are shared.
Expected: the citation graph misses papers with no LaTeX source, and the semantic
graph adds BM25 text-neighbour pairs that were never cited.

Semantic relation mix (cross-paper contribution-edges): {" · ".join(f"{k} {rel_counts[k]}" for k in SEM_REL)} —
**{rel_counts['supports'] / len(sem_cross):.0%} are `supports`**, so the semantic
graph is heavily corroborative and rarely fires `contradicts`.

## 2. Citation **intent** × semantic relation *presence* (on the {len(both)} shared pairs)

Cell = # shared pairs of that intent carrying ≥1 semantic edge of that relation
(% of the row's pairs). Rows can sum past 100% — {diag_ov['multi_type']} pairs carry
more than one relation type.

{table(INTENTS, ct_intent, crow_pairs)}

## 3. Citation **support** × semantic relation *presence* (on the shared pairs)

{table(SUPPORTS, ct_support, srow_pairs)}

## 4. How much does the paper-pair rollup hide?

You asked the right question: does collapsing many contribution-edges onto one
paper-pair throw away signal? Measured on the {diag_ov['n']} shared pairs
(all {diag_all['n']} pairs in parentheses):

| | overlap | all pairs |
|---|---|---|
| mean contribution-edges / pair | {diag_ov['mean_edges']:.2f} | {diag_all['mean_edges']:.2f} |
| max on one pair | {diag_ov['max_edges']} | {diag_all['max_edges']} |
| pairs with **>1 edge** | {diag_ov['multi_edge']} ({diag_ov['multi_edge']/diag_ov['n']:.0%}) | {diag_all['multi_edge']} ({diag_all['multi_edge']/diag_all['n']:.0%}) |
| pairs with **>1 distinct relation type** | {diag_ov['multi_type']} ({diag_ov['multi_type']/diag_ov['n']:.0%}) | {diag_all['multi_type']} ({diag_all['multi_type']/diag_all['n']:.0%}) |
| pairs where a *frequency*-dominant would be an arbitrary **tie** | {diag_ov['freq_ties']} ({diag_ov['freq_ties']/diag_ov['n']:.0%}) | {diag_all['freq_ties']} ({diag_all['freq_ties']/diag_all['n']:.0%}) |

So most multi-edge pairs repeat the *same* relation — only {diag_ov['multi_type']}
shared pairs are genuinely mixed. But those are the ones that matter: **{len(contra_hidden)}
shared pairs carry a `contradicts` that a frequency-dominant rollup would bury under
`supports`.** That is why (a) the cross-tabs above are presence-based (count every
type), and (b) the overlay viz picks its single dashed-line colour by **severity**
(`contradicts` > `refines` > `builds_on` > `supports`), never by frequency — so a
`contradicts` is never hidden and there is no arbitrary tiebreak.

The {diag_ov['multi_type']} genuinely-mixed shared pairs, by intent:

{chr(10).join(f"- `{it}` — " + " · ".join(f"{r}×{n}" for r, n in sorted(rels.items(), key=lambda x: -x[1])) for it, rels in mixed) if mixed else "- (none)"}

## 5. Direction agreement (on the shared pairs)

Citation direction (citing→cited) agrees with the heavier semantic direction in
**{dir_match}** pairs, disagrees in **{dir_rev}** — consistent with the known
result that the model's `builds_on`/`refines` arrow is noisy; citation direction
is the more reliable orientation.

## 6. Findings

1. **The two graphs are complementary, not redundant** ({len(both)} shared of
   {len(S | C)} total pairs). A combined view gains coverage from both.
2. **The semantic graph washes out the distinctions the intent axis makes.** It is
   {rel_counts['supports'] / len(sem_cross):.0%} `supports`; only
   {ct_intent['compares_contrasts'].get('contradicts', 0)} of the
   {crow_pairs['compares_contrasts']} shared `compares_contrasts` pairs carry any
   `contradicts` semantic edge. The contrast/critique signal your intent axis
   captures is precisely what the semantic graph is missing — the payoff the
   onboarding predicted (intent as a prior to fix the noisiest relation).
3. **The rollup is mostly safe but not entirely** (§4): {diag_ov['multi_type']}/{diag_ov['n']}
   shared pairs are genuinely mixed, and {len(contra_hidden)} hide a `contradicts` —
   handled by presence counting + severity colour, not frequency.
4. **Citation direction is the cleaner orientation** ({dir_match} vs {dir_rev}).

## 7. Feasibility note — stamped-vs-unstamped judge task

"Stamped" = a semantic edge whose paper-pair also has a citation.

| | count |
|---|---|
| semantic cross-paper contribution-edges | {len(sem_cross)} |
| — stamped (paper-pair has a citation) | {stamped} |
| — unstamped | {len(sem_cross) - stamped} |
| `contradicts` edges | {len(contra_edges)} |
| — **stamped `contradicts`** | **{contra_stamped}** |
| `contradicts` paper-pairs | {len(contra_pairs)} |
| — stamped | {len(contra_pairs & C)} |

The overall correct%-lift comparison ({stamped} stamped vs {len(sem_cross) - stamped}
unstamped) is **powered**. The headline **contradicts-precision** lift is **not**
(n={contra_stamped}; CI ≈ ±25pp) — not worth the Opus judge budget on Pro.
"""

(EQ / "graph_overlap.md").write_text(md, encoding="utf-8")

# rolled-up semantic paper-edges for the overlay viz
sem_out = []
for fp, cnts in sem_pairs.items():
    a, b = sorted(fp)
    tr = sem_meta[fp]["trust"]
    sem_out.append({
        "a": a, "b": b, "rel": rep(cnts), "relations": dict(cnts), "n": sum(cnts.values()),
        "n_types": len(cnts), "mixed": len(cnts) > 1,
        "trust": round(sum(tr) / len(tr), 2) if tr else 0.5,
        "evidence": sem_meta[fp]["evidence"][:4],
        "both": fp in C,
    })
(EQ / "graph_overlap.json").write_text(json.dumps({"sem_edges": sem_out}, ensure_ascii=False), encoding="utf-8")

print("wrote", EQ / "graph_overlap.md")
print("wrote", EQ / "graph_overlap.json", f"({len(sem_out)} semantic paper-edges)")
print(f"overlap: both={len(both)} sem-only={len(S - C)} cit-only={len(C - S)}")
print(f"stamped semantic edges: {stamped}/{len(sem_cross)} · stamped contradicts: {contra_stamped}/{len(contra_edges)}")
