#!/usr/bin/env bash
# Edge-quality experiment, end to end. Safe to re-run: every stage resumes.
#   stage 0  citation backfill (must already be running/done: citations_core.json)
#   stage 1  Arm B  — decomposed pairwise labeling
#   stage 2  Arm C  — decomposed + citation signal (reuses B where identical)
#   stage 3  judging A/B/C, one blind rubric
#   stage 4  temporal mini-eval (no LLM) + blinded human queue + summary
set -uo pipefail
cd "$(dirname "$0")/../.."          # repo root
BUNDLE="${BUNDLE:-../prior-core-v0.2}"
export PRIOR_LLM_BACKEND="${PRIOR_LLM_BACKEND:-claude-cli}"
export PRIOR_MAP_WORKERS="${PRIOR_MAP_WORKERS:-6}"
EQ=experiments/edge_quality
PY="$(pwd)/.venv-exp/bin/python"    # clean venv (system numpy is shadowed)
alias python3="$PY"; python3() { "$PY" "$@"; }
log() { printf '\n[%s] == %s ==\n' "$(date +%H:%M:%S)" "$*"; }

log "stage 0: wait for citation backfill"
for _ in $(seq 1 240); do
  [ -f "$EQ/out/citations_core.json" ] && break
  sleep 30
done
[ -f "$EQ/out/citations_core.json" ] || { echo "backfill never finished — Arm C will be skipped"; }

log "stage 1: Arm B (decomposed)"
python3 "$EQ/relate_decomposed.py" --bundle "$BUNDLE" --arm B

if [ -f "$EQ/out/citations_core.json" ]; then
  log "stage 2: Arm C (decomposed + citations)"
  python3 "$EQ/relate_decomposed.py" --bundle "$BUNDLE" --arm C
  ARMS="A B C"
else
  ARMS="A B"
fi

log "stage 3: judging ($ARMS)"
python3 "$EQ/judge_edges.py" --bundle "$BUNDLE" --arms $ARMS --sample 250

log "stage 4: temporal mini-eval + human queue"
python3 "$EQ/temporal_holdout.py" --bundle "$BUNDLE" || echo "(temporal eval failed — non-blocking)"
python3 "$EQ/make_human_queue.py" --bundle "$BUNDLE" --per-arm 15

log "ALL DONE — outputs in $EQ/out/ (judge_summary.json is the headline)"
