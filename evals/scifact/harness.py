"""SciFact eval harness for Prior's Navigator (forward mode).

Per claim: BM25-retrieve the top-k abstracts from the corpus, build a small
atlas whose claim-nodes are the abstracts' sentences, run Navigator, and map its
verdict to a SciFact label. We score 3-way accuracy, macro-F1, and abstention
(NOINFO) behaviour.

Credit thrift:
  * `ask_fn` is injectable — pass a mock to run the whole harness with no API.
  * `cache_path` records per-claim predictions; reruns skip finished claims.
  * `limit` runs a cheap dev slice.
The LLM backend (API vs Claude Code subscription) is chosen in prior.llm.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from rank_bm25 import BM25Okapi

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from prior import navigator  # noqa: E402
from prior.atlas import Atlas  # noqa: E402
from prior.models import Claim, Paper  # noqa: E402

from . import dataset  # noqa: E402
from .dataset import Doc, LABELS, SciFactClaim  # noqa: E402

_WORD = re.compile(r"[a-z0-9]+")


def _tok(s: str) -> list[str]:
    return _WORD.findall(s.lower())


class CorpusIndex:
    """BM25 over abstracts, built once and reused across all claims."""

    def __init__(self, corpus: dict[str, Doc]):
        self.docs = list(corpus.values())
        self._bm = BM25Okapi([_tok(d.title + " " + d.abstract) for d in self.docs])

    def topk(self, query: str, k: int) -> list[Doc]:
        scores = self._bm.get_scores(_tok(query))
        order = sorted(range(len(self.docs)), key=lambda i: scores[i], reverse=True)
        return [self.docs[i] for i in order[:k] if scores[i] > 0]


def atlas_from_docs(docs: list[Doc]) -> Atlas:
    """Build a small atlas: each abstract a Paper, each sentence a grounded
    claim node Navigator can retrieve and cite."""
    a = Atlas()
    for d in docs:
        pid = f"scifact:{d.doc_id}"
        a.add_paper(Paper(id=pid, source="scifact", title=d.title,
                          abstract=d.abstract, url=""))
        for i, sent in enumerate(d.sentences):
            a.add_claim(Claim(id=f"{pid}::s{i}", paper_id=pid, text=sent,
                              claim_type="empirical", evidence=sent,
                              location=f"sentence {i}"))
    return a


def map_label(answer: navigator.ForwardAnswer) -> str:
    """Collapse Prior's forward output to a SciFact label. We trust the
    supporting/contradicting evidence lists, with the verdict as tiebreaker."""
    s, c = len(answer.supporting), len(answer.contradicting)
    if answer.verdict == "not_found" or (s == 0 and c == 0):
        return "NOINFO"
    if c > s:
        return "CONTRADICT"
    if s > c:
        return "SUPPORT"
    return "SUPPORT" if answer.verdict == "established" else "NOINFO"


def _metrics(pairs: list[tuple[str, str]]) -> dict:
    n = len(pairs)
    conf = {g: {p: 0 for p in LABELS} for g in LABELS}
    for g, p in pairs:
        conf[g][p] += 1
    acc = sum(1 for g, p in pairs if g == p) / n if n else 0.0
    per, f1s = {}, []
    for L in LABELS:
        tp = conf[L][L]
        fp = sum(conf[g][L] for g in LABELS if g != L)
        fn = sum(conf[L][p] for p in LABELS if p != L)
        prec = tp / (tp + fp) if tp + fp else 0.0
        rec = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
        per[L] = {"precision": round(prec, 3), "recall": round(rec, 3),
                  "f1": round(f1, 3), "support": sum(conf[L].values())}
        f1s.append(f1)
    return {"n": n, "accuracy": round(acc, 3),
            "macro_f1": round(sum(f1s) / len(f1s), 3) if f1s else 0.0,
            "per_label": per, "confusion": conf}


def _load_cache(path: Path | None) -> dict[str, str]:
    if not path or not Path(path).exists():
        return {}
    out = {}
    for line in Path(path).read_text().splitlines():
        if line.strip():
            r = json.loads(line)
            out[r["id"]] = r["pred"]
    return out


def run_eval(corpus, claims, *, k=5, model=None, limit=None, ask_fn=navigator.ask,
             cache_path: Path | None = None, progress=print) -> dict:
    index = CorpusIndex(corpus)
    cache = _load_cache(cache_path)
    cache_fh = open(cache_path, "a") if cache_path else None
    todo = claims[:limit] if limit else claims

    pairs: list[tuple[str, str]] = []
    for i, claim in enumerate(todo, 1):
        if claim.id in cache:
            pred = cache[claim.id]
        else:
            docs = index.topk(claim.claim, k)
            if not docs:
                pred = "NOINFO"
            else:
                answer = ask_fn(atlas_from_docs(docs), claim.claim, model=model)
                pred = map_label(answer)
            if cache_fh:
                cache_fh.write(json.dumps({"id": claim.id, "pred": pred,
                                           "gold": claim.gold_label}) + "\n")
                cache_fh.flush()
        pairs.append((claim.gold_label, pred))
        progress(f"  [{i}/{len(todo)}] {claim.id}: gold={claim.gold_label} pred={pred}")

    if cache_fh:
        cache_fh.close()
    return _metrics(pairs)


def render(m: dict) -> str:
    lines = ["── SciFact eval (Navigator, forward) ──",
             f"claims     : {m['n']}",
             f"accuracy   : {m['accuracy']:.1%}",
             f"macro-F1   : {m['macro_f1']:.3f}", "",
             "per label  :  precision  recall   f1   support"]
    for L in LABELS:
        d = m["per_label"][L]
        lines.append(f"  {L:<10}   {d['precision']:.3f}    {d['recall']:.3f}  "
                     f"{d['f1']:.3f}    {d['support']}")
    lines += ["", "confusion (gold → pred):",
              "            " + "  ".join(f"{L[:4]:>5}" for L in LABELS)]
    for g in LABELS:
        row = "  ".join(f"{m['confusion'][g][p]:>5}" for p in LABELS)
        lines.append(f"  {g:<10}{row}")
    return "\n".join(lines)
