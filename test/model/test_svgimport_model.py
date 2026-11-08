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


# --------------------------------------------------------------- gradients

def skencil_color(obj, x, y):
    """The color of OBJ's gradient fill at (x, y), by the formulas of
    Graphics/pattern.py."""
    pattern = obj.Properties().fill_pattern
    rect = obj.bounding_rect
    w = rect.right - rect.left
    h = rect.top - rect.bottom
    if pattern.is_AxialGradient:
        dx, dy = pattern.Direction()
        cx = (rect.left + rect.right) / 2
        cy = (rect.bottom + rect.top) / 2
        extent = (w * abs(dx) + h * abs(dy)) * (1 - pattern.Border())
        t = 0.5 - ((x - cx) * dx + (y - cy) * dy) / extent
    else:
        px, py = pattern.Center()
        cx = rect.left + px * w
        cy = rect.bottom + py * h
        radius = max(math.hypot(a - cx, b - cy)
                     for a in (rect.left, rect.right)
                     for b in (rect.bottom, rect.top)) \
                 * (1 - pattern.Border())
        t = 1 - math.hypot(x - cx, y - cy) / radius
    c = pattern.Gradient().ColorAt(min(max(t, 0), 1))
    return (c.red, c.green, c.blue)


STOPS = ('<stop offset="0" stop-color="#ff0000"/>'
         '<stop offset="0.5" stop-color="#ffff00"/>'
         '<stop offset="1" stop-color="#0000ff"/>')

def svg_stops(s):
    """The color of STOPS at the (padded) position S."""
    s = min(max(s, 0), 1)
    if s <= 0.5:
        return (1, s * 2, 0)
    f = (s - 0.5) * 2
    return (1 - f, 1 - f, f)


def test_linear_gradient_is_exact():
    # gradient vector (20, 10) - (80, 40) in user space, rotated and
    # sheared element: the color must agree everywhere in the object
    doc = load('<linearGradient id="g" gradientUnits="userSpaceOnUse" '
               'x1="20" y1="10" x2="80" y2="40" '
               'gradientTransform="rotate(10)">%s</linearGradient>'
               '<rect x="0" y="0" width="100" height="60" fill="url(#g)" '
               'transform="translate(0 20) skewX(15)"/>' % STOPS)
    obj = single(doc)
    from Sketch.Plugins.Filters.Lib.svgimport import values
    g = values.rotate(10)
    inv = values.inverse(g)
    ctm = values.mul((1, 0, 0, -1, 0, 100), values.mul(
        values.translate(0, 20), values.parse_transform('skewX(15)')))
    for ux, uy in ((5, 5), (50, 30), (95, 55), (30, 50), (70, 10)):
        # SVG: position along the gradient vector in gradient space
        qx, qy = values.apply(inv, ux, uy)
        s = ((qx - 20) * 60 + (qy - 10) * 30) / (60 ** 2 + 30 ** 2)
        x, y = values.apply(ctm, ux, uy)
        expected = svg_stops(s)
        assert close(skencil_color(obj, x, y), expected, 0.01), (ux, uy)


def test_radial_gradient_is_exact():
    doc = load('<radialGradient id="g" cx="0.3" cy="0.4" r="0.6">%s'
               '</radialGradient><rect x="10" y="20" width="50" '
               'height="50" fill="url(#g)"/>' % STOPS)
    obj = single(doc)
    cx, cy, r = 10 + 0.3 * 50, 20 + 0.4 * 50, 0.6 * 50
    for ux, uy in ((15, 25), (25, 40), (55, 65), (40, 30)):
        s = math.hypot(ux - cx, uy - cy) / r
        assert close(skencil_color(obj, ux, 100 - uy), svg_stops(s), 0.01)


def test_repeat_gradient_keeps_period_ends():
    doc = load('<linearGradient id="g" x1="0" x2="0.5" '
               'spreadMethod="repeat">%s</linearGradient>'
               '<rect width="100" height="10" fill="url(#g)"/>' % STOPS)
    obj = single(doc)
    # just before the end of the first period: blue; just after: red
    assert close(skencil_color(obj, 49.9, 95), (0, 0, 1), 0.02)
    assert close(skencil_color(obj, 50.1, 95), (1, 0, 0), 0.02)
    # the right end of the object is the end of the second period
    assert close(skencil_color(obj, 100, 95), (0, 0, 1), 0.02)


def test_gradient_stop_opacity_and_fallbacks():
    doc = load('<linearGradient id="g"><stop offset="0" stop-color="red" '
               'stop-opacity="0.5"/><stop offset="1" stop-color="red"/>'
               '</linearGradient>'
               '<linearGradient id="one"><stop stop-color="lime"/>'
               '</linearGradient><linearGradient id="none"/>'
               '<rect width="10" height="10" fill="url(#g)"/>'
               '<rect width="10" height="10" fill="url(#one)"/>'
               '<rect width="10" height="10" fill="url(#none)"/>'
               '<rect width="10" height="10" fill="url(#missing) blue"/>'
               '<rect width="10" height="10" fill="url(#missing)" '
               'stroke="url(#g)"/>')
    first, one, none, fallback, stroke = objects(doc)
    stops = first.Properties().fill_pattern.Gradient().Colors()
    c = stops[0][1]
    assert close((c.red, c.green, c.blue), (1, 0.5, 0.5))
    assert rgb(one.Properties().fill_pattern) == (0, 1, 0)
    assert none.Properties().fill_pattern.is_Empty
    assert rgb(fallback.Properties().fill_pattern) == (0, 0, 1)
    # gradient strokes: the middle color (opacity 0.75, over white)
    assert stroke.Properties().fill_pattern.is_Empty
    assert rgb(stroke.Properties().line_pattern) == (1, 0.25, 0.25)
    assert 'Gradient or pattern strokes' in doc.meta.load_messages


def test_pattern_object_bounding_box_tiles():
    # tiles of 0.25 x 0.5 of the bounding box, content in bbox units
    doc = load('<pattern id="p" width="0.25" height="0.5" '
               'patternContentUnits="objectBoundingBox">'
               '<rect x="0.05" y="0.1" width="0.1" height="0.2" '
               'fill="red"/></pattern>'
               '<rect x="10" y="20" width="80" height="40" '
               'fill="url(#p)"/>')
    # the tiles lie within the rect: no clip needed
    tiles = single(doc)
    assert tiles.is_Group and not tiles.is_MaskGroup
    rects = sorted((round(r.coord_rect.left, 6), round(r.coord_rect.top, 6))
                   for r in tiles.GetObjects())
    # 4 x 2 tiles of 20 x 20, the red rect at (4, 4) in each
    assert rects == sorted((x, 100 - y) for x in (14, 34, 54, 74)
                           for y in (24, 44))


def test_image_pattern_is_tiled():
    from Sketch.Plugins.Filters.Lib import svgimport
    import base64, io
    from PIL import Image
    buf = io.BytesIO()
    Image.new('RGB', (4, 2), (255, 0, 0)).save(buf, 'PNG')
    uri = 'data:image/png;base64,' + base64.b64encode(buf.getvalue()).decode()
    doc = load('<pattern id="p" width="8" height="4" '
               'patternUnits="userSpaceOnUse"><image width="8" height="4" '
               'preserveAspectRatio="none" xlink:href="%s"/></pattern>'
               '<rect width="50" height="50" fill="url(#p)"/>' % uri)
    pattern = single(doc).Properties().fill_pattern
    assert pattern.is_Tiled
    # a tile pixel is 2 x 2
    assert close(pattern.trafo.coeff()[:4], (2, 0, 0, -2))


# -------------------------------------------------------------------- text

import shutil

have_inkscape = shutil.which('inkscape') is not None


def leaves(obj):
    if obj.is_Compound:
        result = []
        for child in obj.GetObjects():
            result.extend(leaves(child))
        return result
    return [obj]


@pytest.mark.skipif(not have_inkscape, reason='inkscape not installed')
def test_text_converted_by_inkscape():
    doc = load('<style>text { fill: green }</style>'
               '<text x="10" y="50" font-size="20">Ab <tspan fill="red">'
               'cd</tspan></text>')
    paths = leaves(single(doc))
    assert all(p.is_Bezier for p in paths)
    # the paint comes from this document's cascade
    colors = [rgb(p.Properties().fill_pattern) for p in paths
              if p.Properties().fill_pattern.is_Solid]
    assert (0, 0.502, 0) in colors and (1, 0, 0) in colors
    r = single(doc).coord_rect
    assert 9 < r.left < 12 and r.bottom > 100 - 52 and r.top < 100 - 30


def test_text_fallback_without_inkscape(monkeypatch):
    monkeypatch.setenv('INKSCAPE', '/nonexistent/inkscape')
    doc = load('<text x="50" y="50" font-size="20" fill="blue" '
               'text-anchor="middle">A☃B<tspan x="10" y="80" '
               'fill="red">C</tspan></text>')
    texts = leaves(single(doc))
    assert [t.__class__.__name__ for t in texts] == ['SimpleText'] * 2
    first, second = texts
    from Sketch.Base import config
    assert first.Font().PostScriptName() == config.preferences.fallback_font
    # the snowman is not in the font
    assert len(first.Text()) == 2
    assert first.FontSize() == 20
    assert rgb(first.Properties().fill_pattern) == (0, 0, 1)
    assert rgb(second.Properties().fill_pattern) == (1, 0, 0)
    # centered on x = 50
    r = first.coord_rect
    assert abs((r.left + r.right) / 2 - 50) < 2
    # the tspan inherits text-anchor: centered on x = 10
    r = second.coord_rect
    assert abs((r.left + r.right) / 2 - 10) < 1 and second.trafo.v2 == 20
    messages = doc.meta.load_messages
    assert 'inkscape not found' in messages and 'missing' in messages


def test_svg_font_text():
    # a two-glyph SVG font with 100 units per em: a square and a bar
    doc = load('<defs><font id="f" horiz-adv-x="100">'
               '<font-face font-family="sq" units-per-em="100"/>'
               '<glyph unicode="a" d="M0 0 h50 v50 h-50z"/>'
               '<glyph unicode="b" horiz-adv-x="200" d="M0 0 h150 v10 h-150z"/>'
               '<glyph unicode="ab" d="M0 0 h10 v10 h-10z"/>'
               '</font></defs>'
               '<text x="10" y="50" font-family="sq" font-size="20">'
               'aba<tspan dx="5">b</tspan></text>')
    group = single(doc)
    # "ab" is a ligature (2 x 2 at 10), then "a" at 10 + 0.2 * 100 = 30
    # (advance of the ligature: the font default), then "b" 5 later
    # one curve per run (the tspan is a run of its own)
    boxes = sorted((round(b[0], 6), round(b[2], 6)) for obj in leaves(group)
                   for b in [subpath_box(p) for p in obj.Paths()])
    assert boxes == [(10, 12), (30, 40), (55, 85)]


def subpath_box(path):
    xs = [path.Node(i).x for i in range(path.len)]
    ys = [path.Node(i).y for i in range(path.len)]
    return (min(xs), min(ys), max(xs), max(ys))


# ----------------------------------------------------------------- markers

def test_marker_vertices():
    from Sketch.Plugins.Filters.Lib.svgimport import marker, pathdata
    subs = pathdata.parse('M0 0 L10 0 L10 10 Z M20 0 L30 0')
    verts = marker.vertices(subs)
    # the closing point is a vertex
    assert [v[0] for v in verts] == ['start', 'mid', 'mid', 'mid', 'mid',
                                     'end']
    # the start of a closed subpath bisects the closing and the first
    # segment
    assert verts[0][3] == pytest.approx(math.radians(-135))
    # at (10, 10): in 90 (down), out -135 (closing segment)
    kind, x, y, a_in, a_out = verts[2]
    assert marker.bisector(a_in, a_out) == pytest.approx(math.radians(157.5))


def test_markers_are_drawn():
    doc = load('<marker id="m" markerWidth="4" markerHeight="4" refX="2" '
               'refY="2" orient="auto"><rect width="4" height="2"/></marker>'
               '<path d="M10 10 L50 10 L50 50" stroke="black" '
               'stroke-width="2" fill="none" marker-start="url(#m)" '
               'marker-mid="url(#m)" marker-end="url(#m)"/>')
    group = single(doc)
    assert group.is_Group
    path, *marks = group.GetObjects()
    assert path.is_Bezier and len(marks) == 3
    # 4 x 2 marker units times the stroke width; the end marker is
    # rotated by 90 degrees (pointing down)
    r = marks[2].coord_rect
    assert close((r.right - r.left, r.top - r.bottom), (4, 8))


def test_native_arrows_round_trip():
    from Sketch.Base import plugins
    doc = testsupport.load_document(testsupport.data_path('tarr.sk'))
    out = testsupport.output_path('svgimport', 'tarr-arrows.svg')
    plugins.find_export_plugin('SVG')(doc, out, options = {'flavour': 0})
    imported = svgimport().import_svg(out)
    def arrows(document):
        result = []
        for obj in objects(document):
            for leaf in leaves(obj):
                if leaf.is_Bezier and leaf.Properties().HasLine():
                    props = leaf.Properties()
                    if props.line_arrow1 or props.line_arrow2:
                        result.append((leaf, props))
        return result
    # paths with several subpaths are exported with explicit arrows
    original = [item for item in arrows(doc) if len(item[0].Paths()) == 1]
    found = arrows(imported)
    assert original and len(found) == len(original)
    for (o, op), (i, ip) in zip(original, found):
        assert (op.line_arrow1 is None) == (ip.line_arrow1 is None)
        assert (op.line_arrow2 is None) == (ip.line_arrow2 is None)
        # the original path ends are restored
        a = o.Paths()[0]; b = i.Paths()[0]
        assert close(a.Node(0), b.Node(0), 1e-3)
        assert close(a.Node(-1), b.Node(-1), 1e-3)


# ------------------------------------------------------------------- masks

def png_uri(image):
    import base64, io
    buf = io.BytesIO()
    image.save(buf, 'PNG')
    return 'data:image/png;base64,' + base64.b64encode(buf.getvalue()).decode()


def test_image_mask_is_flattened():
    from PIL import Image
    picture = Image.new('RGB', (10, 10), (255, 0, 0))
    # the mask: left half white, right half 50% gray
    mask = Image.new('RGB', (10, 10), (128, 128, 128))
    mask.paste((255, 255, 255), (0, 0, 5, 10))
    doc = load('<mask id="m" maskUnits="userSpaceOnUse" x="0" y="0" '
               'width="100" height="100"><image width="40" height="40" '
               'xlink:href="%s"/></mask>'
               '<image width="40" height="40" mask="url(#m)" '
               'xlink:href="%s"/>' % (png_uri(mask), png_uri(picture)))
    image = single(doc)
    assert image.is_Image
    data = image.data.Image()
    assert data.mode == 'RGBA'
    alpha = data.getchannel('A')
    assert alpha.getpixel((1, 5)) == 255
    assert abs(alpha.getpixel((8, 5)) - 128) <= 2
    assert 'flattened' in doc.meta.load_messages


def test_gradient_mask_on_image():
    from PIL import Image
    picture = Image.new('RGB', (20, 4), (0, 0, 255))
    doc = load('<linearGradient id="g"><stop offset="0" stop-color="white"/>'
               '<stop offset="1" stop-color="black"/></linearGradient>'
               '<mask id="m"><rect width="100" height="10" fill="url(#g)"/>'
               '</mask><image width="100" height="20" '
               'preserveAspectRatio="none" mask="url(#m)" '
               'xlink:href="%s"/>' % png_uri(picture))
    alpha = single(doc).data.Image().getchannel('A')
    # the mask region (bbox -10%..120%) covers the image; the fade
    # runs over x = 0..100, the mask rect covers y = 0..10 (rows 0, 1)
    values = [alpha.getpixel((x, 0)) for x in (0, 10, 19)]
    assert values[0] > 230 and 100 < values[1] < 155 and values[2] < 25
    assert alpha.getpixel((10, 3)) == 0


def test_mask_with_opacity_and_unsupported_mask():
    doc = load('<mask id="half"><rect width="100" height="100" '
               'fill="white" opacity="0.5"/></mask>'
               '<rect width="50" height="50" fill="red" mask="url(#half)"/>')
    # a semi-transparent mask on a vector shape cannot be represented
    assert single(doc).is_Rectangle
    assert 'Masks ignored' in doc.meta.load_messages


# ------------------------------------------------- Inkscape and Sketch extras

def test_inkscape_arc():
    from Sketch.Base import const
    doc = load('<path sodipodi:type="arc" sodipodi:cx="50" sodipodi:cy="50" '
               'sodipodi:rx="20" sodipodi:ry="10" sodipodi:start="0" '
               'sodipodi:end="1.5707963" sodipodi:open="true" '
               'sodipodi:arc-type="arc" d="M 70,50 A 20,10 0 0 1 50,60" '
               'fill="none" stroke="black"/>'
               '<path sodipodi:type="arc" sodipodi:cx="50" sodipodi:cy="50" '
               'sodipodi:rx="20" sodipodi:ry="20" sodipodi:start="0" '
               'sodipodi:end="6.2831853" d="M 70,50 A 20,20 0 1 1 30,50 '
               'A 20,20 0 1 1 70,50 Z"/>')
    arc, circle = objects(doc)
    assert arc.is_Ellipse and arc.arc_type == const.ArcArc
    # from (70, 50) clockwise on screen to (50, 60): in the document
    # (y up) from (50, 40) counterclockwise to (70, 50)
    t = arc.trafo
    def point(angle):
        return t(math.cos(angle), math.sin(angle))
    assert close(point(arc.start_angle), (50, 40))
    assert close(point(arc.end_angle), (70, 50))
    assert circle.is_Ellipse and circle.start_angle == circle.end_angle


def test_inkscape_guides():
    doc = load('<sodipodi:namedview><sodipodi:guide position="20,30" '
               'orientation="0,1"/><sodipodi:guide position="40,0" '
               'orientation="1,0"/><sodipodi:guide position="1,1" '
               'orientation="0.7,0.7"/></sodipodi:namedview>')
    guides = sorted((g.horizontal, round(g.point.x, 6), round(g.point.y, 6))
                    for g in doc.GuideLines())
    # y up from the bottom of the page; diagonal guides are dropped
    assert guides == [(0, 40, 0), (1, 0, 30)]


def count_classes(document):
    counts = {}
    def walk(objs):
        for obj in objs:
            name = obj.__class__.__name__
            counts[name] = counts.get(name, 0) + 1
            if obj.is_Compound and not obj.is_Plugin:
                walk(obj.GetObjects())
    for layer in document.layers:
        if not layer.is_SpecialLayer:
            walk(layer.GetObjects())
    return counts


def test_editing_structure_round_trip():
    """Plugin objects (LaTeX objects among them), linked EPS files and
    guides of Sketch's Inkscape SVG come back."""
    from Sketch.Base import plugins
    doc = testsupport.load_document(testsupport.data_path('alphares.sk'))
    out = testsupport.output_path('svgimport', 'alphares-structure.svg')
    plugins.find_export_plugin('SVG')(doc, out, options = {'flavour': 0})
    imported = svgimport().import_svg(out)
    before = count_classes(doc)
    after = count_classes(imported)
    for name in ('LtxObj', 'EpsImage'):
        assert before.get(name) and after.get(name) == before[name], \
            (name, before, after)
    ltx = [o for layer in imported.layers for o in layer.GetObjects()
           if o.__class__.__name__ == 'LtxObj']
    orig = [o for layer in doc.layers for o in layer.GetObjects()
            if o.__class__.__name__ == 'LtxObj']
    assert sorted(o.text for o in ltx) == sorted(o.text for o in orig)
    for a, b in zip(sorted(orig, key = lambda o: o.text),
                    sorted(ltx, key = lambda o: o.text)):
        assert close(a.trafo.coeff(), b.trafo.coeff(), 1e-3)
    assert len(imported.GuideLines()) == len(doc.GuideLines())


def test_textext_group_without_skencil_attributes():
    doc = load('<g xmlns:textext="http://www.iki.fi/pav/software/textext/" '
               'textext:text="$x^2$" textext:scale="1.2" '
               'transform="matrix(1 0 0 1 10 20)">'
               '<path d="M0 0 h5 v5 z"/><path d="M6 0 h5 v5 z"/></g>')
    obj = single(doc)
    assert obj.__class__.__name__ == 'LtxObj'
    assert obj.text == '$x^2$' and obj.size == pytest.approx(12)
    assert len(obj.GetObjects()) == 2
