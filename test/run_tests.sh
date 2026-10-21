#!/bin/sh
# Run the skencil-tk test suite.
#
# Usage:
#   test/run_tests.sh                 # compare against baselines
#   test/run_tests.sh --record       # regenerate baselines from master
#   test/run_tests.sh [pytest args]  # e.g. test/run_tests.sh -k tarr
#
# With --record a worktree of the `master' branch at the revision
# recorded in test/baselines/BASELINE-REV (or the current master tip if
# the file does not exist yet) is built and the suite runs against it
# in record mode; all golden artifacts are (re)written.

set -e

TEST_DIR=$(cd "$(dirname "$0")" && pwd)
REPO_ROOT=$(dirname "$TEST_DIR")
cd "$REPO_ROOT"

PYTHON=${PYTHON:-python2}

if [ "$1" = "--record" ]; then
    shift
    REV=$($PYTHON -c "import subprocess;print(subprocess.check_output(['git','rev-parse','master']).strip()[:12])")
    WORKTREE=/tmp/skencil-baseline-$REV
    if [ ! -d "$WORKTREE" ]; then
        echo "Creating baseline worktree $WORKTREE (master @ $REV)"
        git worktree add "$WORKTREE" master
    fi
    if [ ! -d "$WORKTREE"/build/lib.linux* ]; then
        echo "Building baseline (this may take a while)..."
        (cd "$WORKTREE" && $PYTHON setup.py build)
    fi
    mkdir -p "$TEST_DIR/baselines"
    echo "$REV" > "$TEST_DIR/baselines/BASELINE-REV"
    export SKENCIL_TEST_BUILD="$WORKTREE/build"
    export SKENCIL_TEST_RECORD=1
    echo "Recording baselines from master @ $REV"
else
    # staleness check: warn when baselines are older than master
    if [ -f "$TEST_DIR/baselines/BASELINE-REV" ]; then
        STORED=$(cat "$TEST_DIR/baselines/BASELINE-REV")
        CURRENT=$(git rev-parse master | cut -c1-12)
        if [ "$STORED" != "$CURRENT" ]; then
            echo "NOTE: baselines were recorded from master @ $STORED," \
                 "but master is now @ $CURRENT." >&2
            echo "      Consider running \`test/run_tests.sh --record'." >&2
        fi
    fi
fi

exec $PYTHON -m pytest "$@" "$TEST_DIR"
