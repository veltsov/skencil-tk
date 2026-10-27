# Layer 2: format tests -- converter output against baselines recorded
# from the master build.  SVG import/export is deliberately NOT tested
# (the SVG loader is broken on modern Pythons; fixing it is a separate
# project).


import pytest

import testsupport


@pytest.mark.parametrize('name', testsupport.fixtures())
def test_sk2ps(name):
    """sk2ps output must match the baseline EPS (byte comparison first,
    then a ghostscript raster comparison)."""
    infile = testsupport.data_path(name)
    out = testsupport.output_path('eps', name + '.eps')
    testsupport.sk2ps(infile, out)
    testsupport.compare_eps('eps', name, out)


def test_fig_import():
    """The XFig loader must load zz.fig into a sane document."""
    doc = testsupport.load_document(testsupport.data_path('zz.fig'))
    assert len(doc.layers) >= 1
    assert doc.DocumentInfo()
