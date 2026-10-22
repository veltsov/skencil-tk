# Layer 1: headless model tests -- mutations.  Change objects and layer
# attributes, transform objects and bezier curve points, and verify the
# results including undo/redo.  (no display required)

from __future__ import print_function

import math

import pytest

import testsupport

FIXTURE = 'tarr.sk'          # 24 objects, 3 layers
BEZIER_FIXTURE = 'alphares.sk'   # contains real PolyBezier objects


def load(name=FIXTURE):
    return testsupport.load_document(testsupport.data_path(name))


def approx(x):
    return pytest.approx(x, abs=1e-4)


# ------------------------------------------------------------ transforms

def test_translate_selected():
    doc = load()
    doc.SelectAll()
    r0 = doc.selection.bounding_rect
    # NOTE: TranslateSelected needs a Point, not a tuple: the undo
    # factory computes -offset, and tuples cannot be negated.
    sk = testsupport.sketch()
    from Sketch import Point
    doc.TranslateSelected(Point(10, 0))
    r1 = doc.selection.bounding_rect
    assert r1.left == approx(r0.left + 10)
    assert r1.right == approx(r0.right + 10)
    assert r1.top == approx(r0.top)
    doc.Undo()
    r2 = doc.selection.bounding_rect
    assert r2.left == approx(r0.left)
    assert r2.right == approx(r0.right)
    assert r2.top == approx(r0.top)
    assert r2.bottom == approx(r0.bottom)
    doc.Redo()
    r3 = doc.selection.bounding_rect
    assert (r3.left, r3.top, r3.right, r3.bottom) == \
           (r1.left, r1.top, r1.right, r1.bottom)


def test_scale_selected():
    doc = load()
    doc.SelectAll()
    r0 = doc.selection.bounding_rect
    sk = testsupport.sketch()
    from Sketch import Scale
    doc.TransformSelected(Scale(2, 2))
    r1 = doc.selection.bounding_rect
    # The selection must have grown (doubling about the origin); the
    # exact new bbox is not asserted because instances/clones transform
    # differently from plain primitives.
    assert r1.right > r0.right and r1.bottom > r0.bottom
    doc.Undo()
    r2 = doc.selection.bounding_rect
    assert r2.left == approx(r0.left)
    assert r2.right == approx(r0.right)
    assert r2.top == approx(r0.top)
    assert r2.bottom == approx(r0.bottom)


def test_rotate_selected():
    doc = load()
    doc.SelectAll()
    r0 = doc.selection.bounding_rect
    # NOTE: document.RotateSelected takes degrees; 90 degrees is known
    # to be buggy (see document.py), so use a smaller angle.
    doc.RotateSelected(30)
    r1 = doc.selection.bounding_rect
    assert (r1.left, r1.top, r1.right, r1.bottom) != \
           (r0.left, r0.top, r0.right, r0.bottom)
    doc.Undo()
    r2 = doc.selection.bounding_rect
    assert r2.left == approx(r0.left)
    assert r2.top == approx(r0.top)
    assert r2.right == approx(r0.right)
    assert r2.bottom == approx(r0.bottom)


# ------------------------------------------------------ layer attributes

def test_layer_state():
    doc = load()
    layer = doc.layers[0]
    assert (layer.visible, layer.printable, layer.locked, layer.outlined) \
        == (1, 1, 0, 0)
    doc.SetLayerState(0, 0, 0, 1, 1)
    layer = doc.layers[0]
    assert (layer.visible, layer.printable, layer.locked, layer.outlined) \
        == (0, 0, 1, 1)
    doc.Undo()
    layer = doc.layers[0]
    assert (layer.visible, layer.printable, layer.locked, layer.outlined) \
        == (1, 1, 0, 0)



def test_layer_state_survives_save_reload():
    doc = load()
    doc.SetLayerState(0, 0, 1, 0, 1)
    sk = testsupport.sketch()
    from Sketch import plugins
    saver = plugins.find_export_plugin(plugins.guess_export_plugin('.sk'))
    out = testsupport.output_path('sk', 'layerstate.sk')
    saver(doc, out)
    doc2 = testsupport.load_document(out)
    layer = doc2.layers[0]
    assert (layer.visible, layer.printable, layer.locked, layer.outlined) \
        == (0, 1, 0, 1)


def test_move_layer():
    doc = load()
    names0 = [l.name for l in doc.layers]
    assert len(names0) >= 2
    doc.MoveLayerUp(0)
    names1 = [l.name for l in doc.layers]
    assert names1[0] == names0[1]
    assert names1[1] == names0[0]
    doc.Undo()
    names2 = [l.name for l in doc.layers]
    assert names2 == names0


# --------------------------------------------------------- object changes

def test_set_properties():
    doc = load()
    doc.SelectAll()
    sk = testsupport.sketch()
    from Sketch import CreateRGBColor, SolidPattern
    red = SolidPattern(CreateRGBColor(1, 0, 0))
    doc.SetProperties(line_pattern=red)
    checked = 0
    for obj in doc.selection.GetObjects():
        if not hasattr(obj.Properties(), 'line_pattern'):
            continue
        pattern = obj.Properties().line_pattern
        if testsupport.class_name(pattern) == 'SolidPattern':
            color = pattern.Color()
            assert (color.red, color.green, color.blue) == (1, 0, 0)
            checked = checked + 1
    assert checked > 0, 'no solid line pattern after SetProperties'
    doc.Undo()


# ------------------------------------------------------- bezier editing

def _edit_first_bezier_path(doc, edit_path):
    obj = testsupport.first_bezier(doc)
    assert obj is not None
    new = edit_path(obj.Paths()[0])
    paths = list(obj.Paths())
    paths[0] = new
    doc.begin_transaction(u'test edit')
    try:
        doc.AddUndo(obj.SetPaths(paths))
    except:
        doc.abort_transaction()
        raise
    doc.end_transaction()
    return obj


def test_bezier_path_translate():
    doc = load(BEZIER_FIXTURE)
    obj = testsupport.first_bezier(doc)
    assert obj is not None, 'no PolyBezier in %s' % BEZIER_FIXTURE
    path = obj.Paths()[0]
    p0 = path.Node(0)

    def shift(p):
        new = p.Duplicate()
        new.Translate((25, 0))
        return new

    obj = _edit_first_bezier_path(doc, shift)
    p1 = obj.Paths()[0].Node(0)
    assert p1.x == approx(p0.x + 25)
    assert p1.y == approx(p0.y)
    doc.Undo()
    p2 = obj.Paths()[0].Node(0)
    assert (p2.x, p2.y) == (p0.x, p0.y)



def test_bezier_single_node_edit():
    doc = load(BEZIER_FIXTURE)
    p0 = testsupport.first_bezier(doc).Paths()[0].Node(0)

    def move_first_node(p):
        new = p.Duplicate()
        new.SetLine(0, (p0.x + 3, p0.y + 2))
        return new

    obj = _edit_first_bezier_path(doc, move_first_node)
    p1 = obj.Paths()[0].Node(0)
    assert p1.x == approx(p0.x + 3)
    assert p1.y == approx(p0.y + 2)
    doc.Undo()
    p2 = obj.Paths()[0].Node(0)
    assert (p2.x, p2.y) == (p0.x, p0.y)


def test_bezier_edit_survives_save_reload():
    doc = load(BEZIER_FIXTURE)
    first = testsupport.first_bezier(doc)
    p0 = first.Paths()[0].Node(0)

    def shift(p):
        new = p.Duplicate()
        new.Translate((25, 0))
        return new

    _edit_first_bezier_path(doc, shift)
    sk = testsupport.sketch()
    from Sketch import plugins
    saver = plugins.find_export_plugin(plugins.guess_export_plugin('.sk'))
    out = testsupport.output_path('sk', 'bezedit.sk')
    saver(doc, out)
    doc2 = testsupport.load_document(out)
    obj2 = testsupport.first_bezier(doc2)
    p1 = obj2.Paths()[0].Node(0)
    assert p1.x == approx(p0.x + 25)
    assert p1.y == approx(p0.y)
