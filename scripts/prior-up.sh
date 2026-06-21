#!/usr/bin/env bash
# Start the three `prior` server processes ON ziz4 (Neo4j + API + UI).
# Run this on ziz4, then tunnel from your laptop with prior-tunnel.sh.
set -euo pipefail

REPO=/vols/bitbucket/stat0531/workspace/prior
NEO4J=/vols/bitbucket/stat0531/opt/neo4j
API_PORT=8078
UI_PORT=5175

echo "[1/3] Neo4j ..."
"$NEO4J/bin/neo4j" start || true        # no-op if already running

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
echo "now tunnel from your laptop:  ./prior-tunnel.sh"
