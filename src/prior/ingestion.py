"""On-demand single-paper ingestion for the web UI.

A user adds one paper — by arXiv id/URL, a PDF URL, or an uploaded PDF — and we
run the existing per-paper pipeline (daemon.process_paper: full text → Reader →
embed → MERGE into Neo4j → incremental global relate) in a BACKGROUND thread so
the UI never blocks. Progress is tracked in an in-memory job registry the UI polls.

Jobs are process-local (fine for a single-node demo). PDFs without metadata get
their title/authors/abstract derived from the first page via one LLM call.
"""

from __future__ import annotations

import hashlib
import re
import threading
import uuid
from dataclasses import asdict, dataclass, field
from typing import Optional

import requests

from . import config, daemon, fulltext, graph, llm
from .models import Paper
from .sources import arxiv


def _norm_title(title: str) -> str:
    """Same normalisation as Paper.key() — the cross-source/version join key."""
    t = " ".join(re.sub(r"[^a-z0-9]", " ", (title or "").lower()).split())
    return t if len(t) >= 8 else ""


def find_duplicate(paper: Paper) -> Optional[dict]:
    """Is this paper already in the graph? Returns {kind, id, title} where kind is
    'exact' (same id) or 'version' (same normalised title — e.g. arXiv vs
    proceedings vs an uploaded PDF), else None."""
    if graph.have_paper(paper.id):
        return {"kind": "exact", "id": paper.id, "title": paper.title}
    tkey = _norm_title(paper.title)
    if tkey:
        for p in graph.paper_index():
            if _norm_title(p.get("title", "")) == tkey:
                return {"kind": "version", "id": p["id"], "title": p.get("title")}
    return None


# ── job registry ────────────────────────────────────────────────────────────────
@dataclass
class Job:
    id: str
    kind: str                       # arxiv | pdf_url | pdf_upload
    label: str                      # what the user submitted (for display)
    status: str = "queued"          # queued|fetching|extracting|done|failed|duplicate
    message: str = ""
    paper_id: Optional[str] = None
    title: Optional[str] = None
    result: dict = field(default_factory=dict)   # contribs/claims/edges on done
    duplicate_of: Optional[dict] = None          # {kind, id, title} when a dup is found
    error: Optional[str] = None


_JOBS: dict[str, Job] = {}
_LOCK = threading.Lock()


def _set(job: Job, **kw) -> None:
    with _LOCK:
        for k, v in kw.items():
            setattr(job, k, v)


def job_status(job_id: str) -> Optional[dict]:
    with _LOCK:
        j = _JOBS.get(job_id)
        return asdict(j) if j else None


# ── building a Paper from each input ────────────────────────────────────────────
_ARXIV_RE = re.compile(r"(\d{4}\.\d{4,5})(v\d+)?")


def _arxiv_id(value: str) -> Optional[str]:
    m = _ARXIV_RE.search(value or "")
    return m.group(1) if m else None


def _paper_from_arxiv(value: str) -> Paper:
    aid = _arxiv_id(value)
    if not aid:
        raise ValueError("Could not find an arXiv id in the input.")
    papers = arxiv.fetch_ids([aid])
    if not papers:
        raise ValueError(f"arXiv {aid} not found.")
    return next(iter(papers.values()))


_META_SYS = """You are given the first part of a research paper (often from a PDF).
Extract its bibliographic metadata. If a field is unknown, use an empty string /
empty list. `abstract` should be the paper's actual abstract if present."""

_META_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "authors": {"type": "array", "items": {"type": "string"}},
        "abstract": {"type": "string"},
        "year": {"type": "integer"},
    },
    "required": ["title", "authors", "abstract"],
}


def _paper_from_pdf_bytes(content: bytes, label: str) -> Paper:
    text = fulltext._pdf_text(content)
    if not text or len(text) < 400:
        raise ValueError("Could not extract readable text from the PDF.")
    meta = llm.structured(model=config.READER_MODEL, system=_META_SYS,
                          user=f"PAPER (beginning):\n{text[:8000]}",
                          schema=_META_SCHEMA, tool_name="emit_meta", timeout=90)
    pid = "pdf:" + hashlib.sha1(content).hexdigest()[:12]
    return Paper(
        id=pid, source="pdf",
        title=(meta.get("title") or label).strip(),
        abstract=(meta.get("abstract") or "").strip(),
        url="", year=meta.get("year"),
        authors=[a for a in (meta.get("authors") or []) if a],
        full_text=text,
    )


def _paper_from_pdf_url(url: str) -> Paper:
    r = requests.get(url, headers={"User-Agent": config.USER_AGENT},
                     timeout=config.HTTP_TIMEOUT)
    r.raise_for_status()
    if b"%PDF" not in r.content[:1024]:
        raise ValueError("That URL did not return a PDF.")
    return _paper_from_pdf_bytes(r.content, url.rsplit("/", 1)[-1])


# ── background runner ───────────────────────────────────────────────────────────
def _run(job: Job, *, content: Optional[bytes], value: str, force: bool,
         collection: str) -> None:
    try:
        _set(job, status="fetching", message="Fetching the paper…")
        if job.kind == "arxiv":
            paper = _paper_from_arxiv(value)
        elif job.kind == "pdf_url":
            paper = _paper_from_pdf_url(value)
        else:  # pdf_upload
            paper = _paper_from_pdf_bytes(content or b"", job.label)
        _set(job, paper_id=paper.id, title=paper.title)

        # Dedup before the expensive extraction.
        dup = find_duplicate(paper)
        if dup and (dup["kind"] == "exact" or not force):
            msg = ("This paper is already in the graph."
                   if dup["kind"] == "exact"
                   else f"A version of this paper is already in the graph "
                        f"(“{dup.get('title')}”). Add anyway?")
            _set(job, status="duplicate", message=msg, duplicate_of=dup)
            return

        _set(job, status="extracting", message="Extracting contributions & claims…")
        st = daemon.process_paper(paper, collection=collection)
        if not st.get("contribs") and not st.get("claims"):
            _set(job, status="failed",
                 error="No contributions or claims could be extracted from this paper.")
            return
        _set(job, status="relating", message="Re-clustering the graph…")
        from . import render
        render.recluster(collection)
        _set(job, status="done", message="Added to the graph.", result=st)
    except Exception as e:  # noqa: BLE001 — surface to the UI
        _set(job, status="failed", error=str(e))


def start(kind: str, *, value: str = "", content: Optional[bytes] = None,
          filename: str = "", force: bool = False,
          collection: str = "default") -> str:
    """Register a job and run it in a daemon thread. `force` skips the version-
    duplicate guard (exact-id duplicates are always skipped). The paper is added to
    `collection` and that collection is re-clustered on success. Returns the job id."""
    label = value or filename or kind
    job = Job(id=uuid.uuid4().hex[:12], kind=kind, label=label)
    with _LOCK:
        _JOBS[job.id] = job
    threading.Thread(target=_run, args=(job,),
                     kwargs={"content": content, "value": value, "force": force,
                             "collection": collection},
                     daemon=True).start()
    return job.id
