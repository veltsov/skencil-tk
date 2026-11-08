# Layer 1: SVG import (Plugins/Filters/Lib/svgimport, see
# devdocs/svg-import.md) -- the value parsers and the structure of
# imported documents.  The visual comparisons are in
# test/formats/test_svgimport.py.

import math

import pytest

import testsupport


def setup_module(module):
    testsupport.sketch()


def svgimport():
    from Sketch.Plugins.Filters.Lib import svgimport
    return svgimport


def svg(body, width = 100, height = 100, extra = ''):
    return ('<svg xmlns="http://www.w3.org/2000/svg" '
            'xmlns:xlink="http://www.w3.org/1999/xlink" '
            'xmlns:inkscape="http://www.inkscape.org/namespaces/inkscape" '
            'xmlns:sodipodi="http://sodipodi.sourceforge.net/DTD/'
            'sodipodi-0.dtd" '
            'width="%spt" height="%spt" viewBox="0 0 %s %s" %s>%s</svg>'
            % (width, height, width, height, extra, body)).encode()


def load(body, **kw):
    return svgimport().import_svg(svg(body, **kw))


def objects(doc):
    result = []
    for layer in doc.layers:
        if not layer.is_SpecialLayer:
            result.extend(layer.GetObjects())
    return result


def single(doc):
    objs = objects(doc)
    assert len(objs) == 1, objs
    return objs[0]


def rgb(pattern):
    c = pattern.Color()
    return (round(c.red, 3), round(c.green, 3), round(c.blue, 3))


def close(a, b, eps = 1e-6):
    return all(abs(x - y) < eps for x, y in zip(a, b))


# ----------------------------------------------------------------- values

def test_numbers_and_transforms():
    from Sketch.Plugins.Filters.Lib.svgimport import values
    assert values.numbers('M.5.5-1e2,3+4') == [0.5, 0.5, -100.0, 3.0, 4.0]
    m = values.parse_transform('translate(10) scale(2, 3)')
    assert close(m, (2, 0, 0, 3, 10, 0))
    m = values.parse_transform('rotate(90 10 0)')
    assert close(values.apply(m, 10, 10), (0, 0))
    assert values.parse_transform('bogus(1)') is None
    assert close(values.parse_transform('skewX(45)'), (1, 0, 1, 1, 0, 0))


def test_lengths_and_colors():
    from Sketch.Plugins.Filters.Lib.svgimport import values
    assert values.length('1in') == 96
    assert values.length('72pt') == 96
    assert values.length('50%', 200) == 100
    assert values.length('2em', 0, 10) == 20
    assert values.length('x', default = 7) == 7
    assert values.color('#f00') == (1, 0, 0, 1)
    assert values.color('#ff000080')[3] == pytest.approx(128 / 255.)
    assert values.color('rgb(100%, 0, 255)') == (1, 0, 1, 1)
    assert values.color('rgba(0,0,0,.5)')[3] == 0.5
    assert close(values.color('hsl(120, 100%, 50%)'), (0, 1, 0, 1))
    assert values.color('Navy') == (0, 0, 128 / 255., 1)
    assert values.color('nonsense') is None
    assert values.paint('none') is None
    assert values.paint('url(#g) red') == ('url', 'g', (1, 0, 0, 1))
    assert values.paint('currentColor') == 'currentColor'


def test_css():
    from Sketch.Plugins.Filters.Lib.svgimport import tree
    root = tree.parse(svg(
        '<style>/* c */ rect { fill: red } .a { fill: green } '
        '#r { fill: blue !important } g > .b { stroke: black } '
        'a:hover { fill: pink } @media print { rect { fill: gray } }'
        '</style><g><rect id="r" class="a b" fill="yellow" '
        'style="fill: white"/></g>'))
    cascade = tree.Cascade(root)
    rect = root.children[1].children[0]
    style = cascade.compute(rect, cascade.compute(root.children[1],
                                                  tree.ROOT_STYLE))
    # !important in the sheet beats the style attribute
    assert style['fill'] == 'blue'
    assert style['stroke'] == 'black'


def test_path_data():
    from Sketch.Plugins.Filters.Lib.svgimport import pathdata
    subs = pathdata.parse('M10 10h5v5z m1 1 l2 2')
    assert [s.closed for s in subs] == [True, False]
    # after z the current point is the start of the closed subpath
    assert subs[1].start == (11, 11)
    # compact arc flags
    subs = pathdata.parse('M0,0a10 10 0 1010 10')
    assert close(subs[0].end(), (10, 10))
    assert all(seg[0] == 'C' for seg in subs[0].segments)
    # the arc is a 3/4 circle around (0, 10)
    for seg in subs[0].segments:
        x, y = seg[-2:]
        assert math.hypot(x, y - 10) == pytest.approx(10)
    # smooth curves reflect the previous control point
    subs = pathdata.parse('M0 0C0 10 10 10 10 0S20 -10 20 0')
    assert close(subs[0].segments[1][1:3], (10, -10))
    # quadratics become cubics
    subs = pathdata.parse('M0 0Q5 5 10 0T20 0')
    assert close(subs[0].segments[1][1:3], (40 / 3., -10 / 3.))
    # an error ends the path data
    subs = pathdata.parse('M0 0 L10 10 L x 20 30')
    assert len(subs[0].segments) == 1


def test_dash_offset():
    from Sketch.Plugins.Filters.Lib.svgimport.paint import shift_dashes
    assert shift_dashes([4, 2, 3, 1], 0) == [4, 2, 3, 1]
    # inside a dash: the dash is split
    assert shift_dashes([4, 2, 3, 1], 1) == [3, 2, 3, 1, 1, 0]
    # at the start of a gap
    assert shift_dashes([4, 2, 3, 1], 4) == [0, 2, 3, 1, 4, 0]
    # inside a gap: exact with a zero dash, else at the next dash
    assert shift_dashes([4, 2, 3, 1], 5) == [0, 1, 3, 1, 4, 1]
    assert shift_dashes([4, 2, 3, 1], 5, False) == [3, 1, 4, 2]
    assert shift_dashes([4, 2, 3, 1], 13) == [1, 2, 3, 1, 3, 0]


# --------------------------------------------------------------- fill rule

def squares(*specs):
    from Sketch.Plugins.Filters.Lib.svgimport import pathdata
    subs = []
    for x, y, size, clockwise in specs:
        d = ('M%g %g h%g v%g h%gz' if clockwise else 'M%g %g v%g h%g v%gz') \
            % (x, y, size, size, -size)
        subs.extend(pathdata.parse(d))
    return subs


def fill_subset(subs, rule = 'nonzero'):
    from Sketch.Plugins.Filters.Lib.svgimport import fillrule
    warnings = []
    kept = fillrule.even_odd_equivalent(subs, rule, warnings.append)
    return [subs.index(s) for s in kept], warnings


def test_fill_rule_nested_same_orientation():
    # the inner square is filled under nonzero: its boundary is dropped
    subs = squares((0, 0, 10, 1), (2, 2, 6, 1))
    assert fill_subset(subs) == ([0], [])


def test_fill_rule_nested_opposite_orientation():
    # a hole under both rules
    subs = squares((0, 0, 10, 1), (2, 2, 6, 0))
    assert fill_subset(subs) == ([0, 1], [])


def test_fill_rule_three_levels():
    # outer and middle same orientation (middle invisible), inner
    # opposite: winding 1, 2, 1 -- all filled
    subs = squares((0, 0, 10, 1), (2, 2, 6, 1), (4, 4, 2, 0))
    assert fill_subset(subs) == ([0], [])
    # winding 1, 0, 1 (an "O" with a dot): all boundaries visible
    subs = squares((0, 0, 10, 1), (2, 2, 6, 0), (4, 4, 2, 1))
    assert fill_subset(subs) == ([0, 1, 2], [])


def test_fill_rule_disjoint_and_evenodd():
    subs = squares((0, 0, 4, 1), (10, 0, 4, 1))
    assert fill_subset(subs) == ([0, 1], [])
    subs = squares((0, 0, 10, 1), (2, 2, 6, 1))
    assert fill_subset(subs, 'evenodd') == ([0, 1], [])


def test_fill_rule_crossing_is_reported():
    subs = squares((0, 0, 10, 1), (5, 5, 10, 1))
    kept, warnings = fill_subset(subs)
    assert warnings


def test_self_intersecting_star():
    from Sketch.Plugins.Filters.Lib.svgimport import pathdata, fillrule
    star = pathdata.parse('M50 0 L79 90 L2 35 L98 35 L21 90 Z')[0]
    assert fillrule.self_intersecting(star)
    assert not fillrule.self_intersecting(squares((0, 0, 4, 1))[0])


# --------------------------------------------------------------- documents

def test_page_and_coordinates():
    doc = svgimport().import_svg(
        b'<svg xmlns="http://www.w3.org/2000/svg" width="210mm" '
        b'height="297mm" viewBox="0 0 210 297">'
        b'<rect x="10" y="20" width="30" height="40"/></svg>')
    # A4 is recognized
    assert doc.page_layout.FormatName() == 'A4'
    r = single(doc).coord_rect
    mm = 72 / 25.4
    # y is flipped: the top of the page is y = 297 mm
    assert close((r.left, r.bottom, r.right, r.top),
                 (10 * mm, (297 - 60) * mm, 40 * mm, (297 - 20) * mm), 1e-4)


def test_page_from_content_without_size():
    doc = svgimport().import_svg(
        b'<svg xmlns="http://www.w3.org/2000/svg">'
        b'<rect x="10" y="20" width="30" height="40"/></svg>')
    w, h = doc.PageSize()
    assert close((w, h), (30 * 0.75, 40 * 0.75))


def test_shapes():
    doc = load('<rect x="10" y="10" width="40" height="20" rx="5"/>'
               '<circle cx="50" cy="50" r="10"/>'
               '<ellipse cx="50" cy="50" rx="10" ry="5"/>'
               '<line x1="0" y1="0" x2="10" y2="10" stroke="black"/>'
               '<polygon points="0,0 10,0 5,5"/>'
               '<polyline points="0,0 10,0 5,5" fill="none" stroke="red"/>')
    objs = objects(doc)
    kinds = [o.__class__.__name__ for o in objs]
    assert kinds == ['Rectangle', 'Ellipse', 'Ellipse', 'PolyBezier',
                     'PolyBezier', 'PolyBezier']
    rect = objs[0]
    assert rect.radius1 == pytest.approx(5 / 40.)
    assert rect.radius2 == pytest.approx(5 / 20.)
    # positive orientation for rectangles and ellipses
    assert rect.trafo.m11 * rect.trafo.m22 - rect.trafo.m12 * rect.trafo.m21 > 0
    # a line is never filled; a polygon is closed
    assert objs[3].Properties().fill_pattern.is_Empty
    assert objs[4].Paths()[0].closed
    assert not objs[5].Paths()[0].closed


def test_paint_and_opacity():
    doc = load('<rect width="10" height="10" fill="#ff0000" '
               'fill-opacity="0.5" stroke="blue" stroke-width="2"/>'
               '<g opacity="0.5"><rect width="10" height="10" fill="black" '
               'opacity="0.5"/></g>'
               '<rect width="10" height="10" fill="red" fill-opacity="0"/>'
               '<rect width="10" height="10" fill="none"/>')
    objs = objects(doc)
    props = objs[0].Properties()
    assert rgb(props.fill_pattern) == (1, 0.5, 0.5)
    assert rgb(props.line_pattern) == (0, 0, 1)
    assert props.line_width == 2
    # opacities multiply along the ancestors
    assert rgb(objs[1].Properties().fill_pattern) == (0.75, 0.75, 0.75)
    # invisible paint: the object is kept (outline mode, construction)
    assert len(objs) == 4
    assert objs[2].Properties().fill_pattern.is_Empty
    assert objs[3].Properties().fill_pattern.is_Empty
    assert 'blended' in doc.meta.load_messages


def test_line_properties():
    from Sketch.Base import const
    doc = load('<path d="M0 0 L10 10" stroke="black" stroke-width="4" '
               'stroke-linecap="round" stroke-linejoin="bevel" '
               'stroke-dasharray="4 2 2" transform="scale(2)"/>'
               '<path d="M0 0 L10 10 L20 0" stroke="black" '
               'stroke-miterlimit="1.2"/>'
               '<path d="M0 0 L10 10" stroke="black" stroke-width="0"/>')
    objs = objects(doc)
    props = objs[0].Properties()
    assert props.line_width == 8
    assert props.line_cap == const.CapRound
    assert props.line_join == const.JoinBevel
    # odd dash arrays are repeated; units of the line width
    assert close(props.line_dashes, (1, 0.5, 0.5, 1, 0.5, 0.5))
    assert objs[1].Properties().line_join == const.JoinBevel
    assert objs[2].Properties().line_pattern.is_Empty


def test_use_symbol_and_nested_svg():
    doc = load('<defs><path id="p" d="M0 0 h10 v10 z"/>'
               '<symbol id="s" viewBox="0 0 10 10"><rect width="10" '
               'height="10"/></symbol></defs>'
               '<use xlink:href="#p" x="20" y="30"/>'
               '<use href="#s" x="50" y="50" width="20" height="20"/>'
               '<svg x="0" y="80" width="10" height="10" viewBox="0 0 1 1">'
               '<rect width="1" height="1"/></svg>'
               '<use xlink:href="#missing"/>')
    objs = objects(doc)
    assert len(objs) == 3
    r = objs[0].coord_rect
    assert close((r.left, r.top), (20, 100 - 30))
    r = objs[1].coord_rect
    assert close((r.left, r.bottom, r.right, r.top), (50, 30, 70, 50))
    r = objs[2].coord_rect
    assert close((r.left, r.bottom, r.right, r.top), (0, 10, 10, 20))
    assert 'unknown element' in doc.meta.load_messages


def test_recursive_use():
    doc = load('<g id="g"><use xlink:href="#g"/><rect width="1" '
               'height="1"/></g>')
    assert 'Recursive' in doc.meta.load_messages


def test_display_and_visibility():
    doc = load('<rect width="1" height="1" display="none"/>'
               '<g visibility="hidden"><rect width="1" height="1"/>'
               '<rect width="2" height="2" visibility="visible"/></g>'
               '<g style="display:none"><rect width="3" height="3"/></g>')
    objs = objects(doc)
    assert len(objs) == 1
    assert objs[0].coord_rect.right == 2


def test_nonzero_fill_with_stroke_is_split():
    doc = load('<path d="M0 0 h30 v30 h-30z M5 5 h20 v20 h-20z" '
               'fill="orange" stroke="black"/>')
    group = single(doc)
    assert group.is_Group
    fill, line = group.GetObjects()
    assert len(fill.Paths()) == 1 and fill.Properties().line_pattern.is_Empty
    assert len(line.Paths()) == 2 and line.Properties().fill_pattern.is_Empty


def test_paint_order_stroke_first():
    doc = load('<rect width="10" height="10" fill="red" stroke="blue" '
               'style="paint-order: stroke"/>')
    below, above = single(doc).GetObjects()
    assert below.Properties().fill_pattern.is_Empty
    assert above.Properties().line_pattern.is_Empty


def test_round_cap_dots():
    doc = load('<path d="M10 10 z M20 20 l0 0" stroke="black" '
               'stroke-width="4" stroke-linecap="round"/>')
    objs = objects(doc)
    assert [o.__class__.__name__ for o in objs] == ['Ellipse', 'Ellipse']


def test_clip_path():
    doc = load('<clipPath id="c"><circle cx="50" cy="50" r="20"/>'
               '</clipPath>'
               '<clipPath id="big"><rect width="100" height="100"/>'
               '</clipPath>'
               '<clipPath id="two"><rect width="10" height="10"/>'
               '<rect x="20" width="10" height="10"/></clipPath>'
               '<rect width="100" height="100" fill="red" '
               'clip-path="url(#c)"/>'
               '<rect x="10" y="10" width="10" height="10" '
               'clip-path="url(#big)"/>'
               '<rect width="100" height="100" clip-path="url(#two)"/>'
               '<rect x="500" width="10" height="10" '
               'clip-path="url(#big)"/>')
    objs = objects(doc)
    # the clip that cuts nothing off is dropped, the one that cuts
    # everything off removes the object
    assert [o.__class__.__name__ for o in objs] == ['MaskGroup', 'Rectangle',
                                                    'MaskGroup']
    mask = objs[0].Mask()
    assert mask.is_Ellipse
    assert mask.Properties().fill_pattern.is_Empty
    assert mask.Properties().line_pattern.is_Empty
    # several clip children: one curve with their union
    assert len(objs[2].Mask().Paths()) == 2


def test_clip_path_object_bounding_box():
    doc = load('<clipPath id="c" clipPathUnits="objectBoundingBox">'
               '<rect width="0.5" height="1"/></clipPath>'
               '<rect x="10" y="10" width="40" height="20" '
               'clip-path="url(#c)"/>')
    r = single(doc).Mask().coord_rect
    assert close((r.left, r.right, r.bottom, r.top), (10, 30, 70, 90))


def test_inkscape_layers():
    doc = load('<rect width="1" height="1"/>'
               '<g inkscape:groupmode="layer" inkscape:label="Top" '
               'style="display:none" sodipodi:insensitive="true">'
               '<rect width="2" height="2"/><rect width="3" height="3"/></g>')
    layers = [l for l in doc.layers if not l.is_SpecialLayer]
    assert [l.name for l in layers] == ['Layer 1', 'Top']
    top = layers[1]
    assert not top.visible and top.locked
    assert len(top.GetObjects()) == 2


def test_data_uri_image():
    import base64, io
    from PIL import Image
    buf = io.BytesIO()
    Image.new('RGBA', (4, 2), (255, 0, 0, 128)).save(buf, 'PNG')
    uri = 'data:image/png;base64,' + base64.b64encode(buf.getvalue()).decode()
    doc = load('<image x="10" y="10" width="40" height="20" '
               'preserveAspectRatio="none" xlink:href="%s"/>'
               '<image x="10" y="50" width="40" height="40" '
               'opacity="0.5" xlink:href="%s"/>' % (uri, uri))
    first, second = objects(doc)
    assert first.data.mode == 'RGBA'
    r = first.coord_rect
    assert close((r.left, r.bottom, r.right, r.top), (10, 70, 50, 90))
    # meet: centred in the box
    r = second.coord_rect
    assert close((r.left, r.bottom, r.right, r.top), (10, 20, 50, 40))


def test_load_messages_and_errors():
    from Sketch import SketchLoadError
    with pytest.raises(SketchLoadError):
        svgimport().import_svg(b'<svg xmlns="http://www.w3.org/2000/svg">')
    with pytest.raises(SketchLoadError):
        svgimport().import_svg(b'<html/>')


def test_loader_plugin_detection():
    import io
    from Sketch.Base import load
    for head in (b'<?xml version="1.0"?>\n', b'<!-- comment -->\n',
                 b'\xef\xbb\xbf', b'<!DOCTYPE svg PUBLIC "x" "y">\n'):
        data = head + svg('<rect width="1" height="1"/>')
        doc = load.load_drawing_from_file(io.BytesIO(data), 'x.svg')
        assert len(objects(doc)) == 1, head


def test_import_svg_group():
    group, messages = svgimport().import_svg_group(svg(
        '<rect width="1" height="1"/><circle r="1"/>'))
    assert group.is_Group and len(group.GetObjects()) == 2
