#!/usr/bin/env bash
# Prior demo runbook. Builds one atlas, then runs the demo queries + key-free
# evals from the cached atlas. Run the BUILD step early (not live on stage);
# everything after it reads the cached atlas and is safe to run live.
#
#   export ANTHROPIC_API_KEY=...            # or: export PRIOR_LLM_BACKEND=claude-code
#   bash scripts/demo.sh                    # default topic (RAG)
#   bash scripts/demo.sh "continual learning"   # custom topic
set -euo pipefail
cd "$(dirname "$0")/.."

TOPIC="${1:-continual learning catastrophic forgetting}"
FORWARD_Q="${FORWARD_Q:-Do regularization-based methods prevent catastrophic forgetting in continual learning?}"
NOINFO_Q="${NOINFO_Q:-Does continual learning reduce data-center energy consumption?}"
CONCEPT="${CONCEPT:-catastrophic forgetting}"
MAX_PAPERS="${MAX_PAPERS:-20}"
CITE_HOPS="${CITE_HOPS:-1}"   # expand backward along citations so origin tracing reaches true origins (e.g. 1989)

run() { echo; echo "════ $1"; shift; PYTHONPATH=src python3 -m prior.cli "$@"; }

echo "TOPIC: $TOPIC   (backend=${PRIOR_LLM_BACKEND:-api}, max_papers=$MAX_PAPERS)"

echo; echo "════ [BUILD] ingest → read → map  (do this EARLY, not on stage)"
PYTHONPATH=src python3 -m prior.cli build "$TOPIC" --max-papers "$MAX_PAPERS" --cite-hops "$CITE_HOPS"

run "[INFO] atlas summary"            info
run "[1 · FORWARD] state of evidence" ask "$FORWARD_Q"
run "[2 · GRACEFUL NO] honest abstain" ask "$NOINFO_Q"
run "[3 · BACKWARD] origin tracing"   origin "$CONCEPT"

echo; echo "════ [EVALS] per-agent numbers (no credits)"
PYTHONPATH=src python3 evals/groundedness.py || true
PYTHONPATH=src python3 evals/graph_stats.py || true
PYTHONPATH=src python3 evals/origin_check.py "$CONCEPT" || true

echo; echo "Done. atlas: data/atlas/atlas.json"
