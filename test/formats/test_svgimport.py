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
# ghostscript renders the glyphs of TeX fonts slightly bolder
LATEX_MAX_DIFF = 0.004


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


# Real-world files in test/data/svgimport (not regenerable: skipped
# when missing).
DATA_FILES = ['becuse.svg']    # Inkscape 1.3 from PDF: flipped text


@pytest.mark.skipif(not have_inkscape, reason='inkscape not installed')
@pytest.mark.parametrize('name', DATA_FILES)
def test_data_file(name):
    path = testsupport.data_path(os.path.join('svgimport', name))
    if not os.path.exists(path):
        pytest.skip('%s missing' % path)
    compare_with_inkscape(path, 'svgimport')


# Fraction of differing pixels allowed for the round trips where the
# import is known to be inexact.
ROUND_TRIP_DIFFERENCES = {}


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


LATEX = r'''\documentclass{article}
\usepackage{xcolor}
\usepackage{tikz}
\pagestyle{empty}
\begin{document}
Text with math $\int_0^\infty e^{-x^2}\,dx = \frac{\sqrt{\pi}}{2}$,
\textcolor{red}{red text}, a rule \rule{1cm}{2pt} and ligatures: fi ffl.
\[ \sum_{k=1}^n k^2 = \frac{n(n+1)(2n+1)}{6} \]
\begin{tikzpicture}
\fill[blue!30] (0,0) rectangle (2,1);
\fill[red, opacity=0.5] (3,0.5) circle (0.4);
\begin{scope}
\clip (5,0.5) circle (0.5);
\fill[orange] (4.5,0) rectangle (5.3,1);
\end{scope}
\draw[->, thick, dashed] (0,-0.3) -- (4,-0.3);
\end{tikzpicture}
\end{document}
'''

have_latex = all(shutil.which(tool) for tool in ('latex', 'pdflatex',
                                                 'dvips'))

_latex = {}

def latex_outputs():
    """The DVI, EPS and PDF of LATEX (once per session)."""
    if not _latex:
        dir = testsupport.output_dir('svgimport-latex')
        with open(os.path.join(dir, 't.tex'), 'w') as f:
            f.write(LATEX)
        for cmd in (['latex', '-interaction=batchmode', 't.tex'],
                    ['pdflatex', '-interaction=batchmode', 't.tex'],
                    ['dvips', '-q', '-E', 't.dvi', '-o', 't.eps']):
            subprocess.check_call(cmd, cwd = dir, stdout = subprocess.PIPE,
                                  stderr = subprocess.PIPE)
        _latex['dir'] = dir
    return _latex['dir']


def dvisvgm(dir, args, out):
    out = os.path.join(dir, out)
    subprocess.check_call(['dvisvgm'] + args + ['-o', out], cwd = dir,
                          stdout = subprocess.PIPE, stderr = subprocess.PIPE)
    return out


@pytest.mark.skipif(not (have_dvisvgm and have_inkscape and have_latex),
                    reason='dvisvgm, inkscape or latex not installed')
@pytest.mark.parametrize('variant', ['nofonts', 'eps', 'pdf'])
def test_dvisvgm_latex(variant):
    """LaTeX output through dvisvgm: glyphs as paths (DVI with
    --no-fonts, EPS, PDF)."""
    dir = latex_outputs()
    args = {'nofonts': ['--no-fonts', 't.dvi'],
            'eps': ['-E', '--no-fonts', 't.eps'],
            'pdf': ['--pdf', '--no-fonts', 't.pdf']}[variant]
    out = dvisvgm(dir, args, 't-%s.svg' % variant)
    compare_with_inkscape(out, 'svgimport-latex', LATEX_MAX_DIFF)


@pytest.mark.skipif(not (have_dvisvgm and have_inkscape and have_latex),
                    reason='dvisvgm, inkscape or latex not installed')
def test_dvisvgm_svg_fonts():
    """dvisvgm's default output (SVG fonts, which Inkscape does not
    render): compared with Inkscape's rendering of the --no-fonts
    output."""
    dir = latex_outputs()
    fonts = dvisvgm(dir, ['t.dvi'], 't-fonts.svg')
    paths = dvisvgm(dir, ['--no-fonts', 't.dvi'], 't-paths.svg')
    doc, png = render_imported(fonts, 'svgimport-latex')
    ref = render_inkscape(paths, os.path.splitext(png)[0] + '-ref.png')
    frac = test_svg.difference(png, ref)
    assert frac <= LATEX_MAX_DIFF, (frac, doc.meta.load_messages)


# MATLAB SVG (print -dsvg), in test/data/svgimport/matlab; missing
# files are generated by matlab_svg_samples.m when MATLAB is available.
MATLAB_SAMPLES = ['bar', 'contourf', 'image', 'line', 'patch', 'scatter',
                  'surf']
# overlapping transparent patches: blended with white, not with each other
MATLAB_DIFFERENCES = {'patch': 0.07}

have_matlab = shutil.which('matlab') is not None

def matlab_sample(name):
    dir = testsupport.data_path(os.path.join('svgimport', 'matlab'))
    path = os.path.join(dir, name + '.svg')
    if not os.path.exists(path) and have_matlab:
        here = os.path.dirname(os.path.abspath(__file__))
        subprocess.call(['matlab', '-batch', "addpath('%s'); "
                         "matlab_svg_samples('%s')" % (here, dir)],
                        stdout = subprocess.PIPE, stderr = subprocess.PIPE,
                        timeout = 600)
    if not os.path.exists(path):
        pytest.skip('%s missing and MATLAB not available' % path)
    return path


@pytest.mark.skipif(not have_inkscape, reason='inkscape not installed')
@pytest.mark.parametrize('name', MATLAB_SAMPLES)
def test_matlab(name):
    compare_with_inkscape(matlab_sample(name), 'svgimport-matlab',
                          MATLAB_DIFFERENCES.get(name, DEFAULT_MAX_DIFF))
