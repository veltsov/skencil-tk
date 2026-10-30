# -*- coding: utf-8 -*-
# Layer 3 regression: the LaTeX plugin with the external tools MISSING
# (e.g. no TeX installed -- the usual AppImage case, where pstoedit and
# ghostscript are bundled but the TeX toolchain is not).
#
# An exception raised in the plugin's error report used to escape
# recompute(); the plugin undo machinery caught it and re-applied the
# parameters, re-running the recompute each time -- an endless loop
# (356k toolchain attempts and 241 MB of console output in 20 seconds
# in the repro).  Now both the edit and the create flow must complete
# with exactly one message box per flow and no traceback anywhere.
# Runs the full application under Xvfb with a PATH shim that hides the
# TeX tools; SKENCIL_TEST_HEADLESS=1 makes the MessageBox stub answer
# Cancel instead of blocking on the modal dialog.

import os
import tempfile

import pytest

import testsupport

SCRIPTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'scripts')

# the tools whose absence triggers the bug (pstoedit/gs stay available,
# so the pre-check reports exactly these)
MISSING = ('pdflatex', 'latex', 'dvips')


def _shim_path():
    """Create a temp directory with symlinks to all executables of the
    current PATH except MISSING, and return it (as a PATH value)."""
    shim = tempfile.mkdtemp(prefix = 'skencil-ltex-shim-')
    linked = set()
    for dir_ in os.environ.get('PATH', '').split(os.pathsep):
        if not dir_:
            continue
        try:
            entries = os.listdir(dir_)
        except OSError:
            continue
        for name in entries:
            if name in MISSING or name in linked:
                continue
            path = os.path.join(dir_, name)
            if not os.path.isfile(path) or not os.access(path, os.X_OK):
                continue
            try:
                os.symlink(path, os.path.join(shim, name))
                linked.add(name)
            except OSError:
                pass
    return shim


def test_latex_missing_tools_no_loop():
    script = os.path.join(SCRIPTS, 'latex_missing.py')
    env = {'SKENCIL_TEST_HEADLESS': '1',
           'PATH': _shim_path()}
    rc, app_out, app_err = testsupport.run_app(
        [testsupport.data_path('rustext.sk')],
        script = script, script_env = env, timeout = 120)
    stdout = app_out.decode('utf-8', 'replace')
    stderr = app_err.decode('utf-8', 'replace')
    assert rc == 0, ('application exited with %d\nstdout:\n%s\nstderr:\n%s'
                     % (rc, stdout, stderr))
    # the recompute failure must be a rejected update: the change is
    # reported once, the object is untouched (same group and children,
    # parameters unchanged), no undo entry is added, and the create
    # flow places no object
    assert 'LTXMISSING: rejected=1 intact=True' in stdout, \
        'the failed update was not rejected cleanly\nstdout:\n%s' % stdout
    assert 'undo-unchanged=True' in stdout, \
        'the failed update left an undo entry\nstdout:\n%s' % stdout
    assert 'create-rejected=1' in stdout, \
        'the rejected create flow behaved unexpectedly\nstdout:\n%s' % stdout
    # one message box per failed apply: edit flow, create flow
    assert stdout.count('MessageBox:') == 2, \
        'expected exactly one message box per failed apply\nstdout:\n%s' % stdout
    # the recompute error report must not have raised anywhere
    assert 'Traceback' not in stdout, 'traceback on stdout:\n%s' % stdout
    assert 'Traceback' not in stderr, 'traceback on stderr:\n%s' % stderr
