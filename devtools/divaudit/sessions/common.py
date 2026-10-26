# Shared bootstrap for the headless division-audit sessions (see
# devtools/divaudit/ and devdocs/python3-porting.md).  Mirrors
# test/testsupport.py: put the build tree on sys.path and initialize
# Sketch without Tk.

import glob
import os
import sys


def repo_root():
    return os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.dirname(os.path.abspath(__file__)))))


def build_lib():
    root = os.environ.get('SKENCIL_TEST_BUILD',
                          os.path.join(repo_root(), 'build'))
    candidates = sorted(glob.glob(os.path.join(root, 'lib.*-2.7')))
    if not candidates:
        raise RuntimeError('no build tree found under %s '
                           '(run `python2 setup.py build` first)' % root)
    return candidates[0]


def bootstrap():
    lib = build_lib()
    if lib not in sys.path:
        sys.path.insert(0, lib)
    import Sketch
    Sketch.init_lib()
    return Sketch


def load_document(path):
    from Sketch.Base import load
    return load.load_drawing(path)


def step(name, fn):
    """Run one exercise step, reporting failures without aborting."""
    try:
        fn()
        print '  OK   %s' % name
        return True
    except Exception:
        print '  FAIL %s' % name
        import traceback
        traceback.print_exc()
        return False
