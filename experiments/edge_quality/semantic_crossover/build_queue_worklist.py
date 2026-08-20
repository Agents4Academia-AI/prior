#!/usr/bin/env python3
"""Render Klara's full-intent-graph audit queue as one annotate-ready worklist.

Klara (on `dev`) scaled the citation-intent×graph audit to all sites and left an
87-item prioritised queue (`out/full_intent_graph_audit_pair_queue.json`, 85
unique contribution pairs) built against the *enriched v12* canonical graph
(`out/canonical_semantic_candidates_enriched_evidence_v12.json`) — the 989 legacy
pairs RELABELLED with citation + full-text evidence. That relabel means some
relations differ from the citation-blind shipped bundle we annotated in
`overlap_cases.md`.

This script produces `queue_worklist.md`:
  * Part 1 — the 11 pairs we ALREADY judged: carries our prior verdict/notes, and
    flags per pair whether the enriched relation CHANGED vs what we judged (so a
    carried verdict is never silently pasted onto a different edge).
  * Part 2 — the ~74 new pairs, in Klara's priority order, each a full case block
    (flagged citation sites + enriched graph relation/reason + both contributions'
    statement & quote) with a blank Verdict/Notes to fill.

Zero LLM cost, deterministic. Read-only over all inputs; only writes the .md.
"""
from __future__ import annotations
import json
import re
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
EQ = ROOT / "experiments" / "edge_quality" / "out"
BUNDLE = ROOT / "data" / "prior-core-v0.2"
CASES = HERE / "overlap_cases.md"
OUT = HERE / "queue_worklist.md"

VERDICTS = ("complementary", "semantic-wrong", "citation-wrong", "rollup-artifact")

# ── load ─────────────────────────────────────────────────────────────────────
queue = json.loads((EQ / "full_intent_graph_audit_pair_queue.json").read_text(encoding="utf-8"))["queue"]
canon = json.loads((EQ / "canonical_semantic_candidates_enriched_evidence_v12.json").read_text(encoding="utf-8"))
contribs = {c["id"]: c for c in canon["contributions"]}
edge_by_pair = {frozenset((e["src"], e["dst"])): e for e in canon["edges"]}
papers = {p["id"]: p for p in (json.loads(l) for l in
          (BUNDLE / "papers_core.jsonl").read_text(encoding="utf-8").splitlines() if l.strip())}

# ── full citation graph: my 809 sites + Klara's +294 new-substrate sites ──────
# The queue only carries the *flagged* sites; the complete site list (and the
# real citation DIRECTION, which is independent of the semantic edge's src/dst)
# lives in these two intent files. They are exactly what audit_full_intent_graph
# joined into 1103 sites. Support/priority come from my typed pass (809 only);
# the +294 new-substrate sites have intent but no typed support/priority yet.
def _skey(citing: str, cited: str, i: int) -> str:
    return f"{citing}->{cited}#{i}"


cit_by_pair: dict[frozenset, dict] = {}      # paper-pair -> {citing, cited, sites[]}
_typed = {(e["citing_id"], e["cited_id"]): e for e in
          json.loads((EQ / "citations_typed.json").read_text(encoding="utf-8"))["edges"]}
for e in json.loads((EQ / "citations_intent.json").read_text(encoding="utf-8"))["edges"]:
    a, b = e["citing_id"], e["cited_id"]
    tsites = {(s.get("claim") or "")[:60]: (s.get("supports_claim", ""), s.get("priority", ""))
              for s in _typed.get((a, b), {}).get("sites", [])}
    sites = []
    for i, s in enumerate(e.get("sites", [])):
        sp = tsites.get((s.get("claim") or "")[:60], ("", ""))
        sites.append({**s, "support": sp[0], "priority": sp[1], "origin": "callum_809",
                      "site_key": _skey(a, b, i)})
    cit_by_pair.setdefault(frozenset((a, b)), {"citing": a, "cited": b, "sites": []})["sites"] += sites
# Marked windows ([CITED]/[CITED:TARGET]) for the new substrate live only in
# Klara's local citation-substrate worktree; the pushed `citation_contexts.json`
# recovers a MINORITY of them (keyed "citing->cited" -> list of marked strings).
# Use a recovered window only when the pair's list length matches the site count,
# so index i aligns safely; otherwise the raw (unmarked) window is labelled as such.
_ctx = json.loads((EQ / "citation_contexts.json").read_text(encoding="utf-8"))
_new_raw = json.loads((EQ / "citations_intent_incoming_v12_new.json").read_text(encoding="utf-8"))["sites"]
_new_by_pk: dict[str, list] = {}
for s in _new_raw:
    _new_by_pk.setdefault(f"{s['citing_id']}->{s['cited_id']}", []).append(s)
# +294 new-substrate sites (119 brand-new paper-pairs, disjoint from mine)
for pk, group in _new_by_pk.items():
    marked = _ctx.get(pk)
    aligned = isinstance(marked, list) and len(marked) == len(group) and all(
        isinstance(m, str) and "[CITED" in m for m in marked)
    for i, s in enumerate(group):
        a, b = s["citing_id"], s["cited_id"]
        rec = cit_by_pair.setdefault(frozenset((a, b)), {"citing": a, "cited": b, "sites": []})
        claim = marked[i] if aligned else s.get("claim", "")
        rec["sites"].append({**s, "claim": claim, "support": "", "priority": "",
                             "origin": "v12_new", "unmarked": not aligned,
                             "site_key": s.get("site_key", _skey(a, b, i))})

# User's own Part 1 annotations, decoupled into a sidecar so regeneration never
# loses them (falls back to the overlap_cases carry when a pair isn't stored).
_ann_path = HERE / "queue_annotations.json"
user_ann: dict[str, dict] = json.loads(_ann_path.read_text(encoding="utf-8")) if _ann_path.exists() else {}


def pid(cid: str) -> str:
    return cid.split("::")[0]


def cpair(rec) -> frozenset:
    return frozenset(rec["contribution_pair"].split("|"))


# ── prior annotations from overlap_cases.md ──────────────────────────────────
# paper-pair -> {"verdict", "notes"}; contribution-pair -> set(relations we judged)
prior_by_ppair: dict[frozenset, dict] = {}
prior_rel_by_cpair: dict[frozenset, set] = defaultdict(set)
md = CASES.read_text(encoding="utf-8")
for block in re.split(r"### Case ", md)[1:]:
    citing = re.search(r"\*\*Citing\*\*.*?`((?:arxiv:[0-9v.]+|openalex:W[0-9]+))`", block)
    cited = re.search(r"\*\*Cited\*\*.*?`((?:arxiv:[0-9v.]+|openalex:W[0-9]+))`", block)
    notes = re.search(r"\*\*Notes:\*\*\s*(.*)", block)
    note_txt = (notes.group(1).strip().lstrip("… ").strip() if notes else "")
    verdict = next((v for v in VERDICTS if v in note_txt.lower()), "")
    if citing and cited:
        prior_by_ppair[frozenset((citing.group(1), cited.group(1)))] = {
            "verdict": verdict, "notes": note_txt}
    for seg in re.split(r"\n  - \*\*", block)[1:]:
        m = re.match(r"([a-z_]+)\*\*", seg)
        ids = re.findall(r"(?:src|dst) `((?:arxiv:[0-9v.]+|openalex:W[0-9]+)::k[0-9]+)`", seg)
        if m and len(ids) >= 2:
            prior_rel_by_cpair[frozenset((ids[0], ids[1]))].add(m.group(1))


# ── merge queue to unique contribution pairs ─────────────────────────────────
by_cpair: dict[frozenset, dict] = {}
for rec in queue:
    fp = cpair(rec)
    if fp not in by_cpair:
        by_cpair[fp] = {**rec, "audit_reasons": set(), "all_sites": []}
    by_cpair[fp]["audit_reasons"].add(rec["audit_reason"])
    for s in rec.get("sites", []):
        if s not in by_cpair[fp]["all_sites"]:
            by_cpair[fp]["all_sites"].append(s)

# priority: comparison→contradiction first, then uses-extends exceptions, then
# background hard relations ordered contradicts/refines/builds_on/supports/related.
REASON_RANK = {"comparison_promoted_to_contradiction": 0, "uses_extends_not_builds_on": 1,
               "background_passage_supports_hard_relation": 2}
REL_RANK = {"contradicts": 0, "refines": 1, "builds_on": 2, "supports": 3, "related": 4, "none": 5}


def sortkey(fp):
    r = by_cpair[fp]
    return (min(REASON_RANK.get(a, 9) for a in r["audit_reasons"]),
            REL_RANK.get(r["relation"], 9), sorted(fp))


# ── rendering helpers (match overlap_cases.md style) ─────────────────────────
def host_label(u: str) -> str:
    return ("OpenAlex" if "openalex" in u else "S2" if "semanticscholar" in u
            else "arXiv" if "arxiv" in u else "link")


def paper_line(p_id: str) -> str:
    p = papers.get(p_id, {})
    au = p.get("authors") or []
    first = (au[0].split()[-1] if au and isinstance(au[0], str) else "?")
    etal = " et al." if len(au) > 1 else ""
    links = []
    if p.get("url"):
        links.append(f"[{host_label(p['url'])}]({p['url']})")
    if p.get("doi"):
        links.append(f"[doi]({p['doi']})")
    if p.get("pdf_url") and p["pdf_url"] not in (p.get("url"), ""):
        links.append(f"[pdf]({p['pdf_url']})")
    return (f"**{p.get('title','?')}** — {first}{etal} ({p.get('year','?')}) "
            f"· `{p_id}` · {' · '.join(links) if links else 'no link'}")


def window(txt: str) -> str:
    return " ".join((txt or "").split()).replace("[CITED:TARGET]", "**[CITED:TARGET]**")


def contrib_block(cid: str) -> list[str]:
    c = contribs.get(cid, {})
    out = [f"    - `{cid}` [{c.get('kind','?')}] — {c.get('statement','(statement missing)')}"]
    q = " ".join((c.get("quote") or "").split())
    if q:
        out.append(f"      > {q}")
    return out


def case_body(fp: frozenset) -> list[str]:
    r = by_cpair[fp]
    src, dst = r["graph_src"], r["graph_dst"]     # SEMANTIC edge orientation
    ppair = frozenset((pid(src), pid(dst)))
    cit = cit_by_pair.get(ppair)
    flagged = {s.get("site_key") for rec in queue if cpair(rec) == fp
               for s in rec.get("sites", [])}
    # Citing/Cited come from the CITATION direction, not the semantic src/dst.
    if cit:
        citing_p, cited_p, sites = cit["citing"], cit["cited"], cit["sites"]
    else:  # no full edge (shouldn't happen for queue pairs) — fall back to queue sites
        s0 = next((s for s in r["all_sites"]), {})
        citing_p, cited_p = s0.get("citing_id", pid(src)), s0.get("cited_id", pid(dst))
        sites = r["all_sites"]
    L = [f"- **Citing** → {paper_line(citing_p)}",
         f"- **Cited** ← {paper_line(cited_p)}\n"]
    L.append(f"**Flagged for:** {', '.join(sorted(r['audit_reasons']))} "
             f"· {r['n_flagged_sites']} of {len(sites)} site(s) flagged")
    L.append("\n**All citation sites** (⚑ = flagged by the audit queue; ⁿ = new v12 substrate; "
             "intent · conf · support/priority · justification, then the citing passage):")
    for s in sites:
        tag = ("⚑ " if s.get("site_key") in flagged else "") + ("ⁿ " if s.get("origin") == "v12_new" else "")
        sp = " · ".join(x for x in (s.get("support"), s.get("priority")) if x)
        meta = f"conf {s.get('confidence','?')}" + (f" · {sp}" if sp else "")
        L.append(f"  - {tag}_{s.get('intent','?')}_ ({meta}): {s.get('justification','')}")
        cw = window(s.get("claim", ""))
        if cw and s.get("unmarked"):
            # New-substrate window with no [CITED]/[CITED:TARGET] marker recoverable
            # from git (the marked source is only in Klara's local substrate worktree).
            L.append("    > _(raw window — no `[CITED:TARGET]` marker available; the marked "
                     "version lives in Klara's local `citation-substrate` worktree)_")
            L.append(f"    > {cw}")
        elif cw:
            L.append(f"    > {cw}")
    e = edge_by_pair.get(fp, {})
    L.append(f"\n**Enriched-v12 semantic relation:** **{r['relation']}** "
             f"(semantic-edge direction: {e.get('direction','?')}; existence "
             f"{e.get('existence_confidence','?')}, type {e.get('type_confidence','?')}) — "
             f"`{src}` → `{dst}`")
    L.append(f"  - _rationale:_ {r.get('graph_reason','')}")
    L += contrib_block(src)
    L += contrib_block(dst)
    return L


# ── partition done vs new ────────────────────────────────────────────────────
done, new = [], []
for fp in by_cpair:
    if prior_by_ppair.get(frozenset(pid(x) for x in fp)):
        done.append(fp)
    else:
        new.append(fp)
done.sort(key=sortkey)
new.sort(key=sortkey)

# ── emit ─────────────────────────────────────────────────────────────────────
doc: list[str] = []
doc.append("# Citation-intent audit queue — reconciled worklist\n")
doc.append("*Source: Klara's `out/full_intent_graph_audit_pair_queue.json` (87 pair-reasons, "
           f"{len(by_cpair)} unique contribution pairs), built against the **enriched v12** canonical "
           "graph. That graph relabels the 989 legacy pairs using citation + full-text evidence, so "
           "its relation types can differ from the citation-blind shipped bundle we annotated in "
           "`overlap_cases.md`.*\n")
doc.append("**Annotation — set each `Verdict` to one of:** `complementary` · `semantic-wrong` · "
           "`citation-wrong` · `rollup-artifact` (definitions in `overlap_cases.md`). Then a one-line "
           "`Notes`. Queue membership is an *audit pointer*, not a claim the edge is wrong.\n")
doc.append("> **Provenance of the graph relation:** every relation below is the enriched-v12 label "
           "(citation evidence already folded in). Where it changed vs our earlier blind annotation, "
           "the Part-1 flag records both, so a carried verdict is never mistaken for a verdict of the "
           "new edge.\n")
doc.append("---\n")

# Part 1
doc.append(f"## Part 1 — already annotated ({len(done)} pairs): carried over, re-check the flagged ones\n")
doc.append("*Your prior verdict was made against the **blind** graph. For each pair: your note, then "
           "whether the enriched relation moved. ⚠ = relation changed — your verdict may not transfer.*\n")
changed_n = 0
for i, fp in enumerate(done, 1):
    r = by_cpair[fp]
    ppair = frozenset(pid(x) for x in fp)
    prior = prior_by_ppair[ppair]
    mine = prior_rel_by_cpair.get(fp, set())
    now = r["relation"]
    changed = bool(mine) and now not in mine
    changed_n += changed
    flag = (f"⚠ **RE-CHECK — relation changed: you judged `{'/'.join(sorted(mine))}`, enriched v12 says "
            f"`{now}`.**" if changed else
            f"✓ relation unchanged (`{now}`) — verdict carries." if mine else
            f"(relation `{now}`; no exact-pair match in your notes — check).")
    doc.append(f"### P1-{i}  `{sorted(fp)[0]}` | `{sorted(fp)[1]}`\n")
    doc.append(flag + "\n")
    # Prefer the user's own annotation on this worklist (made against the enriched
    # graph, stored in queue_annotations.json); fall back to the overlap_cases carry.
    ann = user_ann.get("|".join(sorted(fp)))
    if ann:
        doc.append(f"- **Your annotation:** {ann.get('notes') or '(recorded, no note)'}\n")
        v, n = ann.get("verdict", ""), ann.get("notes", "")
    else:
        doc.append(f"- **Carried from overlap_cases (blind graph):** {prior['notes'] or '(none)'}\n")
        v, n = f"_(carried: {prior['verdict'] or '?'}{' — RE-CHECK' if changed else ''})_", prior["notes"]
    doc += case_body(fp)
    doc.append(f"\n**Verdict:** {v}  ")
    doc.append(f"**Notes:** {n}\n")
    doc.append("---\n")

# Part 2
doc.append(f"## Part 2 — new pairs to annotate ({len(new)})\n")
doc.append("*Klara's priority order: comparison→contradiction, then uses_extends exceptions, then "
           "background-as-evidence (contradicts → refines → builds_on → supports).*\n")
cur = None
for i, fp in enumerate(new, 1):
    r = by_cpair[fp]
    grp = min(r["audit_reasons"], key=lambda a: REASON_RANK.get(a, 9))
    if grp != cur:
        cur = grp
        doc.append(f"\n### ▸ {grp}\n")
    doc.append(f"#### N-{i}\n")
    doc += case_body(fp)
    doc.append("\n**Verdict:** _( complementary | semantic-wrong | citation-wrong | rollup-artifact )_  ")
    doc.append("**Notes:** …\n")
    doc.append("---\n")

OUT.write_text("\n".join(doc), encoding="utf-8")
print(f"wrote {OUT}")
print(f"  done (already annotated): {len(done)}  | of which relation CHANGED: {changed_n}")
print(f"  new to annotate:          {len(new)}")
print(f"  total unique pairs:       {len(by_cpair)}")
