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
# SVG import: markers.
#
# Markers are drawn as explicit objects at the vertices of paths,
# lines, polylines and polygons (orient, markerUnits, viewBox, refX/Y,
# clipped to the marker viewport unless overflow is visible).  The
# arrows of Sketch's own SVG export (single open subpaths) become
# native arrows again: the marker shape is matched against the
# standard arrows and the path ends are extended by the retraction the
# arrows imply.

import math

from Sketch import _, Group, Point

from . import values, pathdata
from .values import mul

MARKED = ('path', 'line', 'polyline', 'polygon')

EPS = 1e-9


def direction(dx, dy):
    if abs(dx) < EPS and abs(dy) < EPS:
        return None
    return math.atan2(dy, dx)


def segment_directions(start, seg):
    """The directions at the start and at the end of SEG (from START)."""
    x0, y0 = start
    if seg[0] == 'L':
        a = direction(seg[1] - x0, seg[2] - y0)
        return a, a
    x1, y1, x2, y2, x3, y3 = seg[1:]
    d0 = direction(x1 - x0, y1 - y0)
    if d0 is None:
        d0 = direction(x2 - x0, y2 - y0)
    if d0 is None:
        d0 = direction(x3 - x0, y3 - y0)
    d1 = direction(x3 - x2, y3 - y2)
    if d1 is None:
        d1 = direction(x3 - x1, y3 - y1)
    if d1 is None:
        d1 = direction(x3 - x0, y3 - y0)
    return d0, d1


def bisector(a_in, a_out):
    if a_in is None:
        return a_out or 0.0
    if a_out is None:
        return a_in
    d = (a_out - a_in) % (2 * math.pi)
    if d > math.pi:
        d -= 2 * math.pi
    return a_in + d / 2


def vertices(subpaths):
    """The marker vertices of SUBPATHS (user space): a list of (kind, x,
    y, angle in, angle out) with KIND 'start', 'mid' or 'end'."""
    result = []
    for sub in subpaths:
        points = [sub.start]
        dirs = []
        start = sub.start
        for seg in sub.segments:
            dirs.append(segment_directions(start, seg))
            start = seg[-2:]
            points.append(start)
        if sub.closed:
            x0, y0 = sub.start
            if abs(start[0] - x0) > EPS or abs(start[1] - y0) > EPS:
                a = direction(x0 - start[0], y0 - start[1])
                dirs.append((a, a))
                points.append(sub.start)
        for i, (x, y) in enumerate(points):
            a_in = dirs[i - 1][1] if i > 0 else None
            a_out = dirs[i][0] if i < len(dirs) else None
            if sub.closed and dirs:
                if i == 0:
                    a_in = dirs[-1][1]
                elif i == len(points) - 1:
                    a_out = dirs[0][0]
            result.append(['mid', x, y, a_in, a_out])
    if result:
        result[0][0] = 'start'
        if len(result) > 1:
            result[-1][0] = 'end'
        else:
            result.append(['end'] + result[0][1:])
    return result


class Markers:

    def __init__(self, builder):
        self.builder = builder
        self.native = None

    def marker_node(self, style, which):
        value = style['marker-' + which]
        if not value or value == 'none':
            return None
        node = self.builder.lookup(values.url_id(value))
        if node is None or node.tag != 'marker':
            return None
        return node

    def apply(self, node, objects, ctm, style, subpaths):
        """OBJECTS (of the path NODE) with the markers of STYLE."""
        b = self.builder
        if node.tag not in MARKED or b.clips.clip_mode or not objects:
            return objects
        nodes = dict((which, self.marker_node(style, which))
                     for which in ('start', 'mid', 'end'))
        if not any(nodes.values()):
            return objects
        if self.native_arrows(objects, nodes, subpaths, ctm):
            return objects
        stroke_width = values.length(style['stroke-width'], 0.0,
                                     style['font-size'], 1.0)
        marks = []
        for kind, x, y, a_in, a_out in vertices(subpaths):
            marker = nodes[kind]
            if marker is None:
                continue
            orient = marker.get('orient', '0').strip()
            if orient in ('auto', 'auto-start-reverse'):
                if kind == 'start':
                    angle = a_out if a_out is not None else (a_in or 0.0)
                    if orient == 'auto-start-reverse':
                        angle += math.pi
                elif kind == 'end':
                    angle = a_in if a_in is not None else (a_out or 0.0)
                else:
                    angle = bisector(a_in, a_out)
                angle = math.degrees(angle)
            else:
                nums = values.numbers(orient)
                angle = nums[0] if nums else 0.0
                if orient.endswith('rad'):
                    angle = math.degrees(angle)
                elif orient.endswith('turn'):
                    angle *= 360
            marks.extend(self.draw(marker, ctm, x, y, angle, stroke_width))
        if not marks:
            return objects
        return [Group(list(objects) + marks)]

    def draw(self, marker, ctm, x, y, angle, stroke_width):
        b = self.builder
        if marker in b.use_stack:
            return []
        style = b.tree_style(marker)
        fs = style['font-size']
        mw = values.length(marker.get('markerWidth'), 0, fs, 3.0)
        mh = values.length(marker.get('markerHeight'), 0, fs, 3.0)
        if mw <= 0 or mh <= 0:
            return []
        m = mul(ctm, values.translate(x, y))
        m = mul(m, values.rotate(angle))
        if marker.get('markerUnits', 'strokeWidth') == 'strokeWidth':
            m = mul(m, values.scale(stroke_width))
        from .builder import parse_viewbox, viewbox_transform
        viewbox = parse_viewbox(marker.get('viewBox'))
        content = viewbox_transform(viewbox,
                                    marker.get('preserveAspectRatio'),
                                    mw, mh) if viewbox else values.IDENTITY
        rx = values.length(marker.get('refX'), 0, fs, 0.0)
        ry = values.length(marker.get('refY'), 0, fs, 0.0)
        ref = values.apply(content, rx, ry)
        m = mul(m, values.translate(-ref[0], -ref[1]))
        b.use_stack.append(marker)
        try:
            objects = b.children(marker, mul(m, content), style,
                                 viewbox[2:] if viewbox else (mw, mh))
        finally:
            b.use_stack.pop()
        if objects and style['overflow'] in ('hidden', 'scroll', 'auto'):
            objects = b.clips.clip_rect(objects, m, 0, 0, mw, mh)
        return objects

    # ------------------------------------------------- Sketch's own arrows

    def standard_arrows(self):
        if self.native is None:
            from Sketch import StandardArrows
            self.native = []
            for arrow in StandardArrows():
                shapes = {}
                for which, flip in (('start', (-1.0, 0.0, 0.0, 1.0, 0, 0)),
                                    ('end', (1.0, 0.0, 0.0, -1.0, 0, 0))):
                    pts = []
                    for path in arrow.Paths():
                        for i in range(path.len):
                            pts.append(values.apply(flip, *path.Node(i)))
                    shapes[which] = pts
                self.native.append((arrow, shapes))
        return self.native

    def match_arrow(self, marker, which):
        """The standard arrow drawn by MARKER (from Sketch's export), or
        None."""
        b = self.builder
        if b.root.get('skencil:version') is None \
           or marker.get('orient') != 'auto' \
           or marker.get('markerUnits', 'strokeWidth') != 'strokeWidth' \
           or len(marker.children) != 1 or marker.children[0].tag != 'path':
            return None
        subs = pathdata.parse(marker.children[0].get('d'))
        pts = []
        for sub in subs:
            pts.append(sub.start)
            pts.extend(seg[-2:] for seg in sub.segments)
        for arrow, shapes in self.standard_arrows():
            ref = shapes[which]
            if len(ref) != len(pts):
                continue
            if all(abs(p[0] - q[0]) < 1e-3 and abs(p[1] - q[1]) < 1e-3
                   for p, q in zip(pts, ref)):
                return arrow
        return None

    def native_arrows(self, objects, nodes, subpaths, ctm):
        """Turn the markers of Sketch's export into native arrows."""
        if nodes['mid'] is not None or len(objects) != 1 \
           or not objects[0].is_Bezier or len(subpaths) != 1 \
           or subpaths[0].closed:
            return False
        arrows = {}
        for which in ('start', 'end'):
            if nodes[which] is not None:
                arrow = self.match_arrow(nodes[which], which)
                if arrow is None:
                    return False
                arrows[which] = arrow
        obj = objects[0]
        props = obj.Properties()
        if not props.HasLine():
            return False
        width = max(props.line_width, 1.0)
        # the export wrote the retracted path: extend its ends again
        from .builder import make_path
        sub = subpaths[0].transformed(ctm)
        if 'start' in arrows and arrows['start'].Head():
            sub = extend(sub, 0, arrows['start'].Head().x * width)
        if 'end' in arrows and arrows['end'].Head():
            sub = extend(sub, 1, arrows['end'].Head().x * width)
        obj.SetPaths((make_path(sub),))
        obj.SetProperties(line_arrow1 = arrows.get('start'),
                          line_arrow2 = arrows.get('end'))
        return True


def extend(sub, at_end, length):
    """SUB with its start (AT_END false) or end point moved outward by
    LENGTH, undoing PolyBezier.retract_for_arrows (which moves the end
    point only, along the direction from the neighbouring control
    point)."""
    segs = list(sub.segments)
    if at_end:
        seg = segs[-1]
        prev = sub.start if len(segs) == 1 else segs[-2][-2:]
        anchor = seg[3:5] if seg[0] == 'C' else prev
        x, y = seg[-2:]
    else:
        seg = segs[0]
        anchor = seg[1:3] if seg[0] == 'C' else seg[-2:]
        x, y = sub.start
    # the original end p satisfies p - length * unit(p - anchor) = (x, y)
    px, py = x, y
    for i in range(20):
        dx, dy = px - anchor[0], py - anchor[1]
        n = math.hypot(dx, dy)
        if n < EPS:
            dx, dy = x - anchor[0], y - anchor[1]
            n = math.hypot(dx, dy) or 1.0
        px, py = x + length * dx / n, y + length * dy / n
    result = pathdata.SubPath(*sub.start)
    result.segments = segs
    result.closed = sub.closed
    if at_end:
        segs[-1] = seg[:-2] + (px, py)
    else:
        result.start = (px, py)
    return result
