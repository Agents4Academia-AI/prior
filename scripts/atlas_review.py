#!/usr/bin/env python3
"""Atlas review linter — scan the contribution atlas for data-quality problems and
flag them for human review. It does NOT mutate the data; it emits a report
(`data/atlas/review.json` + a console summary) of candidates a human should check.

This is the "automatic checker" companion to the auto-merge in gen_global_d3.py:
the generator applies the obvious same-title merge so the view is correct, while
this linter surfaces the full set of issues (including borderline ones) as a
review queue. Intended to run as a QA gate after Reader/Cartographer and before
serving, with a human approving the suggested actions.

Checks:
  duplicate_paper          same paper ingested as multiple records (same title)
  version_variant          a duplicate group mixes preprint / published versions
  duplicate_contribution   same contribution restated across duplicate records
  intra_paper_edge         a "cross-paper" edge whose endpoints are one paper
  isolated_paper           a paper with no cross-paper relations
  lineage_cycle            refines/extends/builds_on has a cycle (mutual precedence)
  precedence_year_conflict a derivative predates its antecedent
  low_confidence_edge      a relation below the confidence threshold

Usage:  python3 scripts/atlas_review.py
"""
from __future__ import annotations

import json
import re
import sys
from collections import defaultdict, deque
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "data" / "atlas" / "contributions.json"
ATLAS = ROOT / "data" / "atlas" / "atlas.json"
OUT = ROOT / "data" / "atlas" / "review.json"
# Optional: point at another atlas dir + contributions file
#   python3 atlas_review.py <atlas_dir> [contributions_file]
if len(sys.argv) > 1:
    _d = Path(sys.argv[1])
    SRC = _d / (sys.argv[2] if len(sys.argv) > 2 else "contributions.json")
    ATLAS, OUT = _d / "atlas.json", _d / "review.json"

LOW_CONF = 0.5
LINEAGE = {"refines", "extends", "builds_on"}
# Non-primary detection: use the work's OWN framing + unambiguous article types.
# Deliberately NOT `is_review` or bare "review"/"peer review" — those are confounded
# by peer-review-TOPIC papers (a whole primary cluster) and over-flag.
NONPRIM_TITLE = re.compile(r"\b(perspective|position paper|a survey|survey of|systematic review|a review of|roadmap|viewpoint|the case for|primer)\b", re.I)
NONPRIM_TEXT = re.compile(r"(this perspective|this position|position paper|we argue|we advocate|we call for|we contend|we posit|this survey|we survey|a survey of|this review|we review the)", re.I)


def norm_title(t: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (t or "").lower()).strip()


def pid_of(cid: str) -> str:
    return cid.split("::")[0]


def year_of(p: dict):
    try:
        return int(p.get("year"))
    except (TypeError, ValueError):
        return None


def review() -> list[dict]:
    data = json.loads(SRC.read_text())
    atlas = {p["id"]: p for p in json.loads(ATLAS.read_text()).get("papers", [])}
    contribs = data.get("contributions", [])
    edges = data.get("edges", [])
    cpaper = {c["id"]: c["paper_id"] for c in contribs}
    used = list(dict.fromkeys(c["paper_id"] for c in contribs))

    flags: list[dict] = []
    add = lambda **kw: flags.append(kw)

    # 1/2. duplicate papers + version variants (same normalized title) -----------
    groups: dict[str, list] = defaultdict(list)
    for pid in used:
        groups[norm_title((atlas.get(pid) or {}).get("title")) or pid].append(pid)
    remap = {}
    for pids in groups.values():
        canon = sorted(pids)[0]
        for p in pids:
            remap[p] = canon
        if len(pids) > 1:
            dois = {p: (atlas.get(p) or {}).get("doi") for p in pids}
            add(type="duplicate_paper", severity="high", items=pids,
                detail=f"{len(pids)} records share a title — likely one paper. "
                       + "; ".join(f"{p}→{dois[p]}" for p in pids),
                suggested_action="merge into one canonical paper node")
            kinds = set()
            for p in pids:
                d = ((atlas.get(p) or {}).get("doi") or "").lower()
                v = (atlas.get(p) or {}).get("venue")
                kinds.add("arXiv preprint" if "arxiv" in d else (v if v and v != "None" else "published"))
            if len(kinds) > 1:
                add(type="version_variant", severity="medium", items=pids,
                    detail="records look like different versions: " + ", ".join(sorted(kinds)),
                    suggested_action="canonicalize; use earliest (preprint) date for precedence")

    # 3. duplicate contributions (supports edge across records of one merged paper)
    for e in edges:
        s, d = e.get("src"), e.get("dst")
        if (e.get("relation") == "supports" and s in cpaper and d in cpaper
                and cpaper[s] != cpaper[d] and remap.get(cpaper[s]) == remap.get(cpaper[d])):
            add(type="duplicate_contribution", severity="medium", items=[s, d],
                detail="contributions of duplicate paper records linked by 'supports' — likely restated",
                suggested_action="merge contributions")

    # 4. intra-paper edges masquerading as cross-paper -------------------------
    for e in edges:
        s, d = e.get("src"), e.get("dst")
        if s in cpaper and d in cpaper and cpaper[s] == cpaper[d]:
            add(type="intra_paper_edge", severity="low", items=[s, d], relation=e.get("relation"),
                detail="cross-paper edge whose endpoints are the same paper",
                suggested_action="drop or reclassify as a local (within-paper) edge")

    # 5. isolated papers --------------------------------------------------------
    touched = set()
    for e in edges:
        for x in (e.get("src"), e.get("dst")):
            if x in cpaper:
                touched.add(cpaper[x])
    for pid in used:
        if pid not in touched:
            add(type="isolated_paper", severity="low", items=[pid],
                detail=f"no cross-paper relations — '{(atlas.get(pid) or {}).get('title')}'",
                suggested_action="review relevance / look for missing links")

    # 6/7. lineage cycles + precedence year conflicts (paper level) ------------
    succ = defaultdict(set)
    indeg: dict[str, int] = defaultdict(int)
    nodes = set()
    for e in edges:
        if e.get("relation") not in LINEAGE:
            continue
        a, b = pid_of(e["dst"]), pid_of(e["src"])  # antecedent -> derivative
        if a == b:
            continue
        nodes.update((a, b))
        if b not in succ[a]:
            succ[a].add(b)
            indeg[b] += 1
        ya, yb = year_of(atlas.get(a) or {}), year_of(atlas.get(b) or {})
        if ya and yb and yb < ya:
            add(type="precedence_year_conflict", severity="medium", items=[a, b], relation=e["relation"],
                detail=f"{b} ({yb}) {e['relation']} {a} ({ya}) — derivative predates antecedent",
                suggested_action="check dates/direction; may be a preprint-vs-published artifact")
    indeg2 = dict(indeg)
    q = deque(n for n in nodes if indeg2.get(n, 0) == 0)
    seen = 0
    while q:
        u = q.popleft()
        seen += 1
        for v in succ[u]:
            indeg2[v] -= 1
            if indeg2[v] == 0:
                q.append(v)
    if seen != len(nodes):
        add(type="lineage_cycle", severity="high", items=sorted(nodes),
            detail="refines/extends/builds_on graph has a cycle (mutual precedence)",
            suggested_action="inspect edge directions; precedence must be acyclic")

    # 8. low-confidence edges ---------------------------------------------------
    for e in edges:
        c = e.get("confidence")
        if isinstance(c, (int, float)) and c < LOW_CONF:
            add(type="low_confidence_edge", severity="low", items=[e.get("src"), e.get("dst")],
                relation=e.get("relation"), confidence=c,
                detail=f"relation '{e.get('relation')}' confidence {c} < {LOW_CONF}",
                suggested_action="human-verify the relation")

    # 9. non-primary candidates (perspective / position / survey / review article) -
    # Primary-only corpus, but the metadata filters miss arXiv perspectives. Detect
    # by the work's own framing + unambiguous title types; HUMAN-CONFIRM (peer-review-
    # topic papers can still slip in as false positives — never auto-drop).
    ptext: dict[str, str] = defaultdict(str)
    for c in contribs:
        ptext[c["paper_id"]] += " " + (c.get("statement") or "") + " " + (c.get("quote") or "")
    for pid in used:
        title = (atlas.get(pid) or {}).get("title") or ""
        sig = []
        mt = NONPRIM_TITLE.search(title)
        mx = NONPRIM_TEXT.search(ptext[pid])
        if mt:
            sig.append(f"title:'{mt.group(0)}'")
        if mx:
            sig.append(f"framing:'{mx.group(0)}'")
        if sig:
            add(type="non_primary_candidate", severity="medium", items=[pid],
                detail=f"reads as a perspective/survey/review article ({'; '.join(sig)}) — "
                       f"'{title[:60]}'. Primary-only corpus; is_review is unreliable here.",
                suggested_action="human-confirm; drop if non-primary (do NOT auto-drop)")

    return flags


def main() -> None:
    flags = review()
    order = {"high": 0, "medium": 1, "low": 2}
    flags.sort(key=lambda f: order.get(f["severity"], 3))
    counts: dict[str, int] = defaultdict(int)
    for f in flags:
        counts[f["severity"]] += 1
    OUT.write_text(json.dumps({"summary": dict(counts), "flags": flags}, indent=2))

    print(f"Atlas review — {len(flags)} flags for human review "
          f"({counts['high']} high · {counts['medium']} medium · {counts['low']} low)\n")
    for f in flags:
        print(f"[{f['severity'].upper():6}] {f['type']}")
        print(f"         {f['detail']}")
        if f.get("items"):
            print("         items: " + ", ".join(f["items"]))
        print(f"         → {f['suggested_action']}\n")
    print(f"(machine-readable report: {OUT})")


if __name__ == "__main__":
    main()
