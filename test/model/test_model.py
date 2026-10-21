# Layer 1: headless model tests -- loading and save/reload stability
# (no display required).

from __future__ import print_function

import os

import pytest

import testsupport


def save_document(doc, path):
    """Save a document in the native .sk format, headlessly."""
    sk = testsupport.sketch()
    from Sketch import plugins
    saver = plugins.find_export_plugin(plugins.guess_export_plugin('.sk'))
    saver(doc, path)


@pytest.mark.parametrize('name', testsupport.fixtures())
def test_fixture_loads(name):
    path = testsupport.data_path(name)
    doc = testsupport.load_document(path)
    assert len(doc.layers) >= 1, '%s: no layers' % name
    info = doc.DocumentInfo()
    assert '%d layers' % len(doc.layers) in info


@pytest.mark.parametrize('name', testsupport.fixtures())
def test_save_reload_stable(name):
    # load -> save -> reload -> save: the second save must reproduce the
    # first (modulo trailing whitespace and the unstable id() embedded
    # in bm() directives).  A failure means the loader/saver pair is not
    # round-trip stable.
    doc = testsupport.load_document(testsupport.data_path(name))
    out1 = testsupport.output_path('sk', name)
    save_document(doc, out1)
    doc2 = testsupport.load_document(out1)
    out2 = testsupport.output_path('sk', name + '.rt.sk')
    save_document(doc2, out2)
    with open(out1) as f:
        first = testsupport.normalize_sk(f.read())
    with open(out2) as f:
        second = testsupport.normalize_sk(f.read())
    assert first == second, \
        ('%s: .sk round trip is not stable' % name)


@pytest.mark.parametrize('name', testsupport.fixtures())
def test_fixture_baseline(name):
    # The saved .sk must match the artifact recorded from the baseline
    # (master) build.  This is the strongest format regression net.
    doc = testsupport.load_document(testsupport.data_path(name))
    out = testsupport.output_path('sk', name)
    save_document(doc, out)
    testsupport.compare_text('sk', name, out, normalize=testsupport.normalize_sk)
