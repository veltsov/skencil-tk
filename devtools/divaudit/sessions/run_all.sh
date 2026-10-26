#!/bin/sh
# Run all division-audit exercise sessions under the audit wrapper,
# one warning log per session, then merge everything into the report.
#
# Usage: devtools/divaudit/sessions/run_all.sh
#
# Logs: /tmp/divaudit/session-{model,load,ui}.jsonl
#       (merged with the pytest baseline /tmp/divaudit/runtime.jsonl)

set -e
REPO=$(cd "$(dirname "$0")/../../.." && pwd)
cd "$REPO"

DIVDIR=devtools/divaudit
LOGDIR=${DIVAUDIT_LOGDIR:-/tmp/divaudit}
mkdir -p "$LOGDIR"

run() {
    log=$1; shift
    echo "=== $log: $*"
    DIVAUDIT_LOG="$LOGDIR/$log" "$DIVDIR/python2-divaudit" "$@"
}

# 1. headless model session: build, save all formats, raster render
run session-model.jsonl "$DIVDIR/sessions/build_rich.py"

# 2. headless loader session: all fixtures + synthetic samples
run session-load.jsonl "$DIVDIR/sessions/load_foreign.py"

# 3. live app session under Xvfb: the whole app runs in the
#    instrumented process, so viewport/canvas/ruler/dialog math is
#    covered too (the UI tests' subprocess blind spot does not apply
#    here because we control the launch)
xvfb-run -a -s '-screen 0 1024x768x24' \
    env DIVAUDIT_LOG="$LOGDIR/session-ui.jsonl" \
    "$DIVDIR/python2-divaudit" \
    build/scripts-2.7/skencil --geometry=900x650+0+0 \
    --run-script="$DIVDIR/sessions/ui_exercise.py"

# 4. merged report: pytest baseline + all sessions
echo "=== merged report"
python2 "$DIVDIR/report.py" -s "$LOGDIR/static.json" \
    -r "$LOGDIR/runtime.jsonl" \
    -r "$LOGDIR/session-model.jsonl" \
    -r "$LOGDIR/session-load.jsonl" \
    -r "$LOGDIR/session-ui.jsonl"
