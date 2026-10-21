#!/usr/bin/python
# Regenerate the golden (baseline) artifacts for one or more fixtures,
# or for all fixtures.
#
# Usage: record.py [FIXTURE ...]        (default: all fixtures)
#
# The build tree used is (in this order of preference):
#   1. $SKENCIL_TEST_BUILD
#   2. a worktree build of the revision in test/baselines/BASELINE-REV
#      (as created by run_tests.sh --record)
#   3. the repository's own build tree (with a warning -- baselines
#      must come from master, not from a development branch!)
#
# Recording must be enabled with --record; without it this script just
# compares against the existing baselines.

from __future__ import print_function

import glob
import os
import subprocess
import sys

TEST_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, TEST_DIR)

import testsupport


def baseline_build():
    env = os.environ.get('SKENCIL_TEST_BUILD')
    if env:
        return env, 'from SKENCIL_TEST_BUILD'
    rev = None
    if os.path.exists(testsupport.BASELINE_REV_FILE):
        with open(testsupport.BASELINE_REV_FILE) as f:
            rev = f.read().strip()
    if rev:
        worktree = '/tmp/skencil-baseline-%s' % rev
        pattern = os.path.join(worktree, 'build', 'lib.*-2.7')
        if glob.glob(pattern):
            return os.path.join(worktree, 'build'), 'master worktree %s' % rev
    print('WARNING: no baseline (master) build found; using the '
          'repository build tree', file=sys.stderr)
    return os.path.join(testsupport.REPO_ROOT, 'build'), 'repository build'


def main():
    names = [a for a in sys.argv[1:] if not a.startswith('-')]
    build, source = baseline_build()
    if not names:
        names = testsupport.fixtures()
    print('recording baselines for %s (build: %s)'
          % (', '.join(names), source))
    env = dict(os.environ)
    env['SKENCIL_TEST_BUILD'] = build
    env['SKENCIL_TEST_RECORD'] = '1'
    cmd = [sys.executable, '-m', 'pytest', '-q', '-s', 'test/']
    for name in names:
        key = os.path.splitext(os.path.basename(name))[0]
        cmd += ['-k', key]
    return subprocess.call(cmd, cwd=testsupport.REPO_ROOT, env=env)


if __name__ == '__main__':
    sys.exit(main())
