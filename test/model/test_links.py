# Layer 1: headless model tests -- linked external files (EPS, raster
# images): loading documents with missing links, relinking, embedding,
# updating and export of missing links.  (no display required)


import os
import shutil

import PIL.Image
import pytest

import testsupport


EPS = """%!PS-Adobe-3.0 EPSF-3.0
%%BoundingBox: 10 20 110 70
%%EndComments
0 0 1 setrgbcolor
10 20 100 50 rectfill
showpage
%%EOF
"""

EPS_TRAFO = (2, 0, 0, 2, 100, 200)
PNG_TRAFO = (1, 0, 0, 1, 300, 300)


def approx(x):
    return pytest.approx(x, abs=1e-4)


def save_document(doc, path):
    testsupport.sketch()
    from Sketch.Base import plugins
    saver = plugins.find_export_plugin(plugins.guess_export_plugin('.sk'))
    saver(doc, path)


def write_eps(path):
    with open(path, 'w') as f:
        f.write(EPS)


def write_png(path, color=(255, 0, 0)):
    PIL.Image.new('RGB', (8, 6), color).save(path)


def make_document(dir):
    """Save a document linking a.eps and b.png in DIR; return the
    paths (sk, eps, png)."""
    testsupport.sketch()
    from Sketch import EditDocument, Trafo
    from Sketch.Graphics import eps, image
    eps_file = os.path.join(str(dir), 'a.eps')
    png_file = os.path.join(str(dir), 'b.png')
    write_eps(eps_file)
    write_png(png_file)
    doc = EditDocument(create_layer=1)
    doc.Insert(eps.EpsImage(filename=eps_file, trafo=Trafo(*EPS_TRAFO)))
    doc.Insert(image.Image(imagefile=png_file, trafo=Trafo(*PNG_TRAFO)))
    sk_file = os.path.join(str(dir), 'links.sk')
    save_document(doc, sk_file)
    return sk_file, eps_file, png_file


def clear_cache():
    # the external data cache is global: start every test afresh
    testsupport.sketch()
    from Sketch.Graphics import external
    external.instance_cache.clear()


@pytest.fixture
def linked(tmp_path):
    clear_cache()
    yield make_document(tmp_path)
    clear_cache()


@pytest.fixture
def missing(linked):
    """The linked document with both linked files moved away."""
    sk_file, eps_file, png_file = linked
    shutil.move(eps_file, eps_file + '.away')
    shutil.move(png_file, png_file + '.away')
    clear_cache()
    return linked


def linked_objects(doc):
    eps_obj = [o for o in doc.LinkedObjects() if o.is_Eps][0]
    png_obj = [o for o in doc.LinkedObjects() if o.is_Image][0]
    return eps_obj, png_obj


# ------------------------------------------------------------ listing

def test_link_groups(linked):
    sk_file, eps_file, png_file = linked
    doc = testsupport.load_document(sk_file)
    groups = doc.LinkGroups()
    assert [(name, is_eps, len(objs)) for name, is_eps, objs in groups] \
           == [(eps_file, True, 1), (png_file, False, 1)]
    assert not doc.meta.load_messages


# ------------------------------------------------------- missing links

def test_missing_links_load_with_warning(missing):
    sk_file, eps_file, png_file = missing
    doc = testsupport.load_document(sk_file)
    messages = doc.meta.load_messages
    assert 'a.eps' in messages and 'b.png' in messages
    eps_obj, png_obj = linked_objects(doc)
    assert eps_obj.IsMissing() and png_obj.IsMissing()
    assert eps_obj.IsLinked() and png_obj.IsLinked()
    assert not doc.CanEmbedObject(eps_obj)
    assert not doc.CanEmbedObject(png_obj)
    # placeholders of the default size, drawn through the trafo
    from Sketch.Graphics.external import MISSING_SIZE
    r = eps_obj.coord_rect
    assert (r.left, r.bottom) == (100, 200)
    assert r.right == approx(100 + 2 * MISSING_SIZE[0])


def test_missing_links_save_unchanged(missing, tmp_path):
    sk_file, eps_file, png_file = missing
    doc = testsupport.load_document(sk_file)
    out = os.path.join(str(tmp_path), 'out.sk')
    save_document(doc, out)
    with open(out) as f:
        text = f.read()
    assert "eps((2,0,0,2,100,200),'a.eps')" in text
    assert ",'b.png')" in text


def test_missing_links_skipped_in_ps_export(missing, tmp_path):
    sk_file, eps_file, png_file = missing
    out = os.path.join(str(tmp_path), 'out.ps')
    testsupport.sk2ps(sk_file, out)
    with open(out, 'rb') as f:
        ps = f.read()
    assert b'%%BeginDocument' not in ps
    assert b'skeps' not in ps.split(b'%%EndProlog')[-1]


def test_missing_links_skipped_in_svg_export(missing, tmp_path):
    sk_file, eps_file, png_file = missing
    doc = testsupport.load_document(sk_file)
    from Sketch.Base import plugins
    out = os.path.join(str(tmp_path), 'out.svg')
    saver = plugins.find_export_plugin(plugins.guess_export_plugin('.svg'))
    saver(doc, out)
    with open(out) as f:
        svg = f.read()
    assert '<image' not in svg


def test_relink_missing(missing):
    sk_file, eps_file, png_file = missing
    doc = testsupport.load_document(sk_file)
    eps_obj, png_obj = linked_objects(doc)
    write_eps(eps_file + '.new')
    doc.RelinkObjects([eps_obj], eps_file + '.new')
    assert not eps_obj.IsMissing()
    assert eps_obj.Data().Filename() == eps_file + '.new'
    assert eps_obj.coord_rect.right == approx(100 + 2 * 100)
    assert eps_obj.coord_rect.top == approx(200 + 2 * 50)
    doc.Undo()
    assert eps_obj.IsMissing()
    doc.Redo()
    assert not eps_obj.IsMissing()


def redrawn_rects(doc, action):
    # the rectangles the canvas is asked to redraw by ACTION
    from Sketch.Base.const import REDRAW
    rects = []
    def redraw(all, rects_ = ()):
        rects.extend(rects_)
    doc.Subscribe(REDRAW, redraw)
    try:
        action()
    finally:
        doc.Unsubscribe(REDRAW, redraw)
    return rects


def covers(rects, rect):
    return any(r.contains_rect(rect) for r in rects)


def test_relink_redraws_unselected(missing):
    # the objects relinked from the Links panel are usually not
    # selected: the canvas must be redrawn nevertheless
    sk_file, eps_file, png_file = missing
    doc = testsupport.load_document(sk_file)
    eps_obj, png_obj = linked_objects(doc)
    doc.SelectNone()
    old = png_obj.bounding_rect
    new_file = os.path.join(os.path.dirname(png_file), 'c.png')
    write_png(new_file)
    rects = redrawn_rects(doc, lambda: doc.RelinkObjects(
        [png_obj], new_file))
    assert covers(rects, old) and covers(rects, png_obj.bounding_rect)
    new = png_obj.bounding_rect
    rects = redrawn_rects(doc, doc.Undo)
    assert covers(rects, old) and covers(rects, new)


def test_embed_redraws_unselected(linked):
    sk_file, eps_file, png_file = linked
    doc = testsupport.load_document(sk_file)
    eps_obj, png_obj = linked_objects(doc)
    doc.SelectNone()
    rects = redrawn_rects(doc, lambda: doc.EmbedObjects([png_obj]))
    assert covers(rects, png_obj.bounding_rect)


def test_relink_error(missing):
    sk_file, eps_file, png_file = missing
    doc = testsupport.load_document(sk_file)
    eps_obj, png_obj = linked_objects(doc)
    from Sketch import SketchError
    with pytest.raises(SketchError):
        doc.RelinkObjects([png_obj], png_file + '.nonexistent')
    assert png_obj.IsMissing()
    assert not doc.CanUndo()


def test_reload_when_file_appears(missing):
    sk_file, eps_file, png_file = missing
    doc = testsupport.load_document(sk_file)
    eps_obj, png_obj = linked_objects(doc)
    from Sketch.Graphics import external
    external.reload_all_images(really_all=0)
    assert png_obj.IsMissing()
    shutil.move(png_file + '.away', png_file)
    external.reload_all_images(really_all=0)
    assert not png_obj.IsMissing()
    assert png_obj.Data().Size() == (8, 6)
    assert eps_obj.IsMissing()


# ----------------------------------------------------------- embedding

def test_embed_image(linked):
    sk_file, eps_file, png_file = linked
    doc = testsupport.load_document(sk_file)
    eps_obj, png_obj = linked_objects(doc)
    doc.EmbedObjects([png_obj])
    assert png_obj.IsEmbedded()
    assert [o.is_Eps for o in doc.LinkedObjects()] == [1]
    doc.Undo()
    assert png_obj.IsLinked()


def test_replace_embedded_image(linked):
    # an embedded image replaced by another file stays embedded
    sk_file, eps_file, png_file = linked
    doc = testsupport.load_document(sk_file)
    eps_obj, png_obj = linked_objects(doc)
    doc.EmbedObjects([png_obj])
    old = png_obj.Data()
    new_file = os.path.join(os.path.dirname(png_file), 'c.png')
    PIL.Image.new('RGB', (5, 4), (0, 255, 0)).save(new_file)
    doc.RelinkObjects([png_obj], new_file, embed=1)
    assert png_obj.IsEmbedded()
    assert png_obj.Data().Size() == (5, 4)
    doc.Undo()
    assert png_obj.Data() is old


def test_current_external_object(missing):
    sk_file, eps_file, png_file = missing
    doc = testsupport.load_document(sk_file)
    eps_obj, png_obj = linked_objects(doc)
    doc.SelectObject(eps_obj)
    assert doc.CurrentExternalObject(1) is eps_obj
    assert doc.CurrentExternalObject(0) is None
    doc.SelectObject(png_obj)
    assert doc.CurrentExternalObject(0) is png_obj
    doc.SelectObject([eps_obj, png_obj])
    assert doc.CurrentExternalObject(0) is None


def have_ps_import_tools():
    return all(shutil.which(tool) for tool in ('gs', 'pdfinfo', 'pdftocairo'))


@pytest.mark.skipif(not have_ps_import_tools(),
                    reason='needs gs, pdfinfo and pdftocairo')
def test_embed_eps(linked):
    sk_file, eps_file, png_file = linked
    doc = testsupport.load_document(sk_file)
    eps_obj, png_obj = linked_objects(doc)
    rect = eps_obj.coord_rect
    layer = eps_obj.parent
    doc.SelectObject(eps_obj)
    doc.EmbedObjects([eps_obj])
    assert eps_obj.parent is None
    assert [o.is_Image for o in doc.LinkedObjects()] == [1]
    group = layer.GetObjects()[0]
    assert group.is_Compound
    assert doc.CurrentObject() is group
    r = group.coord_rect
    for a, b in ((r.left, rect.left), (r.bottom, rect.bottom),
                 (r.right, rect.right), (r.top, rect.top)):
        assert a == pytest.approx(b, abs=1.0)
    doc.Undo()
    assert layer.GetObjects()[0] is eps_obj
    assert eps_obj.parent is layer
