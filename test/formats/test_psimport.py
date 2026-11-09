# Layer 2: EPS, PostScript and PDF import (devdocs/ps-import.md).
#
# The inputs are generated (test/data is not tracked) or taken from
# test/data when present.  The imported document is rendered through
# sk2ps and ghostscript and compared with ghostscript's rendering of
# the original page.

import os
import shutil
import struct
import subprocess
import sys

import pytest

import testsupport
import test_svg
import test_svgimport

have_tools = all(shutil.which(tool) for tool in
                 ('pdftocairo', 'pdfinfo',
                  os.environ.get('GS') or 'gs'))
pytestmark = pytest.mark.skipif(not have_tools,
                                reason='ghostscript or poppler-utils '
                                'not installed')

DEFAULT_MAX_DIFF = 0.002


def psimport():
    testsupport.sketch()
    from Sketch.Plugins.Filters.Lib import psimport
    return psimport


# shadings, nested clips, text, a dash, CMYK, an inline image
FEATURES_EPS = b'''%!PS-Adobe-3.0 EPSF-3.0
%%BoundingBox: 20 30 320 230
%%EndComments
20 30 translate
gsave 10 10 120 80 rectclip
<< /ShadingType 2 /ColorSpace /DeviceRGB /Coords [10 0 130 0]
   /Function << /FunctionType 2 /Domain [0 1] /C0 [1 0 0] /C1 [0 0 1]
   /N 1 >> /Extend [true true] >> shfill
grestore
gsave newpath 220 50 40 0 360 arc clip
<< /ShadingType 3 /ColorSpace /DeviceRGB /Coords [220 50 0 220 50 40]
   /Function << /FunctionType 2 /Domain [0 1] /C0 [1 1 0] /C1 [0 0.5 0]
   /N 1 >> /Extend [true true] >> shfill
grestore
gsave 140 10 40 80 rectclip
gsave newpath 160 50 25 0 360 arc clip
0.2 0.6 0.2 setrgbcolor 100 0 100 100 rectfill
grestore grestore
/Times-Roman findfont 24 scalefont setfont 0 0 0.5 setrgbcolor
20 140 moveto (Text fi) show
/Helvetica-Bold findfont 18 scalefont setfont 160 140 moveto (Bold) show
[6 3] 0 setdash 2 setlinewidth 1 0 0 setrgbcolor
20 120 moveto 280 120 lineto stroke
0 1 1 0 setcmykcolor 240 160 40 30 rectfill
gsave 150 160 translate 30 30 scale
4 4 8 [4 0 0 -4 0 4] {<ff000000ff000000ffffffff00ff00ff0000ff00ff00ffff
00ffff00ff00ffff00ff00ff00ff00ffffffffff00ff0000ff>}
false 3 colorimage
grestore
showpage
%%EOF
'''

# pages of two sizes, a different mark on each
MULTI_PAGE_PS = b'''%!PS-Adobe-3.0
%%Pages: 3
%%EndComments
%%Page: 1 1
<< /PageSize [300 200] >> setpagedevice
1 0 0 setrgbcolor 20 20 100 60 rectfill
showpage
%%Page: 2 2
<< /PageSize [300 200] >> setpagedevice
0 0.6 0 setrgbcolor 150 100 80 80 rectfill
showpage
%%Page: 3 3
<< /PageSize [200 300] >> setpagedevice
0 0 1 setrgbcolor 10 250 50 40 rectfill
/Helvetica findfont 20 scalefont setfont 20 100 moveto (three) show
showpage
%%EOF
'''


def write(name, data):
    path = testsupport.output_path('psimport', name)
    with open(path, 'wb') as f:
        f.write(data)
    return path


def dos_eps(eps):
    # an EPS with the binary header of a TIFF/WMF preview (none here)
    header = b'\xc5\xd0\xd3\xc6' + struct.pack('<IIIIII', 30, len(eps),
                                               0, 0, 0, 0) + b'\xff\xff'
    return header + eps


def gs_render(args, png, width, height):
    cmd = [os.environ.get('GS') or 'gs',
           '-dSAFER', '-dBATCH', '-dNOPAUSE', '-dQUIET',
           '-sDEVICE=png16m', '-r100',
           '-dTextAlphaBits=4', '-dGraphicsAlphaBits=4',
           '-dDEVICEWIDTHPOINTS=%g' % width,
           '-dDEVICEHEIGHTPOINTS=%g' % height, '-dFIXEDMEDIA',
           '-sOutputFile=%s' % png] + args
    subprocess.check_call(cmd, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE)
    return png


def render_eps(eps, png):
    from Sketch.Lib import dscparser
    llx, lly, urx, ury = dscparser.parse_eps_file(eps).BoundingBox
    return gs_render(['-c', '<</Install {%g %g translate}>> setpagedevice'
                      % (-llx, -lly), '-f', eps],
                     png, urx - llx, ury - lly)


def render_document(doc, base):
    from Sketch.Base import plugins
    plugins.find_export_plugin('SK-1')(doc, base + '.sk')
    testsupport.sk2ps(base + '.sk', base + '.eps', embed_fonts=1)
    width, height = doc.PageSize()
    return gs_render([base + '.eps'], base + '.png', width, height)


def compare_eps(eps, max_diff=DEFAULT_MAX_DIFF, **options):
    doc = psimport().import_ps(eps, **options)
    base = os.path.splitext(eps)[0]
    png = render_document(doc, base + '-imported')
    ref = render_eps(eps, base + '-ref.png')
    frac = test_svg.difference(png, ref)
    assert frac <= max_diff, (frac, doc.meta.load_messages)
    return doc


def test_features_eps():
    doc = compare_eps(write('features.eps', FEATURES_EPS))
    assert doc.PageSize() == (300, 200)


def test_dos_eps():
    eps = write('features-dos.eps', dos_eps(FEATURES_EPS))
    doc = psimport().import_ps(eps)
    assert doc.PageSize() == (300, 200)
    ref = render_eps(write('features.eps', FEATURES_EPS),
                     testsupport.output_path('psimport', 'dos-ref.png'))
    png = render_document(doc, os.path.splitext(eps)[0] + '-imported')
    assert test_svg.difference(png, ref) <= DEFAULT_MAX_DIFF


@pytest.mark.parametrize('name', ['oms.eps', 'prefactor_vs_pressure.eps'])
def test_data_eps(name):
    """A trailing bounding box (oms.eps, Grace) and MATLAB output."""
    path = testsupport.data_path(name)
    if not os.path.exists(path):
        pytest.skip('%s missing' % path)
    eps = write(name, open(path, 'rb').read())
    compare_eps(eps)


def multi_page():
    return write('multi.ps', MULTI_PAGE_PS)


def layer_names(doc):
    return [layer.Name() for layer in doc.layers
            if not layer.is_SpecialLayer]


def test_page_selection():
    psimport_ = psimport()
    parse = psimport_.parse_pages
    assert parse('1', 5) == [1]
    assert parse('2-4', 5) == [2, 3, 4]
    assert parse('4,1,2-3', 5) == [1, 2, 3, 4]
    assert parse('3-', 5) == [3, 4, 5]
    assert parse('-2', 5) == [1, 2]
    assert parse('all', 3) == parse('', 3) == [1, 2, 3]
    from Sketch import SketchLoadError
    for bad in ('0', '6', '2-1', 'x', '1-2-3', ','):
        with pytest.raises(SketchLoadError):
            parse(bad, 5)


@pytest.mark.parametrize('page', [1, 2, 3])
def test_ps_page(page):
    ps = multi_page()
    doc = psimport().import_ps(ps, pages=str(page))
    assert layer_names(doc) == ['Layer 1']
    width, height = doc.PageSize()
    assert (width, height) == ((200, 300) if page == 3 else (300, 200))
    base = testsupport.output_path('psimport', 'multi-%d' % page)
    png = render_document(doc, base + '-imported')
    ref = gs_render(['-dFirstPage=%d' % page, '-dLastPage=%d' % page, ps],
                    base + '-ref.png', width, height)
    assert test_svg.difference(png, ref) <= DEFAULT_MAX_DIFF


def test_ps_pages_as_layers():
    doc = psimport().import_ps(multi_page(), pages='1,3')
    assert layer_names(doc) == ['Page 1', 'Page 3']
    assert doc.PageSize() == (300, 200)
    layers = [layer for layer in doc.layers if not layer.is_SpecialLayer]
    # page 3 (200 x 300) is moved by its height difference: top left
    # corners aligned
    from Sketch import CreateRGBColor
    blue = [obj for obj in testsupport.iter_objects(layers[1])
            if obj.has_fill and obj.Properties().fill_pattern.is_Solid
            and obj.Properties().fill_pattern.Color() == CreateRGBColor(0, 0, 1)]
    rect = blue[0].coord_rect
    assert (rect.left, rect.bottom, rect.right, rect.top) \
        == pytest.approx((10, 150, 60, 190), abs=0.01)
    assert 'differ in size' in doc.meta.load_messages
    group, messages = psimport().import_ps_group(multi_page(), pages='all')
    assert len(group.GetObjects()) == 3


def test_single_page_ignores_selection():
    doc = psimport().import_ps(write('features.eps', FEATURES_EPS),
                               pages='2-5')
    assert doc.PageSize() == (300, 200)


@pytest.mark.skipif(not test_svgimport.have_latex,
                    reason='latex not installed')
def test_pdflatex():
    """pdflatex output (fonts embedded in the PDF)."""
    dir = test_svgimport.latex_outputs()
    pdf = os.path.join(dir, 't.pdf')
    doc = psimport().import_ps(pdf)
    width, height = doc.PageSize()
    png = render_document(doc, testsupport.output_path(
        'psimport', 't-imported'))
    ref = gs_render([pdf], testsupport.output_path('psimport', 't-ref.png'),
                    width, height)
    frac = test_svg.difference(png, ref)
    assert frac <= test_svgimport.LATEX_MAX_DIFF, (frac,
                                                   doc.meta.load_messages)


def test_load_drawing_options():
    """The plugin: magic, options, the dialog callback and its
    cancellation, the options remembered for the session."""
    testsupport.sketch()
    from Sketch.Base import load, plugins
    from Sketch import SketchLoadCancelled
    info = load.find_import_plugin(multi_page())
    assert info.format_name == 'PostScript/PDF'
    assert info.get_default_options() == {'pages': '1'}
    doc = load.load_drawing(multi_page(), options={'pages': '2-3'})
    assert layer_names(doc) == ['Page 2', 'Page 3']
    asked = []
    def ask(info_, description, options):
        asked.append((description, dict(options)))
        return dict(options, pages='3')
    doc = load.load_drawing(multi_page(), ask_options=ask)
    assert layer_names(doc) == ['Layer 1']
    assert asked[0][0].startswith('3 pages, 300 x 200 pt')
    # the last options are the next defaults
    assert asked[0][1] == {'pages': '2-3'}
    assert info.GetOptions() == {'pages': '3'}
    with pytest.raises(SketchLoadCancelled):
        load.load_drawing(multi_page(), ask_options=lambda *args: None)
    # an EPS asks nothing
    asked[:] = []
    load.load_drawing(write('features.eps', FEATURES_EPS), ask_options=ask)
    assert not asked
    assert plugins.parse_plugin_option(info, 'pages=1,3') \
        == ('pages', '1,3')
    info.last_options = {}


def test_gzipped_options():
    import gzip
    path = testsupport.output_path('psimport', 'multi.ps.gz')
    with gzip.open(path, 'wb') as f:
        f.write(MULTI_PAGE_PS)
    testsupport.sketch()
    from Sketch.Base import load
    doc = load.load_drawing(path, options={'pages': '1-2'})
    assert layer_names(doc) == ['Page 1', 'Page 2']
    load.find_import_plugin(multi_page()).last_options = {}


def test_missing_pdftocairo(monkeypatch):
    from Sketch import SketchLoadError
    which = shutil.which
    monkeypatch.setattr(shutil, 'which', lambda cmd, *args:
                        None if cmd == 'pdftocairo' else which(cmd, *args))
    with pytest.raises(SketchLoadError, match='poppler-utils'):
        psimport().import_ps(multi_page())


def test_skconvert_input_option():
    out = testsupport.output_path('psimport', 'skconvert.sk')
    skconvert = os.path.join(testsupport.build_scripts(), 'skconvert')
    subprocess.check_call([sys.executable, skconvert, '-i', 'pages=2-3',
                           multi_page(), out])
    text = open(out).read()
    assert "layer('Page 2'" in text and "layer('Page 3'" in text
    listing = subprocess.check_output([sys.executable, skconvert,
                                       '--input-options', multi_page()])
    assert b'pages' in listing


# a figure of two image tiles, each clipped to its own rectangle (the
# rectangles overlapping by 0.1 pt) inside a common curved clip, at
# fractional positions; and an image really cropped by its clip
TILES_EPS = b'''%!PS-Adobe-3.0 EPSF-3.0
%%BoundingBox: 0 0 200 120
%%EndComments
/tile { % x w color
  /c exch def /w exch def /x exch def
  gsave x 10.27 w 60.31 rectclip
  gsave x 0.13 sub 10.2 translate w 0.3 add 60.5 scale
  4 4 8 [4 0 0 -4 0 4] {c} false 3 colorimage
  grestore grestore
} def
gsave newpath 10.4 10.4 moveto 140.6 10.4 lineto 140.6 70.4 lineto
10.4 70.4 75.5 30.5 80.5 arcn closepath clip
10.728 69.241 <ff8080ff8080ff8080ff8080ff8080ff8080ff8080ff8080
ff8080ff8080ff8080ff8080ff8080ff8080ff8080ff8080> tile
79.863 61.0 <8080ff8080ff8080ff8080ff8080ff8080ff8080ff8080ff
8080ff8080ff8080ff8080ff8080ff8080ff8080ff8080ff> tile
grestore
gsave 150.2 20.3 30 60 rectclip
150.2 10.3 translate 30 80 scale
4 4 8 [4 0 0 -4 0 4] {<80ff8080ff8080ff8080ff8080ff8080ff8080ff8080ff80
80ff8080ff8080ff8080ff8080ff8080ff8080ff8080ff80>} false 3 colorimage
grestore
showpage
%%EOF
'''


def test_snapped_image_clips_dropped():
    """pdftocairo aligns image bounds to whole points by clips, opening
    gaps between tiled images: those clips are dropped, real clips
    kept."""
    from Sketch.Plugins.Filters.Lib.svgimport import clip
    eps = write('tiles.eps', TILES_EPS)
    doc = compare_eps(eps)
    images = [obj for obj in testsupport.iter_objects(doc) if obj.is_Image]
    assert len(images) == 3
    def clips(image):
        # the masks of the clips around IMAGE, innermost first
        result = []
        obj = image.parent
        while obj is not None and obj.is_MaskGroup:
            result.append(obj.Mask())
            obj = obj.parent
        return result
    for image in images[:2]:
        masks = clips(image)
        # only the curved clip
        assert len(masks) == 1 and clip.rect_of(masks[0]) is None, masks
    # a real crop stays (its edges aligned by poppler as well)
    rect = clip.rect_of(clips(images[2])[0])
    assert rect == pytest.approx((150.2, 20.3, 180.2, 80.3), abs=0.5)
