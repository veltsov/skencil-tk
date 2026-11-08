# Sketch - A Python-based interactive drawing program
# Copyright (C) 2026 by Vladimir Eltsov
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Library General Public
# License as published by the Free Software Foundation; either
# version 2 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Library General Public License for more details.
#
# You should have received a copy of the GNU Library General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA

# SVG import: clip paths.
#
# A clip becomes a MaskGroup whose mask is a single object without fill
# and line (the mask's fill and line would be drawn): a rectangle or
# ellipse if the clip path is just that, otherwise one PolyBezier with
# the subpaths of all children of the clip path, their union reduced to
# an even-odd fill (fillrule.py).  Clips that do not cut anything off
# are dropped.

from Sketch import _, Trafo, PolyBezier, Rectangle, MaskGroup, \
     EmptyPattern, PropertyStack
from Sketch.Graphics.properties import factory_defaults

from . import values, pathdata
from .values import mul

EPS = 1e-6

def empty_properties():
    base = factory_defaults.Copy()
    base.fill_pattern = EmptyPattern
    base.line_pattern = EmptyPattern
    return PropertyStack(base = base)

def subpaths_of(obj):
    """The document space subpaths of a Sketch object (as SubPaths)."""
    if not obj.is_Bezier:
        if obj.is_Compound:
            result = []
            for child in obj.GetObjects():
                result.extend(subpaths_of(child))
            return result
        obj = obj.AsBezier()
        if obj is None:
            return []
        if obj.is_Compound:
            return subpaths_of(obj)
    result = []
    for path in obj.Paths():
        result.append(subpath_from_path(path))
    return result

def subpath_from_path(path):
    from Sketch.Modules._sketch import Bezier
    n = path.len
    x, y = path.Node(0)
    sub = pathdata.SubPath(x, y)
    for i in range(1, n):
        seg = path.Segment(i)
        if seg[0] == Bezier:
            (x1, y1), (x2, y2) = seg[1]
            x, y = seg[2]
            sub.segments.append(('C', x1, y1, x2, y2, x, y))
        else:
            x, y = seg[2]
            sub.segments.append(('L', x, y))
    sub.closed = bool(path.closed)
    return sub

def rect_of(obj):
    """(l, b, r, t) if OBJ is an axis-parallel rectangle, else None."""
    if obj.is_Rectangle:
        t = obj.trafo
        if obj.radius1 or obj.radius2:
            return None
        if abs(t.m12) > EPS or abs(t.m21) > EPS:
            return None
        xs = (t.v1, t.v1 + t.m11)
        ys = (t.v2, t.v2 + t.m22)
        return (min(xs), min(ys), max(xs), max(ys))
    if obj.is_Bezier and len(obj.Paths()) == 1:
        sub = subpath_from_path(obj.Paths()[0])
        pts = [sub.start] + [seg[-2:] for seg in sub.segments]
        if any(seg[0] != 'L' for seg in sub.segments):
            return None
        if len(pts) == 5 and abs(pts[0][0] - pts[4][0]) < EPS \
           and abs(pts[0][1] - pts[4][1]) < EPS:
            pts = pts[:4]
        if len(pts) != 4:
            return None
        for i in range(4):
            (x1, y1), (x2, y2) = pts[i - 1], pts[i]
            if abs(x1 - x2) > EPS and abs(y1 - y2) > EPS:
                return None
        xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
        return (min(xs), min(ys), max(xs), max(ys))
    return None


class Clipper:

    def __init__(self, builder):
        self.builder = builder
        self.clip_mode = 0

    def apply(self, node, objects, ctm, style, vp):
        b = self.builder
        id = values.url_id(style['clip-path'])
        ref = b.lookup(id)
        if ref is None or ref.tag != 'clipPath':
            if style['clip-path'].strip().startswith('url'):
                b.warn(_("Reference to an unknown clip path ignored"))
            else:
                b.warn(_("Basic shape clip paths ignored"))
            return objects
        if ref in b.use_stack:
            b.warn(_("Recursive references ignored"))
            return objects
        b.use_stack.append(ref)
        try:
            masks = self.mask_objects(ref, ctm, objects, vp)
        finally:
            b.use_stack.pop()
        for mask in masks:
            objects = self.clip(objects, mask)
        return objects

    def mask_objects(self, ref, ctm, objects, vp):
        """The masks for the clip path REF: one object, plus the masks of
        the clip path's own clip path (intersected by nesting)."""
        b = self.builder
        m = values.parse_transform(ref.get('transform')) or values.IDENTITY
        if ref.get('clipPathUnits') == 'objectBoundingBox':
            box = self.user_bbox(objects, ctm)
            if box is None:
                return []
            l, bt, r, t = box
            m = mul(m, (r - l, 0.0, 0.0, t - bt, l, bt))
        m = mul(ctm, m)
        style = b.tree_style(ref)
        self.clip_mode += 1
        try:
            groups = []
            shapes = []
            for child in ref.children:
                child_style = b.cascade.compute(child, style)
                if child.tag == 'use':
                    target = b.lookup(values.href_id(child.href()))
                    if target is None or target.tag not in \
                       ('rect', 'circle', 'ellipse', 'line', 'polyline',
                        'polygon', 'path', 'text'):
                        continue
                for obj in b.render(child, m, style, vp):
                    shapes.append(obj)
                    groups.append((subpaths_of(obj),
                                   child_style['clip-rule']))
        finally:
            self.clip_mode -= 1
        result = []
        if len(shapes) == 1 and (shapes[0].is_Rectangle
                                 or shapes[0].is_Ellipse):
            mask = shapes[0]
            mask.SetProperties(fill_pattern = EmptyPattern,
                               line_pattern = EmptyPattern)
            result.append(mask)
        else:
            groups = [g for g in groups if g[0]]
            subs = b.fillrule.even_odd_equivalent(None, None, b.warn,
                                                  groups = groups) \
                   if groups else []
            from .builder import make_path
            paths = tuple(make_path(sub) for sub in subs
                          if sub.segments and not sub.is_degenerate())
            if paths:
                result.append(PolyBezier(paths = paths,
                                         properties = empty_properties()))
            else:
                # an empty clip path: nothing is visible
                result.append(None)
        if style['clip-path'] != 'none':
            id = values.url_id(style['clip-path'])
            outer = b.lookup(id)
            if outer is not None and outer.tag == 'clipPath' \
               and outer not in b.use_stack:
                b.use_stack.append(outer)
                try:
                    result.extend(self.mask_objects(outer, ctm, objects, vp))
                finally:
                    b.use_stack.pop()
        return result

    def user_bbox(self, objects, ctm):
        """The bounding box of OBJECTS in the user space of CTM
        (geometric, approximated through the document bounds)."""
        box = None
        for obj in objects:
            r = obj.coord_rect
            box = box and [min(box[0], r.left), min(box[1], r.bottom),
                           max(box[2], r.right), max(box[3], r.top)] \
                  or [r.left, r.bottom, r.right, r.top]
        if box is None:
            return None
        inv = values.inverse(ctm)
        if inv is None:
            return None
        corners = [values.apply(inv, x, y) for x in (box[0], box[2])
                   for y in (box[1], box[3])]
        xs = [c[0] for c in corners]; ys = [c[1] for c in corners]
        if max(xs) - min(xs) <= 0 or max(ys) - min(ys) <= 0:
            return None
        return (min(xs), min(ys), max(xs), max(ys))

    def clip_rect(self, objects, ctm, x, y, w, h):
        m = mul(ctm, (w, 0.0, 0.0, h, x, y))
        if values.det(m) < 0:
            m = mul(m, (1.0, 0.0, 0.0, -1.0, 0.0, 1.0))
        mask = Rectangle(Trafo(*m), properties = empty_properties())
        return self.clip(objects, mask)

    def clip(self, objects, mask):
        """Clip OBJECTS by MASK; None clips everything away."""
        if mask is None:
            return []
        if not objects:
            return objects
        rect = rect_of(mask)
        if rect is not None:
            from .builder import bounds
            box = bounds(objects)
            if box[0] >= rect[0] - EPS and box[1] >= rect[1] - EPS \
               and box[2] <= rect[2] + EPS and box[3] <= rect[3] + EPS:
                return objects
            if box[0] >= rect[2] or box[2] <= rect[0] \
               or box[1] >= rect[3] or box[3] <= rect[1]:
                # completely clipped away
                return []
        return [MaskGroup([mask] + list(objects))]
