# Layer 2: SVG export (the Inkscape and Plain flavours of the SVG
# filter, see devdocs/svg-export.md).
#
# The visual tests rasterize the exported SVG with Inkscape and compare
# it with the ghostscript rendering of the sk2ps output of the same
# build; no recorded baselines are involved.  The structural tests
# check the editing structure of the Inkscape flavour.
#
# svgall.sk, one object of every kind the export maps, is generated
# into the output directory (svgfixture.py): the fixture data is not
# tracked, and it contains path text, which the master build used for
# recording baselines cannot load.

import math
import os
import re
import shutil
import subprocess
import xml.etree.ElementTree as ET

import pytest

import testsupport
import svgfixture


SVG = '{http://www.w3.org/2000/svg}'
XLINK_HREF = '{http://www.w3.org/1999/xlink}href'
INKSCAPE = '{http://www.inkscape.org/namespaces/inkscape}'
SODIPODI = '{http://sodipodi.sourceforge.net/DTD/sodipodi-0.dtd}'
TEXTEXT = '{http://www.iki.fi/pav/software/textext/}'
SKENCIL = '{http://www.skencil.org/namespaces/skencil}'

SVG_FIXTURES = [name for name in testsupport.fixtures()
                if name.endswith('.sk')] + ['svgall.sk']

# Fraction of (4x downsampled) pixels allowed to differ from the
# PostScript rendering, where the PostScript output is known to be
# wrong:
#   svgall: PostScript drops image alpha (devdocs/image-transparency.md).
KNOWN_DIFFERENCES = {'svgall.sk': 0.015}
DEFAULT_MAX_DIFF = 0.002

have_inkscape = shutil.which('inkscape') is not None

_svgall = []

def fixture_path(name):
    if name != 'svgall.sk':
        return testsupport.data_path(name)
    if not _svgall:
        _svgall.append(svgfixture.build(
            testsupport.output_dir('svg-fixture')))
    return _svgall[0]


FLAVOURS = {'inkscape': 0, 'plain': 1}


def export(name, flavour, options=None, document=None, suffix=''):
    testsupport.sketch()
    from Sketch.Base import plugins
    if document is None:
        document = testsupport.load_document(fixture_path(name))
    base = os.path.splitext(name)[0]
    out = testsupport.output_path('svg', '%s-%s%s.svg'
                                  % (base, flavour, suffix))
    options = dict(options or {}, flavour=FLAVOURS[flavour])
    plugins.find_export_plugin('SVG')(document, out, options=options)
    return out


def page_size(svgfile):
    root = ET.parse(svgfile).getroot()
    return [float(root.get(key)[:-2]) for key in ('width', 'height')]


def rasterize_ps(name, width, height):
    infile = fixture_path(name)
    base = os.path.splitext(name)[0]
    eps = testsupport.output_path('svg', base + '.eps')
    png = testsupport.output_path('svg', base + '-ps.png')
    # embed the fonts, as the PDF export does: ghostscript does not
    # have most of the fonts Sketch knows
    testsupport.sk2ps(infile, eps, embed_fonts=1)
    cmd = [os.environ.get('GS') or 'gs',
           '-dSAFER', '-dBATCH', '-dNOPAUSE', '-dQUIET',
           '-sDEVICE=png16m', '-r100',
           '-dTextAlphaBits=4', '-dGraphicsAlphaBits=4',
           '-dDEVICEWIDTHPOINTS=%g' % width,
           '-dDEVICEHEIGHTPOINTS=%g' % height, '-dFIXEDMEDIA',
           '-sOutputFile=%s' % png, eps]
    subprocess.check_call(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return png


def rasterize_svg(svgfile):
    png = os.path.splitext(svgfile)[0] + '.png'
    subprocess.check_call(['inkscape', svgfile, '--export-type=png',
                           '--export-dpi=100', '--export-area-page',
                           '--export-background=white',
                           '--export-background-opacity=1',
                           '--export-filename=' + png],
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return png


def difference(png_a, png_b, scale=4, tol=40):
    """Fraction of pixels differing by more than TOL after a box
    downsampling by SCALE, which removes the antialiasing differences
    of the two renderers."""
    from PIL import Image, ImageChops
    a = Image.open(png_a).convert('RGB')
    b = Image.open(png_b).convert('RGB')
    assert a.size == b.size, (a.size, b.size)
    size = (a.size[0] // scale, a.size[1] // scale)
    a = a.resize(size, Image.BOX)
    b = b.resize(size, Image.BOX)
    hist = ImageChops.difference(a, b).convert('L').histogram()
    return sum(hist[tol + 1:]) / float(size[0] * size[1])


@pytest.mark.skipif(not have_inkscape, reason='inkscape not installed')
@pytest.mark.parametrize('name', SVG_FIXTURES)
def test_plain_svg_matches_postscript(name):
    svgfile = export(name, 'plain')
    width, height = page_size(svgfile)
    frac = difference(rasterize_ps(name, width, height),
                      rasterize_svg(svgfile))
    assert frac <= KNOWN_DIFFERENCES.get(name, DEFAULT_MAX_DIFF), frac


@pytest.mark.skipif(not have_inkscape, reason='inkscape not installed')
@pytest.mark.parametrize('text', [0, 1])
def test_inkscape_svg_matches_plain(text):
    # all layers of svgall.sk that are printable are visible and vice
    # versa, except two, so compare with the Plain SVG and the hidden
    # and non-printable layers removed from both renderings
    doc = testsupport.load_document(fixture_path('svgall.sk'))
    for layer in doc.Layers():
        if not layer.is_SpecialLayer and \
           layer.Visible() != layer.Printable():
            doc.layers.remove(layer)
    plain = export('svgall.sk', 'plain', document=doc, suffix='-vis')
    ink = export('svgall.sk', 'inkscape', {'text': text},
                 document=doc, suffix='-vis%d' % text)
    frac = difference(rasterize_svg(plain), rasterize_svg(ink))
    assert frac <= DEFAULT_MAX_DIFF, frac


def parse(svgfile):
    return ET.parse(svgfile).getroot()


def all_attribute_names(root):
    for elem in root.iter():
        yield elem.tag
        for key in elem.attrib:
            yield key


def test_plain_svg_has_no_editing_structure():
    root = parse(export('svgall.sk', 'plain'))
    for name in all_attribute_names(root):
        assert not name.startswith((INKSCAPE, SODIPODI, SKENCIL, TEXTEXT)), \
               name
    assert root.find('.//' + SVG + 'text') is None
    assert root.find('.//' + SVG + 'use') is None
    for elem in root.iter():
        assert 'display:none' not in elem.get('style', '')
    # only the printable layers
    layers = [elem for elem in root if elem.tag == SVG + 'g']
    assert len(layers) == 2


def inkscape_layers(root):
    return [elem for elem in root
            if elem.get(INKSCAPE + 'groupmode') == 'layer']


def test_inkscape_layers_and_guides():
    root = parse(export('svgall.sk', 'inkscape'))
    layers = inkscape_layers(root)
    assert [layer.get(INKSCAPE + 'label') for layer in layers] \
           == ['Layer 1', 'Hidden printable', 'Notes (non-printable)']
    assert 'display:none' not in layers[0].get('style', '')
    assert 'display:none' in layers[1].get('style', '')
    assert 'display:none' not in layers[2].get('style', '')
    assert layers[2].get(SODIPODI + 'insensitive') == 'true'
    assert layers[2].get(SKENCIL + 'printable') == '0'
    view = root.find(SODIPODI + 'namedview')
    guides = sorted((g.get('position'), g.get('orientation'))
                    for g in view.findall(SODIPODI + 'guide'))
    # guide positions are stored y up from the lower left page corner
    assert guides == [('0,500', '0,1'), ('300,0', '1,0')]
    assert view.find(INKSCAPE + 'grid') is not None


def test_inkscape_structure():
    root = parse(export('svgall.sk', 'inkscape'))
    plugins = [elem.get(SKENCIL + 'plugin') for elem in root.iter()
               if elem.get(SKENCIL + 'plugin')]
    assert 'RegularPolygon' in plugins and 'LCDText' in plugins
    assert any(elem.get(SKENCIL + 'eps-file', '').endswith(
        'svgeps.eps') for elem in root.iter())
    # editable ellipse arcs
    arcs = [elem for elem in root.iter()
            if elem.get(SODIPODI + 'type') == 'arc']
    assert len(arcs) >= 2
    # text is a group of glyph paths carrying the text
    texts = [elem for elem in root.iter()
             if elem.get(SKENCIL + 'text') == 'Plain Times fi AV']
    assert len(texts) == 1 and texts[0].tag == SVG + 'g'
    assert texts[0].get('aria-label') == 'Plain Times fi AV'
    # arrows of single open paths are markers
    assert root.find('.//' + SVG + 'marker') is not None


def test_inkscape_text_mode():
    root = parse(export('svgall.sk', 'inkscape', {'text': 1},
                        suffix='-text'))
    texts = {elem.text: elem for elem in root.iter(SVG + 'text')}
    elem = texts['Plain Times fi AV']
    xs = elem.get('x').split()
    assert len(xs) == len('Plain Times fi AV')
    assert "font-family:'Nimbus Roman'" in elem.get('style')
    bold = [text for text in texts if text.startswith('Helvetica')]
    assert 'font-weight:bold' in texts[bold[0]].get('style')


def test_inkscape_clone_is_use():
    testsupport.sketch()
    from Sketch.Graphics.clone import Clone
    from Sketch import Point
    doc = testsupport.load_document(fixture_path('svgall.sk'))
    layer = doc.Layers()[0]
    original = layer.GetObjects()[0]
    clone = Clone(original)
    clone.Translate(Point(10, 20))
    # a Clone is not a GraphicsObject: Insert takes it in a list
    layer.Insert([clone], len(layer.GetObjects()))
    root = parse(export('svgall.sk', 'inkscape', document=doc,
                        suffix='-clone'))
    uses = list(root.iter(SVG + 'use'))
    assert len(uses) == 1
    ref = uses[0].get(XLINK_HREF)[1:]
    assert any(elem.get('id') == ref for elem in root.iter())
    assert uses[0].get('transform') == 'translate(10 -20)'
    plain = parse(export('svgall.sk', 'plain', document=doc, suffix='-clone'))
    assert plain.find('.//' + SVG + 'use') is None


def test_textext_attributes():
    testsupport.sketch()
    from Sketch.Plugins.Filters.svgsaver import textext_text
    root = parse(export('alphares.sk', 'inkscape'))
    groups = [elem for elem in root.iter()
              if elem.get(SKENCIL + 'plugin') == 'LtxObj']
    assert groups
    for group in groups:
        assert group.get(TEXTEXT + 'text')
        assert group.get(TEXTEXT + 'version')
        assert group.get(TEXTEXT + 'pdfconverter') == 'inkscape'
        # TexText re-renders at 10pt and reuses the node transform: it
        # must hold the scale (size / 10) and Sketch's trafo
        text, size, trafo = eval(group.get(SKENCIL + 'params'))
        a, b, c, d, e, f = map(float, re.match(
            r'matrix\((.*)\)', group.get('transform')).group(1).split())
        det = a * d - b * c
        assert det > 0
        assert abs(det - (size / 10.0) ** 2
                   * abs(trafo[0] * trafo[3] - trafo[1] * trafo[2])) < 1e-3
        assert abs(float(group.get(TEXTEXT + 'jacobian_sqrt'))
                   - math.sqrt(det)) < 1e-3
        # the rendering is kept in an inner group with the inverse
        assert len(group) == 1 and len(group[0])
        assert group[0].get('transform').startswith('matrix(')
    assert textext_text('\\noskltx$x$') == '$x$'
    assert textext_text('\\preamble|\\usepackage{bm}|$\\bm{x}$') \
           == '%\\preamble|\\usepackage{bm}|\n$\\bm{x}$'


def test_default_flavour_is_inkscape():
    # one SVG filter: the default (also of skconvert) is the Inkscape
    # flavour with all layers, Plain has only the printable ones
    testsupport.sketch()
    from Sketch.Base import plugins
    assert plugins.guess_export_plugin('.svg') == 'SVG'
    assert plugins.guess_export_plugin('.pdf') == 'PDF'
    doc = testsupport.load_document(fixture_path('svgall.sk'))
    out = testsupport.output_path('svg', 'svgall-default.svg')
    plugins.find_export_plugin('SVG')(doc, out, options={})
    assert len(inkscape_layers(parse(out))) == 3
    plain = parse(export('svgall.sk', 'plain', document=doc))
    assert not inkscape_layers(plain)
    assert len([elem for elem in plain if elem.tag == SVG + 'g']) == 2
