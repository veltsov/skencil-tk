# Layer 2: SVG import (devdocs/svg-import.md) -- visual comparisons.
#
# - samples: small SVG files (written into the output directory from
#   the sources in svgimport_samples.py), rasterized by Inkscape, against
#   the ghostscript rendering of the sk2ps output of the imported
#   document;
# - round trips: every fixture exported to SVG (both flavours) and
#   imported again, against the ghostscript rendering of the fixture;
# - dvisvgm: the EPS fixtures converted by dvisvgm, and LaTeX output.
#
# No recorded baselines are involved; the external tools are skipped
# when missing.

import os
import shutil
import subprocess
import sys

import pytest

import testsupport
import test_svg
import svgimport_samples


have_inkscape = shutil.which('inkscape') is not None
have_dvisvgm = shutil.which('dvisvgm') is not None

# fraction of (4x downsampled) pixels allowed to differ
DEFAULT_MAX_DIFF = 0.002


def svgimport():
    from Sketch.Plugins.Filters.Lib import svgimport
    return svgimport


def gs_render(eps, png, width, height):
    cmd = [os.environ.get('GS') or 'gs',
           '-dSAFER', '-dBATCH', '-dNOPAUSE', '-dQUIET',
           '-sDEVICE=png16m', '-r100',
           '-dTextAlphaBits=4', '-dGraphicsAlphaBits=4',
           '-dDEVICEWIDTHPOINTS=%g' % width,
           '-dDEVICEHEIGHTPOINTS=%g' % height, '-dFIXEDMEDIA',
           '-sOutputFile=%s' % png, eps]
    subprocess.check_call(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return png


def render_imported(svgfile, kind, **options):
    """Import SVGFILE, save it as .sk and render it through sk2ps and
    ghostscript.  Returns (document, png)."""
    from Sketch.Base import plugins
    doc = svgimport().import_svg(svgfile, **options)
    base = testsupport.output_path(kind, os.path.splitext(
        os.path.basename(svgfile))[0] + '-imported')
    plugins.find_export_plugin('SK-1')(doc, base + '.sk')
    testsupport.sk2ps(base + '.sk', base + '.eps', embed_fonts=1)
    width, height = doc.PageSize()
    return doc, gs_render(base + '.eps', base + '.png', width, height)


def render_inkscape(svgfile, png):
    subprocess.check_call(['inkscape', svgfile, '--export-type=png',
                           '--export-dpi=100', '--export-area-page',
                           '--export-background=white',
                           '--export-background-opacity=1',
                           '--export-filename=' + png],
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return png


def compare_with_inkscape(svgfile, kind, max_diff = DEFAULT_MAX_DIFF,
                          **options):
    doc, png = render_imported(svgfile, kind, **options)
    ref = render_inkscape(svgfile, os.path.splitext(png)[0] + '-ref.png')
    frac = test_svg.difference(png, ref)
    assert frac <= max_diff, (frac, doc.meta.load_messages)
    return doc


@pytest.mark.skipif(not have_inkscape, reason='inkscape not installed')
@pytest.mark.parametrize('name', sorted(svgimport_samples.SAMPLES))
def test_sample(name):
    source, max_diff = svgimport_samples.SAMPLES[name]
    svgfile = svgimport_samples.write(name, testsupport.output_dir(
        'svgimport'))
    compare_with_inkscape(svgfile, 'svgimport', max_diff)


# Fraction of differing pixels allowed for the round trips where the
# import is known to be inexact.
ROUND_TRIP_DIFFERENCES = {
    ('tarr.sk', 'inkscape'): 0.01,      # markers (not yet)
    ('svgall.sk', 'inkscape'): 0.006,
}


@pytest.mark.parametrize('flavour', ['plain', 'inkscape'])
@pytest.mark.parametrize('name', test_svg.SVG_FIXTURES)
def test_round_trip(name, flavour):
    svgfile = test_svg.export(name, flavour)
    width, height = test_svg.page_size(svgfile)
    ref = test_svg.rasterize_ps(name, width, height)
    doc, png = render_imported(svgfile, 'svgimport-rt')
    assert doc.PageSize() == pytest.approx((width, height), abs=0.01)
    frac = test_svg.difference(ref, png)
    assert frac <= ROUND_TRIP_DIFFERENCES.get((name, flavour),
                                              DEFAULT_MAX_DIFF), \
        (frac, doc.meta.load_messages)


@pytest.mark.skipif(not (have_dvisvgm and have_inkscape),
                    reason='dvisvgm or inkscape not installed')
@pytest.mark.parametrize('name', ['oms.eps', 'prefactor_vs_pressure.eps'])
def test_dvisvgm_eps(name):
    """EPS files (Grace, MATLAB) converted by dvisvgm."""
    out = testsupport.output_path('svgimport', os.path.splitext(name)[0]
                                  + '-dvisvgm.svg')
    subprocess.check_call(['dvisvgm', '-E', '--no-fonts', '-o', out,
                           testsupport.data_path(name)],
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    doc = compare_with_inkscape(out, 'svgimport')
    assert not doc.meta.load_messages
