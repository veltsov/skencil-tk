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
# SVG import: Inkscape and Sketch extras.
#
# - Inkscape arcs (sodipodi:type="arc") become ellipse arcs;
# - Inkscape guides become guide lines;
# - the editing structure of Sketch's own export (Inkscape flavour,
#   devdocs/svg-export.md) is restored: plugin objects from
#   skencil:plugin/skencil:params, LaTeX objects also from TexText's
#   attributes, linked EPS files from skencil:eps-file.  The imported
#   children are kept as the objects' rendering (as when loading a .sk
#   file), so nothing has to be recomputed.

import ast
import math
import os

from Sketch import _, Trafo, Point, Ellipse
from Sketch.Base import const

from . import values
from .values import mul

ARC_TYPES = {'arc': const.ArcArc, 'chord': const.ArcChord,
             'slice': const.ArcPieSlice}


def arc(builder, node, ctm, style):
    """The ellipse (arc) of an Inkscape arc path, or None."""
    try:
        cx = float(node.get('sodipodi:cx'))
        cy = float(node.get('sodipodi:cy'))
        rx = float(node.get('sodipodi:rx'))
        ry = float(node.get('sodipodi:ry'))
    except (TypeError, ValueError):
        return None
    if rx <= 0 or ry <= 0:
        return None
    start = float(node.get('sodipodi:start') or 0.0)
    end = float(node.get('sodipodi:end') or 0.0)
    kind = node.get('sodipodi:arc-type')
    if kind is None:
        kind = 'arc' if node.get('sodipodi:open') == 'true' else 'slice'
    m = mul(ctm, (rx, 0.0, 0.0, ry, cx, cy))
    if abs(values.det(m)) < 1e-12:
        return None
    full = abs(end - start) >= 2 * math.pi - 1e-6 or start == end
    if values.det(m) < 0:
        # positive orientation; the arc runs the other way round
        m = mul(m, (1.0, 0.0, 0.0, -1.0, 0.0, 0.0))
        start, end = -end, -start
    if full:
        start = end = 0.0
    arc_type = ARC_TYPES.get(kind, const.ArcPieSlice)
    def make(properties):
        return Ellipse(Trafo(*m), start % (2 * math.pi), end % (2 * math.pi),
                       arc_type, properties = properties)
    return builder.finish_shape(node, ctm, style, make,
                                fill = full or arc_type != const.ArcArc,
                                user_box = (cx - rx, cy - ry, cx + rx,
                                            cy + ry))


def guides(builder, ctm, viewport_height):
    """The guide lines of the sodipodi:namedview: (position, horizontal)
    in document coordinates."""
    result = []
    for view in builder.root.children:
        if view.tag != 'sodipodi:namedview':
            continue
        for guide in view.children:
            if guide.tag != 'sodipodi:guide':
                continue
            pos = values.numbers(guide.get('position'))
            normal = values.numbers(guide.get('orientation'))
            if len(pos) != 2 or len(normal) != 2:
                continue
            # positions are y up from the bottom of the viewport
            x, y = values.apply(ctm, pos[0], viewport_height - pos[1])
            if abs(normal[0]) < 1e-9 and normal[1]:
                result.append((y, 1))
            elif abs(normal[1]) < 1e-9 and normal[0]:
                result.append((x, 0))
    return result


def plugin_object(builder, node, objects):
    """Re-create the plugin object of a group of Sketch's export from
    its class name and parameters; OBJECTS are its rendered
    children."""
    from Sketch.Base import plugins
    name = node.get('skencil:plugin')
    try:
        params = ast.literal_eval(node.get('skencil:params') or '()')
    except (ValueError, SyntaxError):
        return None
    if not isinstance(params, tuple):
        return None
    info = plugins.find_object_plugin(name)
    if info is None:
        builder.warn(_("Unknown Plugin: %s") % name)
        return None
    if node.get('textext:text') is not None:
        objects = unwrap(objects)
    try:
        theclass = info.Constructor()
        obj = theclass(*params, loading = 1)
        for child in objects:
            obj.load_AppendObject(child)
        obj.load_Done()
    except Exception:
        builder.warn(_("Plugin objects imported as groups"))
        return None
    return obj


def unwrap(objects):
    """The children of the inner group of a TexText group."""
    if len(objects) == 1 and objects[0].is_Group:
        return objects[0].GetObjects()
    return objects


def textext_object(builder, node, objects, ctm):
    """A LaTeX object for a TexText group not written by Sketch (no
    skencil:plugin): the text and the size from TexText's attributes,
    the transformation by inverting the export (svg-export.md)."""
    from Sketch.Base import plugins
    info = plugins.find_object_plugin('LtxObj')
    if info is None:
        return None
    text = node.get('textext:text') or ''
    try:
        text = text.encode('utf-8').decode('unicode_escape')
    except UnicodeError:
        pass
    try:
        scale = float(node.get('textext:scale') or '1')
    except ValueError:
        scale = 1.0
    size = scale * 10.0
    if size <= 0:
        return None
    trafo = mul(ctm, mul((1.0, 0.0, 0.0, -1.0, 0.0, 0.0),
                         values.scale(1 / scale)))
    try:
        obj = info.Constructor()(text, size, Trafo(*trafo), loading = 1)
        for child in unwrap(objects):
            obj.load_AppendObject(child)
        obj.load_Done()
    except Exception:
        return None
    return obj


def eps_object(builder, node, ctm):
    """A linked EPS image for a group with skencil:eps-file: placed by
    the bounding box clip of the export.  None if the file is not
    there or the placement cannot be recovered."""
    from Sketch.Graphics.eps import EpsImage
    filename = node.get('skencil:eps-file')
    if not filename or not os.path.exists(filename):
        return None
    clip = builder.lookup(values.url_id(node.get('clip-path')))
    if clip is None or len(clip.children) != 1 \
       or clip.children[0].tag != 'path':
        return None
    from . import pathdata
    subs = pathdata.parse(clip.children[0].get('d'))
    if len(subs) != 1 or len(subs[0].segments) < 3:
        return None
    pts = [subs[0].start] + [seg[-2:] for seg in subs[0].segments[:3]]
    pts = [values.apply(ctm, x, y) for x, y in pts]
    try:
        w, h = EpsImage(filename).data.Size()
        if w <= 0 or h <= 0:
            return None
        # the clip polygon is the trafo of (0,0), (w,0), (w,h), (0,h)
        (x0, y0), (x1, y1), (x2, y2), (x3, y3) = pts
        trafo = Trafo((x1 - x0) / w, (y1 - y0) / w, (x3 - x0) / h,
                      (y3 - y0) / h, x0, y0)
        return EpsImage(filename, trafo)
    except Exception:
        return None
