# Layer 2: format tests -- converter output against baselines recorded
# from the master build.  SVG export is tested in test_svg.py, SVG
# import in test_svgimport.py.


import os
import subprocess
import sys

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


@pytest.mark.parametrize('ext, magic, args', [
    ('.pdf', b'%PDF', []),
    ('.svg', b'<?xml', []),
    ('.wmf', b'\xd7\xcd\xc6\x9a', []),
    # the format independently of the extension, with options
    ('.out', b'<?xml', ['-f', 'svg', '-o', 'flavour=plain',
                        '-o', 'box=bounding']),
])
def test_skconvert(ext, magic, args):
    """The skconvert script of the build tree must convert with the
    default options of the format, or those given with -o, without
    asking for them."""
    out = testsupport.output_path('skconvert', 'tarr' + ext)
    if os.path.exists(out):
        os.remove(out)
    result = run_skconvert(args + [testsupport.data_path('tarr.sk'), out])
    assert result.returncode == 0, result.stderr
    assert result.stdout == b''
    with open(out, 'rb') as f:
        data = f.read()
    assert data.startswith(magic)
    if args:
        assert b'inkscape:' not in data
        # the bounding box, not the A4 page
        assert b'width="595' not in data


def run_skconvert(args):
    script = os.path.join(testsupport.build_scripts(), 'skconvert')
    return subprocess.run([sys.executable, script] + args,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def test_skconvert_options_and_errors():
    result = run_skconvert(['--options', '-f', 'PDF'])
    assert result.returncode == 0
    assert b'0 page (default)' in result.stdout
    out = testsupport.output_path('skconvert', 'bad.pdf')
    for args in (['-o', 'box=nosuch'], ['-o', 'nosuch=1'], ['-f', 'nosuch']):
        result = run_skconvert(args + [testsupport.data_path('tarr.sk'), out])
        assert result.returncode == 1, args
        assert result.stderr.startswith(b'skconvert: '), result.stderr
    assert not os.path.exists(out)
