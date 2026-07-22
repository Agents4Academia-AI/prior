#!/bin/bash
# Weekly freshness scan (launchd: com.prior.refresh-scan).
# Date-windowed search of the watched topics since each topic's watermark;
# writes proposed papers to data/refresh/pending/ for human review — never
# touches the graph. Review + ingest with:
#   prior refresh pending
#   prior refresh approve <batch-id> [--skip N]
set -u
REPO="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO"

# Watched topics — edit this list to change coverage.
TOPICS=(
    "in-context learning"
    "autonomous research agents"
)

ARGS=()
for t in "${TOPICS[@]}"; do ARGS+=(--topic "$t"); done

LOG="$REPO/data/refresh/scan.log"
mkdir -p "$(dirname "$LOG")"
{
    echo "==== scan $(date '+%Y-%m-%d %H:%M') ===="
    PYTHONPATH=src python3 -m prior.cli refresh scan "${ARGS[@]}" --per-topic 25
    PYTHONPATH=src python3 -m prior.cli refresh pending
} >> "$LOG" 2>&1

# Desktop nudge when something new is waiting for review.
if ls "$REPO"/data/refresh/pending/*.json >/dev/null 2>&1; then
    n=$(PYTHONPATH=src python3 -c "
from prior import refresh
print(sum(len(b['papers']) for b in refresh.pending(progress=lambda *_: None)))")
    osascript -e "display notification \"$n paper(s) pending review — prior refresh pending\" with title \"Prior weekly scan\"" 2>/dev/null || true
fi
