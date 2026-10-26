#!/bin/sh
# Start an audited INTERACTIVE skencil session: the whole app runs
# under the -Qwarnall wrapper, so every `/` with an integer operand
# reached by the mouse/keyboard session is recorded.
#
# Usage:  devtools/divaudit/sessions/run_interactive.sh [skencil args]
# e.g.:   devtools/divaudit/sessions/run_interactive.sh /tmp/divaudit/out/rich.sk
#
# Requires a running X display (the real desktop is fine).  Follow
# devtools/divaudit/sessions/interactive-scenario.txt while operating.
# Quit the app with File > Quit when done, then hand the log to the
# analysis step.
#
# Log: /tmp/divaudit/session-interactive.jsonl
#      (deleted on each start; merged later with report.py -r)

set -e
REPO=$(cd "$(dirname "$0")/../../.." && pwd)
cd "$REPO"

LOGDIR=${DIVAUDIT_LOGDIR:-/tmp/divaudit}
LOG="$LOGDIR/session-interactive.jsonl"
mkdir -p "$LOGDIR" "$LOGDIR/out"
if [ -f "$LOG" ]; then
    # preserve earlier (possibly crashed) session logs
    mv "$LOG" "$LOG.$(date +%Y%m%d-%H%M%S)"
fi

echo "division-audit interactive session"
echo "  log: $LOG"
echo "  do the exercise from devtools/divaudit/sessions/"
echo "  interactive-scenario.txt, then quit via File > Quit."

DIVAUDIT_LOG="$LOG" exec devtools/divaudit/python2-divaudit \
    build/scripts-2.7/skencil --geometry=900x650+0+0 "$@"
