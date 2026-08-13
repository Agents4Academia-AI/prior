#!/usr/bin/env python3
"""Select interesting citation×semantic overlap cases for manual inspection.

For each shared paper-pair we render, side by side, everything a human needs to
judge whether the citation signal and the semantic (Cartographer) relation
*disagree*, and if so whether one is wrong or they carry complementary info:

  * the two papers (title, year, links)
  * the CITATION edge: intent / support / priority + every claim-site
    justification and the claim window (the sentence the citation sits in)
  * the SEMANTIC edge(s): each contribution→contribution relation, its evidence,
    and both contributions' statement + grounding quote

Cases are grouped by the *kind* of divergence (see CATEGORIES). Deterministic
(sorted), zero LLM cost. Writes overlap_cases.md next to this file.
"""
from __future__ import annotations
import json
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
EQ = ROOT / "experiments" / "edge_quality" / "out"
BUNDLE = ROOT / "data" / "prior-core-v0.2"
OUT = HERE / "overlap_cases.md"

PER_CATEGORY = 4  # cases rendered per divergence category


def pid(cid: str) -> str:
    return cid.split("::")[0]


# ── load ─────────────────────────────────────────────────────────────────────
papers = {p["id"]: p for p in (json.loads(l) for l in
          (BUNDLE / "papers_core.jsonl").read_text(encoding="utf-8").splitlines() if l.strip())}
g = json.loads((BUNDLE / "contributions_core_grounded.json").read_text(encoding="utf-8"))
contribs = {c["id"]: c for c in (g["contributions"] if isinstance(g, dict) else g)}
sem = json.loads((BUNDLE / "contributions_core_consensus.json").read_text(encoding="utf-8"))["edges"]
cit_intent = json.loads((EQ / "citations_intent.json").read_text(encoding="utf-8"))["edges"]
cit_typed = {(e["citing_id"], e["cited_id"]): e
             for e in json.loads((EQ / "citations_typed.json").read_text(encoding="utf-8"))["edges"]}

# semantic edges rolled to unordered paper pair -> list of contribution-edges
sem_by_pair: dict[frozenset, list] = defaultdict(list)
for e in sem:
    a, b = pid(e["src"]), pid(e["dst"])
    if a != b:
        sem_by_pair[frozenset((a, b))].append(e)

# citation edges keyed by unordered pair (keep the directed original). Each intent
# site gets the matching typed site's support/priority joined on by claim prefix.
cit_by_pair: dict[frozenset, dict] = {}
for e in cit_intent:
    a, b = e["citing_id"], e["cited_id"]
    t = cit_typed.get((a, b), {})
    tsites = {(s.get("claim") or "")[:60]: (s.get("supports_claim", ""), s.get("priority", ""))
              for s in t.get("sites", [])}
    sites = []
    for s in e.get("sites", []):
        sp = tsites.get((s.get("claim") or "")[:60], ("", ""))
        sites.append({**s, "support": sp[0], "priority": sp[1]})
    cit_by_pair[frozenset((a, b))] = {"citing": a, "cited": b, "intent": e["intent"],
                                      "support": t.get("support", ""), "priority": t.get("priority", ""),
                                      "cite_key": e.get("cite_key", ""), "sites": sites,
                                      "conf": max((s.get("confidence", 0) for s in sites), default=0)}

both = set(sem_by_pair) & set(cit_by_pair)


def sem_rels(fp) -> set:
    return {e["relation"] for e in sem_by_pair[fp]}


# ── divergence categories ────────────────────────────────────────────────────
# Each: (title, blurb, predicate over a shared pair fp, sort key desc)
CATEGORIES = [
    ("A. Contrast seen ONLY by the citation",
     "Citation intent = `compares_contrasts`, but the semantic graph asserts no "
     "tension (no contradicts/refines) — only supports/builds_on. Is the citation "
     "over-firing, or did the semantic pass miss a real critique?",
     lambda fp: cit_by_pair[fp]["intent"] == "compares_contrasts"
     and not (sem_rels(fp) & {"contradicts", "refines", "contrast"}),
     lambda fp: cit_by_pair[fp]["conf"]),
    ("B. Citee does NOT back the claim, yet semantic says corroborate",
     "Citation support = `does_not`/`inconclusive` (the citee's abstract doesn't "
     "verify the local claim), but the semantic relation is `supports`. Different "
     "questions — but which is more informative here?",
     lambda fp: cit_by_pair[fp]["support"] in ("does_not", "inconclusive")
     and "supports" in sem_rels(fp),
     lambda fp: cit_by_pair[fp]["conf"]),
    ("C. Both see tension (agreement — positive control)",
     "Citation intent = `compares_contrasts` AND the semantic pair carries a "
     "`contradicts`. The strongest independent corroboration between the two views.",
     lambda fp: cit_by_pair[fp]["intent"] == "compares_contrasts"
     and "contradicts" in sem_rels(fp),
     lambda fp: cit_by_pair[fp]["conf"]),
    ("D. Adoption seen ONLY by the citation",
     "Citation intent = `uses_extends` (first-person adoption / build-on), but the "
     "semantic graph found no lineage edge (no builds_on/refines) — only "
     "supports/mentions. Did the semantic pass under-call the dependency?",
     lambda fp: cit_by_pair[fp]["intent"] == "uses_extends"
     and not (sem_rels(fp) & {"builds_on", "refines"}),
     lambda fp: cit_by_pair[fp]["conf"]),
    ("E. A contradicts buried under supports",
     "The semantic pair is mixed and carries a `contradicts` that a majority vote "
     "would hide under `supports`. What is the model actually claiming clashes?",
     lambda fp: "contradicts" in sem_rels(fp) and "supports" in sem_rels(fp)
     and sum(1 for e in sem_by_pair[fp] if e["relation"] == "supports")
     > sum(1 for e in sem_by_pair[fp] if e["relation"] == "contradicts"),
     lambda fp: len(sem_by_pair[fp])),
]


# ── rendering ────────────────────────────────────────────────────────────────
def paper_line(pid_: str) -> str:
    p = papers.get(pid_, {})
    au = p.get("authors") or []
    first = (au[0].split()[-1] if au and isinstance(au[0], str) else "?")
    etal = " et al." if len(au) > 1 else ""
    def host_label(u: str) -> str:
        return ("OpenAlex" if "openalex" in u else "S2" if "semanticscholar" in u
                else "arXiv" if "arxiv" in u else "link")
    links = []
    if p.get("url"):
        links.append(f"[{host_label(p['url'])}]({p['url']})")
    if p.get("doi"):
        links.append(f"[doi]({p['doi']})")
    if p.get("pdf_url") and p["pdf_url"] not in (p.get("url"), ""):
        links.append(f"[pdf]({p['pdf_url']})")
    return (f"**{p.get('title','?')}** — {first}{etal} ({p.get('year','?')}) "
            f"· `{pid_}` · {' · '.join(links) if links else 'no link'}")


def evidence_or_fallback(e: dict) -> str:
    """~52 shipped edges have an empty `evidence` string; fall back to the model
    dissent (what the other labellers thought) — genuinely informative, e.g. a
    `supports` the other models read as `builds_on`."""
    ev = (e.get("evidence") or "").strip()
    if ev:
        return ev
    ag = e.get("agreement") or {}
    diss = ag.get("dissent") or {}
    conf = e.get("confidence", "?")
    if diss:
        d = ", ".join(f"{m}→{r}" for m, r in diss.items())
        return (f"_(no rationale stored upstream; anchor {ag.get('anchor','?')} labelled "
                f"**{e['relation']}** at conf {conf}, but other models dissented: {d})_")
    return f"_(no rationale stored upstream; tier {ag.get('tier','?')}, confidence {conf})_"


def claim_window(txt: str) -> str:
    """The full claim window, newlines flattened, with the target marker bolded."""
    s = " ".join((txt or "").split())
    return s.replace("[CITED:TARGET]", "**[CITED:TARGET]**")


def render(fp, idx) -> str:
    c = cit_by_pair[fp]
    citing, cited = c["citing"], c["cited"]
    lines = [f"### Case {idx}\n"]
    lines.append(f"- **Citing** → {paper_line(citing)}")
    lines.append(f"- **Cited** ← {paper_line(cited)}\n")
    # citation side
    lines.append(f"**Citation edge** (`{citing.split(':')[-1]}` cites `{cited.split(':')[-1]}`, "
                 f"key `{c['cite_key']}`): intent **{c['intent']}** · support "
                 f"**{c['support'] or '—'}** · priority **{c['priority'] or '—'}**")
    for s in c["sites"]:
        sp = f" · support {s['support']}" if s.get("support") else ""
        pr = f" · priority {s['priority']}" if s.get("priority") else ""
        lines.append(f"  - _{s.get('intent','')}_ (conf {s.get('confidence','?')}{sp}{pr}): "
                     f"{s.get('justification','')}")
        lines.append(f"    > {claim_window(s.get('claim',''))}")
    # semantic side
    lines.append(f"\n**Semantic edge(s)** ({len(sem_by_pair[fp])} contribution→contribution):")
    for e in sorted(sem_by_pair[fp], key=lambda e: e["relation"]):
        sc, dc = contribs.get(e["src"], {}), contribs.get(e["dst"], {})
        tier = (e.get("agreement") or {}).get("tier", "")
        lines.append(f"  - **{e['relation']}** (trust {e.get('trust','?')}, {tier}): "
                     f"{evidence_or_fallback(e)}")
        lines.append(f"    - src `{e['src']}` [{sc.get('kind','?')}] — {sc.get('statement','?')}")
        if sc.get("quote_verbatim") or sc.get("quote"):
            lines.append(f"      > {(sc.get('quote_verbatim') or sc.get('quote'))[:280]}")
        lines.append(f"    - dst `{e['dst']}` [{dc.get('kind','?')}] — {dc.get('statement','?')}")
        if dc.get("quote_verbatim") or dc.get("quote"):
            lines.append(f"      > {(dc.get('quote_verbatim') or dc.get('quote'))[:280]}")
    lines.append("\n**Verdict:** _( complementary | semantic-wrong | citation-wrong | rollup-artifact )_  ")
    lines.append("**Notes:** …\n\n---")
    return "\n".join(lines)


out = ["# Citation × semantic — selected overlap cases\n",
       f"*Generated by `select_cases.py` — {len(both)} shared paper-pairs; {PER_CATEGORY} cases "
       "per divergence category. These are the pairs where the citation signal and the "
       "Cartographer's semantic relation see the pair differently. The two answer different "
       "questions, so a divergence is not automatically an error — the goal is to decide, "
       "case by case, whether one side is **wrong** or the citation adds **complementary** "
       "information the semantic pass lacks.*\n",
       "**How to read a case:** the citation edge is a *fact* (X cites Y) stamped with why "
       "(intent) and whether the citee backs the local claim (support). The semantic edge is "
       "the Cartographer's *assertion* about how the two papers' contributions relate, read "
       "from the contribution statements alone (no citation context). Quotes are verbatim.\n",
       "**Annotation — set each case's `Verdict` to one of:**\n"
       "- **complementary** — both are correct; they describe different facets, so the "
       "citation adds information the semantic edge lacks (e.g. builds_on *and* outperforms).\n"
       "- **semantic-wrong** — the Cartographer's relation type is wrong; the citation is the "
       "better read.\n"
       "- **citation-wrong** — the intent/support label is wrong; the semantic edge is the "
       "better read.\n"
       "- **rollup-artifact** — not a real divergence: the citation concerns a *different* "
       "contribution of the paper than the semantic edge does (paper-level rollup mixing two "
       "things).\n\n"
       "Then jot a one-line reason under `Notes`. When done, we tally the verdicts to decide "
       "whether the citation signal is worth feeding into the Cartographer.\n"]

for title, blurb, pred, keyfn in CATEGORIES:
    # deterministic: primary key desc, ties broken by the sorted paper-pair ids
    picks = sorted([fp for fp in both if pred(fp)],
                   key=lambda fp: (-keyfn(fp), tuple(sorted(fp))))[:PER_CATEGORY]
    out.append(f"\n## {title}\n\n{blurb}\n\n*{len(picks)} shown of "
               f"{sum(1 for fp in both if pred(fp))} matching pairs.*\n")
    for j, fp in enumerate(picks, 1):
        out.append(render(fp, j))

OUT.write_text("\n".join(out), encoding="utf-8")
print(f"wrote {OUT}")
for title, blurb, pred, keyfn in CATEGORIES:
    print(f"  {title.split('.')[0]}: {sum(1 for fp in both if pred(fp))} matching pairs")
