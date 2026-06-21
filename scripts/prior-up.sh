#!/usr/bin/env bash
# Start the three `prior` server processes ON ziz4 (Neo4j + API + UI).
# Run this on ziz4, then tunnel from your laptop with prior-tunnel.sh.
# Works from any checkout — the repo dir is auto-detected from this script.
set -euo pipefail

# Repo root = parent of this script's dir (so it works from anyone's clone).
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Neo4j home: $PRIOR_NEO4J_HOME, else the shared install, else `neo4j` on PATH.
if [ -n "${PRIOR_NEO4J_HOME:-}" ]; then
    NEO4J_BIN="$PRIOR_NEO4J_HOME/bin/neo4j"
elif [ -x /vols/bitbucket/stat0531/opt/neo4j/bin/neo4j ]; then
    NEO4J_BIN=/vols/bitbucket/stat0531/opt/neo4j/bin/neo4j
elif command -v neo4j >/dev/null; then
    NEO4J_BIN=neo4j
else
    echo "Neo4j not found — set PRIOR_NEO4J_HOME=/path/to/neo4j (see docs/RUNNING.md)" >&2
    exit 1
fi

API_PORT="${PRIOR_API_PORT:-8078}"
UI_PORT="${PRIOR_UI_PORT:-5175}"

echo "repo: $REPO"
echo "[1/3] Neo4j ($NEO4J_BIN) ..."
"$NEO4J_BIN" start || true        # no-op if already running

echo "[2/3] API (:$API_PORT) ..."
cd "$REPO"
export PYTHONPATH=src
export PRIOR_LLM_BACKEND="${PRIOR_LLM_BACKEND:-claude-cli}"
nohup python -m prior.cli serve --port "$API_PORT" > /tmp/prior-api.log 2>&1 &

echo "[3/3] UI (:$UI_PORT) ..."
cd "$REPO/frontend"
[ -d node_modules ] || npm install
nohup env VITE_API_BASE="http://127.0.0.1:$API_PORT" \
      npx vite --port "$UI_PORT" --host 127.0.0.1 > /tmp/prior-ui.log 2>&1 &

sleep 3
echo "started. api:$API_PORT ui:$UI_PORT  (logs: /tmp/prior-api.log /tmp/prior-ui.log)"
echo "now tunnel from your laptop:  ./scripts/prior-tunnel.sh"
