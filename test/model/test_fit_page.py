# Layer 1: the "Fit Page to Objects" script (Sketch.Scripts.fit_page).


import pytest

import testsupport


def fit(doc, margin, selected_only = 0):
    from Sketch.Scripts.fit_page import fit_page_to_objects
    doc.BeginTransaction('fit')
    try:
        result = fit_page_to_objects(doc, margin, selected_only)
    finally:
        doc.EndTransaction()
    return result


@pytest.mark.parametrize('margin', [0, 10])
def test_fit_page(margin):
    doc = testsupport.load_document(testsupport.data_path('tarr.sk'))
    from Sketch import Point
    from Sketch.Graphics.guide import GuideLine
    guides = [l for l in doc.Layers() if l.is_GuideLayer][0]
    doc.AddUndo(guides.Insert(GuideLine(Point(0, 100)), None)[1])
    old_rect = doc.BoundingRect()
    old_size = doc.PageSize()
    assert fit(doc, margin)
    r = doc.BoundingRect()
    w, h = doc.PageSize()
    eps = 1e-3      # rects are single precision
    assert abs(r.left - margin) < eps and abs(r.bottom - margin) < eps
    assert abs(r.right + margin - w) < eps and abs(r.top + margin - h) < eps
    assert abs(guides.GetObjects()[-1].point.y
               - (100 + margin - old_rect.bottom)) < eps
    doc.Undo()
    assert doc.PageSize() == old_size
    r = doc.BoundingRect()
    assert max(abs(a - b) for a, b in zip(r, old_rect)) < eps, (tuple(r), tuple(old_rect))


def test_fit_page_selected_only():
    doc = testsupport.load_document(testsupport.data_path('tarr.sk'))
    objects = [o for l in doc.Layers() if not l.is_SpecialLayer
               for o in l.GetObjects()]
    assert len(objects) >= 2
    doc.SelectObject(objects[0])
    sel_rect = doc.SelectionBoundingRect()
    margin = 5
    assert fit(doc, margin, selected_only = 1)
    r = doc.SelectionBoundingRect()
    w, h = doc.PageSize()
    eps = 1e-3
    assert abs(r.left - margin) < eps and abs(r.bottom - margin) < eps
    assert abs(w - (sel_rect.right - sel_rect.left + 2 * margin)) < eps
    assert abs(h - (sel_rect.top - sel_rect.bottom + 2 * margin)) < eps


def test_fit_page_selected_only_no_selection():
    doc = testsupport.load_document(testsupport.data_path('tarr.sk'))
    old_size = doc.PageSize()
    assert not fit(doc, 0, selected_only = 1)
    assert doc.PageSize() == old_size
