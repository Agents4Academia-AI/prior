#!/usr/bin/env bash
# Start/stop/check the prior stack (Neo4j + API + UI) on ziz4.
# Then tunnel from your laptop with prior-tunnel.sh.
# Works from any checkout — the repo dir is auto-detected from this script.
#   ./scripts/prior-ctl.sh start | stop | status
set -euo pipefail
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
API_PORT="${PRIOR_API_PORT:-8078}"; UI_PORT="${PRIOR_UI_PORT:-5175}"

# Neo4j home: $PRIOR_NEO4J_HOME, else the shared install, else `neo4j` on PATH.
neo4j_bin() {
    if [ -n "${PRIOR_NEO4J_HOME:-}" ]; then echo "$PRIOR_NEO4J_HOME/bin/neo4j"
    elif [ -x /vols/bitbucket/stat0531/opt/neo4j/bin/neo4j ]; then echo /vols/bitbucket/stat0531/opt/neo4j/bin/neo4j
    elif command -v neo4j >/dev/null; then echo neo4j
    else echo "Neo4j not found — set PRIOR_NEO4J_HOME=/path/to/neo4j (see docs/RUNNING.md)" >&2; exit 1
    fi
}

start() {
    echo "repo: $REPO"
    echo "[1/3] Neo4j ..."
    "$(neo4j_bin)" start || true        # no-op if already running

    echo "[2/3] API (:$API_PORT) ..."
    cd "$REPO"
    PYTHONPATH=src PRIOR_LLM_BACKEND="${PRIOR_LLM_BACKEND:-claude-cli}" \
        nohup python -m prior.cli serve --port "$API_PORT" > /tmp/prior-api.log 2>&1 &
    echo $! > /tmp/prior-api.pid

    echo "[3/3] UI (:$UI_PORT) ..."
    cd "$REPO/frontend"; [ -d node_modules ] || npm install
    nohup env VITE_API_BASE="http://127.0.0.1:$API_PORT" \
          npx vite --port "$UI_PORT" --host 127.0.0.1 > /tmp/prior-ui.log 2>&1 &
    echo $! > /tmp/prior-ui.pid
    echo "started  api:$API_PORT ui:$UI_PORT  (logs in /tmp/prior-{api,ui}.log)"
    echo "now tunnel from your laptop:  ./scripts/prior-tunnel.sh"
}

stop() {   # leaves Neo4j running — it's shared
    for p in api ui; do
        f=/tmp/prior-$p.pid
        [ -f "$f" ] && kill "$(cat "$f")" 2>/dev/null && echo "stopped $p" || echo "$p not running"
        rm -f "$f"
    done
}

case "${1:-}" in
    start) start ;;
    stop)  stop ;;
    status) "$(neo4j_bin)" status >/dev/null 2>&1 && echo "neo4j up" || echo "neo4j down"
            for p in api ui; do f=/tmp/prior-$p.pid
            [ -f "$f" ] && kill -0 "$(cat "$f")" 2>/dev/null && echo "$p up" || echo "$p down"; done ;;
    *) echo "usage: $0 {start|stop|status}" >&2; exit 1 ;;
esac
