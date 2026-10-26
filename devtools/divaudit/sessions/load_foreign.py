#!/usr/bin/env python2
# Headless division-audit session: load every available sample document
# (the test/data fixtures, the rich document produced by build_rich.py
# and the synthetic samples in sessions/samples/) to exercise the
# import-filter division sites.
#
# Run:  devtools/divaudit/python2-divaudit \
#           devtools/divaudit/sessions/load_foreign.py

import glob
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import bootstrap, load_document, repo_root, step

Sketch = bootstrap()

paths = sorted(glob.glob(os.path.join(repo_root(), 'test/data', '*')))
paths += sorted(glob.glob(os.path.join(os.path.dirname(
    os.path.abspath(__file__)), 'samples', '*')))
paths += sorted(glob.glob('/tmp/divaudit/out/rich.*'))

ok = fail = 0
for path in paths:
    if os.path.isdir(path) or path.endswith('fixtures.txt'):
        continue
    name = os.path.relpath(path, repo_root())
    def load(path=path):
        doc = load_document(path)
        n = len(doc.layers)
        print '       (%d layers)' % n
    print '== load %s' % name
    if step(os.path.basename(path), load):
        ok += 1
    else:
        fail += 1

print '== loaded %d, failed %d (of %d files)' % (ok, fail, ok + fail)
