"""Topic: THE SCIENCE OF LITERATURE SEARCH & SCOPING — a companion corpus.

Deliberately broader than the main atlas on one axis: it INCLUDES classical
(pre-LLM) information-retrieval and systematic-review search methodology, which
the main "agents for the scientific process" filter correctly rejects. Covers
the search/scoping problem WITH and WITHOUT LLMs — query formulation, recall,
stopping rules, and how search quality is evaluated.

Reflexively, this is the literature behind Prior's own Scoper + completeness
model (capture-recapture, Callaghan-style stopping).

Run in its own data dir so it never touches the main build:
    PRIOR_TOPIC=topic_search PRIOR_LLM_BACKEND=claude-code \
        PRIOR_DATA_DIR=data_search PYTHONPATH=src python3 scripts/weekend_run.py
"""

TOPIC = """THE SCIENCE OF LITERATURE SEARCH & SCOPING — methods, systems, and
evaluation for FINDING the relevant scientific literature on a topic, BOTH
classical (pre-LLM information retrieval / systematic-review search) AND modern
(LLM / agentic) approaches. The meta-problem of "what is a good search result"
and how to search comprehensively, reproducibly, and to a known recall.

IN SCOPE (the contribution is about searching/scoping the literature itself):
- query formulation: Boolean query design/optimisation for systematic reviews
  (classical AND LLM-generated); query expansion; (pseudo-)relevance feedback
- systematic review search methodology: search-strategy design and reporting
  (PRISMA-S), source/database coverage and comparison (e.g. Google Scholar vs
  others), reproducibility of searches
- screening prioritisation / technology-assisted review (TAR): active learning,
  continuous active learning, neural/dense rankers for SR screening
- STOPPING criteria & completeness: when has a search found "enough"? recall
  estimation, capture-recapture, statistical stopping rules for screening
- retrieval methods evaluated for scientific/literature search: dense & sparse
  retrieval, semantic search, citation-based retrieval, snowballing
- LLM / agentic literature search & "deep research": query reformulation with
  LLMs, retrieval-augmented literature QA, autonomous iterative search agents
- evaluation of search quality: recall/precision, nDCG, work-saved-over-sampling,
  benchmarks (CLEF TAR, TREC Total Recall) for retrieval and screening

OUT OF SCOPE: general web / e-commerce / open-domain QA search not about
scientific literature; autonomous experimentation or AI-scientist systems that
DO research (unless the contribution IS the literature-search method); a
domain-science paper that merely runs a literature review; generic recommender
systems not about papers."""

SEEDS = [
    # ── classical IR / systematic-review search ──────────────────────────────
    "Boolean query formulation systematic review search strategy",
    "systematic review search strategy design reporting PRISMA-S",
    "technology assisted review active learning screening systematic review",
    "continuous active learning high recall retrieval total recall",
    "statistical stopping criteria screening systematic review recall",
    "capture recapture estimating completeness literature search",
    "query expansion pseudo relevance feedback information retrieval",
    "Google Scholar coverage comparison systematic review searching",
    "seed driven document ranking systematic review screening",
    "citation searching snowballing systematic review methodology",
    "evaluation retrieval effectiveness recall precision literature search",
    "CLEF TAR technology assisted reviews test collection",
    # ── LLM / agentic search ─────────────────────────────────────────────────
    "large language model Boolean query systematic review search",
    "query reformulation generation large language models retrieval",
    "hypothetical document embeddings zero-shot dense retrieval HyDE",
    "query2doc query expansion large language models",
    "generative relevance feedback large language models",
    "LLM agent deep research iterative literature search scientific",
    "retrieval augmented generation scientific literature question answering",
    "dense retrieval neural ranking systematic review screening",
    "large language model automated systematic review screening",
    "autonomous literature discovery agent recall estimation",
]
