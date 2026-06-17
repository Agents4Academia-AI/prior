"""Load SciFact (claims + abstract corpus).

SciFact ships as a tarball of JSONL files: `corpus.jsonl` plus
`claims_{train,dev,test}.jsonl`. We read a local copy (point `--data` at the
extracted dir) and optionally download it once. The test split has no labels, so
we evaluate on dev.
"""

from __future__ import annotations

import json
import tarfile
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

SCIFACT_URL = "https://scifact.s3-us-west-2.amazonaws.com/release/latest/data.tar.gz"
LABELS = ("SUPPORT", "CONTRADICT", "NOINFO")


@dataclass
class Doc:
    doc_id: str
    title: str
    sentences: list[str]

    @property
    def abstract(self) -> str:
        return " ".join(self.sentences)


@dataclass
class SciFactClaim:
    id: str
    claim: str
    gold_label: str                       # SUPPORT | CONTRADICT | NOINFO
    cited_doc_ids: list[str] = field(default_factory=list)
    evidence_doc_ids: list[str] = field(default_factory=list)


def _gold_label(evidence: dict) -> str:
    """A claim with no evidence annotations is NOINFO; otherwise the evidence
    carries a SUPPORT/CONTRADICT label (consistent within a claim in SciFact)."""
    for anns in (evidence or {}).values():
        for a in anns:
            lab = str(a.get("label", "")).upper()
            if lab in ("SUPPORT", "CONTRADICT"):
                return lab
    return "NOINFO"


def load_corpus(path: Path) -> dict[str, Doc]:
    docs: dict[str, Doc] = {}
    for line in Path(path).read_text().splitlines():
        if not line.strip():
            continue
        d = json.loads(line)
        did = str(d["doc_id"])
        docs[did] = Doc(doc_id=did, title=d.get("title", ""),
                        sentences=list(d.get("abstract", [])))
    return docs


def load_claims(path: Path) -> list[SciFactClaim]:
    claims: list[SciFactClaim] = []
    for line in Path(path).read_text().splitlines():
        if not line.strip():
            continue
        c = json.loads(line)
        evidence = c.get("evidence", {}) or {}
        claims.append(SciFactClaim(
            id=str(c["id"]),
            claim=c["claim"],
            gold_label=_gold_label(evidence),
            cited_doc_ids=[str(x) for x in c.get("cited_doc_ids", [])],
            evidence_doc_ids=[str(k) for k in evidence],
        ))
    return claims


def load(data_dir: Path, split: str = "dev") -> tuple[dict[str, Doc], list[SciFactClaim]]:
    data_dir = Path(data_dir)
    corpus = load_corpus(data_dir / "corpus.jsonl")
    claims = load_claims(data_dir / f"claims_{split}.jsonl")
    return corpus, claims


def download(dest: Path) -> Path:  # pragma: no cover - network
    """Download + extract the SciFact tarball into `dest`, returning the dir
    that contains corpus.jsonl."""
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    tgz = dest / "scifact.tar.gz"
    if not tgz.exists():
        urllib.request.urlretrieve(SCIFACT_URL, tgz)
    with tarfile.open(tgz) as t:
        t.extractall(dest)
    for p in dest.rglob("corpus.jsonl"):
        return p.parent
    raise FileNotFoundError("corpus.jsonl not found after extraction")
