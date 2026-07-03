#!/usr/bin/env bash
# Open SSH tunnels to the `prior` web app on ziz4, then open it locally.
# Run this ON YOUR LAPTOP. The servers must already be running on ziz4
# (see scripts/prior-ctl.sh). UI -> 5175; API -> 8078 (the browser hits the API
# directly via VITE_API_BASE, so both ports must be forwarded).
set -euo pipefail

HOST="${PRIOR_HOST:-ziz4}"      # the Host alias in your ~/.ssh/config (ProxyJump handled there)
UI_PORT="${PRIOR_UI_PORT:-5175}"
API_PORT="${PRIOR_API_PORT:-8078}"

echo "Tunneling $HOST: UI :$UI_PORT, API :$API_PORT  (Ctrl-C to stop) ..."
ssh -N -L "$UI_PORT:127.0.0.1:$UI_PORT" -L "$API_PORT:127.0.0.1:$API_PORT" "$HOST" &
SSH_PID=$!
trap 'kill $SSH_PID 2>/dev/null || true' EXIT

# wait for the UI to answer through the tunnel, then open it
for _ in $(seq 1 30); do
  if curl -s "http://127.0.0.1:$UI_PORT" >/dev/null 2>&1; then break; fi
  sleep 1
done

URL="http://127.0.0.1:$UI_PORT"
echo "Opening $URL"
if command -v open >/dev/null;     then open "$URL"          # macOS
elif command -v xdg-open >/dev/null; then xdg-open "$URL"     # Linux
else echo "Open $URL in your browser."; fi

wait $SSH_PID
