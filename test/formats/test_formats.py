# Layer 2: format tests -- converter output against baselines recorded
# from the master build.  SVG export is tested in test_svg.py; SVG
# import is deliberately NOT tested (the SVG loader is broken on modern
# Pythons; fixing it is a separate project).


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


def test_gzip_load():
    """A gzip-compressed drawing must load headless and convert with
    sk2ps (regression guard: the loader read a meta info default that
    only the UI installed)."""
    import gzip
    infile = testsupport.data_path('tarr.sk')
    gz = testsupport.output_path('gzip', 'tarr.sk.gz')
    with open(infile, 'rb') as src, gzip.open(gz, 'wb') as dst:
        dst.write(src.read())
    doc = testsupport.load_document(gz)
    assert doc.meta.compressed == 'gzip'
    assert doc.meta.compressed_file == gz
    plain = testsupport.load_document(infile)
    assert [len(layer.GetObjects()) for layer in doc.layers] \
           == [len(layer.GetObjects()) for layer in plain.layers]
    out = testsupport.output_path('gzip', 'tarr.eps')
    testsupport.sk2ps(gz, out)
    with open(out, 'rb') as f:
        assert f.read().startswith(b'%!PS-Adobe')
