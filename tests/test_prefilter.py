"""BM25 pre-filter — the cheap recall-preserving gate before the LLM."""

from prior import scoper
from prior.models import Paper


def _p(pid, title, abstract):
    return Paper(id=pid, source="t", title=title, abstract=abstract, url="")


TOPIC = """LLM agents for the scientific process.
IN SCOPE: large language model agents for systematic review, literature search,
citation verification, and scientific claim verification.
OUT OF SCOPE: classroom education student grading; software libraries numpy scipy."""

CANDS = [
    _p("on1", "LLM agents for systematic review screening",
       "A large language model agent for literature search and citation verification."),
    _p("on2", "Scientific claim verification with language models",
       "Verifying scientific claims against evidence using LLM agents."),
    _p("on3", "Automated literature search agents",
       "Agentic literature search and screening for systematic reviews."),
    _p("off1", "Classroom education and student grading with ChatGPT",
       "Using ChatGPT for classroom education and student grading in schools."),
    _p("off2", "NumPy: a software library for arrays",
       "NumPy scipy software libraries for numerical array computing in Python."),
]


def test_prefilter_recall_safe_gates_offtopic_keeps_ontopic():
    survivors, gated = scoper.prefilter(TOPIC, CANDS, progress=lambda m: None)
    ids_keep = {p.id for p in survivors}
    ids_gate = {p.id for p in gated}
    assert ids_keep | ids_gate == {p.id for p in CANDS}      # nothing lost
    assert not (ids_keep & ids_gate)
    # recall-safe: every in-scope-dominant paper is kept
    assert {"on1", "on2", "on3"} <= ids_keep
    # the out-of-scope-dominant papers (exact exclusion vocab) are gated
    assert {"off1", "off2"} <= ids_gate


def test_prefilter_empty():
    assert scoper.prefilter(TOPIC, [], progress=lambda m: None) == ([], [])
