#!/bin/bash
# Vocabulary-collapse experiment orchestrator: generate -> match -> analyze.
# Fully resumable: re-running mops up failed calls at every stage.
set -u
cd "$(dirname "$0")/../.."          # repo root (prior-exp)
PY="$(pwd)/.venv-exp/bin/python"
BUNDLE="$(pwd)/../prior-core-v0.2"
EXP="experiments/vocab_collapse"
export PRIOR_LLM_BACKEND=claude-cli
export PRIOR_MAP_WORKERS="${PRIOR_MAP_WORKERS:-5}"

log() { echo "[$(date +%H:%M:%S)] $*"; }

mkdir -p "$EXP/out"
if [ ! -f "$EXP/out/clusters.json" ]; then
  log "== stage 0: canonical clusters =="
  $PY scripts/cluster_core.py "$BUNDLE" "$EXP/out" || exit 1
fi

log "== stage 1: raw-LLM generation =="
$PY "$EXP/generate_claims.py" --calls-per-prompt 12 --k 15 || true
$PY "$EXP/generate_claims.py" --calls-per-prompt 12 --k 15   # mop-up pass

log "== stage 2: strict matching against atlas =="
$PY "$EXP/match_claims.py" --bundle "$BUNDLE" || true
$PY "$EXP/match_claims.py" --bundle "$BUNDLE"                # mop-up pass

log "== stage 3: analysis =="
$PY "$EXP/analyze_collapse.py" --bundle "$BUNDLE"

log "== ALL DONE — $EXP/out/collapse_summary.json =="
