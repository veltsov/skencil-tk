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

# SVG import: the builder -- walks the tree and creates Sketch objects.
#
# Geometry is baked into document coordinates: every element is
# rendered with its current transformation matrix (CTM), which maps its
# user space to the document (points, y up).  See devdocs/svg-import.md.

import math
import os

from Sketch import _, Trafo, CreatePath, PolyBezier, Rectangle, Ellipse, \
     Group, MaskGroup, EmptyPattern, Style, PropertyStack
from Sketch.Graphics.properties import factory_defaults
from Sketch.Base import const

from . import values, pathdata, paint, tree
from .values import mul, IDENTITY

# elements that are never rendered directly (only through references)
NOT_RENDERED = set(['defs', 'symbol', 'clipPath', 'mask', 'marker',
                    'pattern', 'linearGradient', 'radialGradient', 'style',
                    'metadata', 'title', 'desc', 'script', 'font',
                    'font-face', 'filter', 'sodipodi:namedview', 'cursor',
                    'view', 'foreignObject', 'solidColor', 'solidcolor',
                    'hatch', 'meshgradient', 'stop'])

SHAPES = set(['rect', 'circle', 'ellipse', 'line', 'polyline', 'polygon',
              'path'])

PT_PER_PX = 0.75

# the maximal depth of use references
MAX_USE_DEPTH = 50

EPS = 1e-9


def is_layer(node):
    return node.tag == 'g' and node.get('inkscape:groupmode') == 'layer'


def preserve_aspect_ratio(text):
    """Parse preserveAspectRatio: (align, slice) with ALIGN None for
    `none' or a pair of factors (0, 0.5 or 1) for x and y."""
    parts = (text or 'xMidYMid meet').split()
    if parts and parts[0] == 'defer':
        parts = parts[1:]
    align = parts[0] if parts else 'xMidYMid'
    slice = len(parts) > 1 and parts[1] == 'slice'
    if align == 'none':
        return None, slice
    factors = {'Min': 0.0, 'Mid': 0.5, 'Max': 1.0}
    try:
        fx = factors[align[1:4]]
        fy = factors[align[5:8]]
    except (KeyError, IndexError):
        fx = fy = 0.5
    return (fx, fy), slice


def viewbox_transform(viewbox, par, width, height):
    """The matrix mapping the VIEWBOX (x, y, w, h) into the viewport
    (0, 0, WIDTH, HEIGHT) according to the preserveAspectRatio PAR."""
    vx, vy, vw, vh = viewbox
    sx = width / vw
    sy = height / vh
    align, slice = preserve_aspect_ratio(par)
    if align is None:
        return (sx, 0.0, 0.0, sy, -vx * sx, -vy * sy)
    s = max(sx, sy) if slice else min(sx, sy)
    tx = (width - vw * s) * align[0] - vx * s
    ty = (height - vh * s) * align[1] - vy * s
    return (s, 0.0, 0.0, s, tx, ty)


def parse_viewbox(text):
    if not text:
        return None
    nums = values.numbers(text)
    if len(nums) != 4 or nums[2] <= 0 or nums[3] <= 0:
        return None
    return tuple(nums)


def bounds(objects):
    """The union of the bounding rects of OBJECTS as (l, b, r, t)."""
    result = None
    for obj in objects:
        r = obj.bounding_rect
        if result is None:
            result = [r.left, r.bottom, r.right, r.top]
        else:
            result[0] = min(result[0], r.left)
            result[1] = min(result[1], r.bottom)
            result[2] = max(result[2], r.right)
            result[3] = max(result[3], r.top)
    return result


def make_path(sub):
    """A Sketch path from the SubPath SUB (document coordinates)."""
    path = CreatePath()
    path.AppendLine(*sub.start)
    for seg in sub.segments:
        if seg[0] == 'L':
            path.AppendLine(seg[1], seg[2])
        else:
            path.AppendBezier(*seg[1:])
    if sub.closed:
        x, y = sub.end()
        if abs(x - sub.start[0]) > EPS or abs(y - sub.start[1]) > EPS:
            path.AppendLine(*sub.start)
        if path.len > 1:
            path.ClosePath()
    return path


class Builder:

    def __init__(self, root, base_dir = '', warn = None, options = None):
        self.root = root
        self.options = options or {}
        self.base_dir = base_dir
        self.warn = warn or (lambda message: None)
        self.ids = {}
        for node in root.iter():
            node_id = node.get('id')
            if node_id and node_id not in self.ids:
                self.ids[node_id] = node
        self.cascade = tree.Cascade(root)
        self.use_stack = []
        self.current_vp = (100.0, 100.0)
        # opacity is blended toward this color (black in masks)
        self.background = paint.WHITE
        self._tree_styles = {}
        self.page = None
        self.root_scale = PT_PER_PX
        # hooks of the other modules
        from . import text, image, clip, gradient, marker, mask, fillrule
        self.text = text.TextConverter(self)
        self.images = image
        self.clips = clip.Clipper(self)
        self.gradients = gradient.Gradients(self)
        self.markers = marker.Markers(self)
        self.masks = mask.Masker(self)
        self.fillrule = fillrule

    def lookup(self, id):
        return id and self.ids.get(id)

    def tree_style(self, node):
        """The computed style of NODE in its place in the document tree
        (for referenced elements: clip paths, gradients, markers, ...)."""
        cache = self._tree_styles
        style = cache.get(id(node))
        if style is None:
            if node.parent is None:
                parent = tree.ROOT_STYLE
            else:
                parent = self.tree_style(node.parent)
            style = cache[id(node)] = self.cascade.compute(node, parent)
        return style

    # ------------------------------------------------------------ the root

    def root_viewport(self):
        """The CTM of the root, its viewport size in user units and the
        page size in points (None if the SVG does not give one)."""
        root = self.root
        viewbox = parse_viewbox(root.get('viewBox'))
        width = root.get('width')
        height = root.get('height')
        w = values.length(width)
        h = values.length(height)
        if width and width.strip().endswith('%'):
            w = None
        if height and height.strip().endswith('%'):
            h = None
        if viewbox:
            if w is None and h is None:
                w, h = viewbox[2], viewbox[3]
            elif w is None:
                w = h * viewbox[2] / viewbox[3]
            elif h is None:
                h = w * viewbox[3] / viewbox[2]
        if w is not None and h is not None and w > 0 and h > 0:
            page = (w * PT_PER_PX, h * PT_PER_PX)
        else:
            page = None
            w = w or 0.0
            h = h or 0.0
        if viewbox and w and h:
            m = viewbox_transform(viewbox, root.get('preserveAspectRatio'),
                                  w, h)
            vp = viewbox[2:]
        else:
            m = IDENTITY
            vp = (w or 100.0, h or 100.0)
        height_pt = page[1] if page else 0.0
        ctm = mul((PT_PER_PX, 0.0, 0.0, -PT_PER_PX, 0.0, height_pt), m)
        return ctm, vp, page

    def build(self):
        """Render the document.  Returns (page, layers): PAGE is the page
        size in points or None, LAYERS a list of (name, visible, locked,
        attributes, objects)."""
        root = self.root
        ctm, vp, page = self.root_viewport()
        self.page = page
        self.root_scale = values.mean_scale(ctm)
        style = self.cascade.compute(root, tree.ROOT_STYLE)
        layers = []
        pending = []
        def flush():
            if pending:
                layers.append((None, 1, 0, {}, pending[:]))
                del pending[:]
        for child in root.children:
            if is_layer(child):
                flush()
                layers.append(self.layer(child, ctm, style, vp))
            else:
                pending.extend(self.render(child, ctm, style, vp))
        flush()
        if page is None:
            box = bounds([obj for layer in layers for obj in layer[-1]])
            if box:
                # no size given: the page is the bounding box, moved to
                # the origin
                dx, dy = -box[0], -box[1]
                for layer in layers:
                    for obj in layer[-1]:
                        obj.Translate(_point(dx, dy))
                self.page = (box[2] - box[0], box[3] - box[1])
        return self.page, layers

    def render_root(self, ctm, vp, parent_style):
        """Render the whole document into the viewport (0, 0) - VP of
        CTM, without layers (an SVG used as an image)."""
        root = self.root
        self.root_scale = values.mean_scale(ctm)
        viewbox = parse_viewbox(root.get('viewBox'))
        if viewbox:
            ctm = mul(ctm, viewbox_transform(
                viewbox, root.get('preserveAspectRatio'), vp[0], vp[1]))
            vp = viewbox[2:]
        style = self.cascade.compute(root, parent_style)
        return self.children(root, ctm, style, vp)

    def layer(self, node, ctm, parent_style, vp):
        style = self.cascade.compute(node, parent_style)
        visible = style['display'] != 'none'
        locked = node.get('sodipodi:insensitive') == 'true'
        style['display'] = 'inline'
        objects = self.render(node, ctm, parent_style, vp, style = style,
                              wrap = 0)
        attrs = {}
        for name in ('printable', 'outlined'):
            value = node.get('skencil:' + name)
            if value is not None:
                attrs[name] = value not in ('0', 'false')
        name = node.get('inkscape:label') or node.get('id')
        return (name, visible, locked, attrs, objects)

    # ------------------------------------------------------------ elements

    def render(self, node, ctm, parent_style, vp, style = None, wrap = 1):
        """Render NODE.  Returns a list of Sketch objects."""
        tag = node.tag
        if tag in NOT_RENDERED or ':' in tag or tag[0] == '{':
            return []
        if tag in ('text', 'flowRoot'):
            converted = self.text.replacement(node)
            if converted is not None:
                # text converted to curves by Inkscape (text.py)
                return self.render(converted, ctm, parent_style, vp)
        if style is None:
            style = self.cascade.compute(node, parent_style)
        if style['display'] == 'none':
            return []
        if node.get('requiredExtensions') is not None and tag != 'switch':
            # an extension we do not have (switch children are handled
            # by the switch)
            return []
        m = values.parse_transform(node.get('transform'))
        if m is None:
            self.warn(_("Invalid transform attributes ignored"))
            m = IDENTITY
        ctm = mul(ctm, m)
        if tag in SHAPES:
            objects = self.shape(node, ctm, style, vp)
        elif tag in ('g', 'a'):
            objects = self.children(node, ctm, style, vp)
            if wrap and len(objects) > 1:
                objects = [Group(objects)]
        elif tag == 'switch':
            objects = self.switch(node, ctm, style, vp)
        elif tag == 'use':
            objects = self.use(node, ctm, style, vp)
        elif tag == 'svg':
            objects = self.nested_svg(node, ctm, style, vp)
        elif tag == 'image':
            objects = self.images.image(self, node, ctm, style, vp)
        elif tag == 'text':
            objects = self.text.text(node, ctm, style, vp)
        elif tag == 'flowRoot':
            objects = self.text.flow(node, ctm, style, vp)
        else:
            if tag not in ('tspan', 'textPath', 'tref', 'flowRegion',
                           'flowPara', 'flowDiv', 'flowSpan'):
                self.warn(_("Unsupported SVG element <%s> ignored") % tag)
            return []
        if objects:
            objects = self.effects(node, objects, ctm, style, vp)
        return objects

    def children(self, node, ctm, style, vp):
        objects = []
        for child in node.children:
            objects.extend(self.render(child, ctm, style, vp))
        return objects

    def switch(self, node, ctm, style, vp):
        for child in node.children:
            if child.tag in NOT_RENDERED or ':' in child.tag:
                continue
            if child.get('requiredExtensions') is not None:
                continue
            if child.get('requiredFeatures') is not None \
               and child.get('requiredFeatures').strip() == '':
                continue
            return self.render(child, ctm, style, vp)
        return []

    def effects(self, node, objects, ctm, style, vp):
        """Apply filter, mask and clip-path of NODE to its OBJECTS."""
        if style['filter'] != 'none':
            self.warn(_("Filter effects ignored"))
        if style['mask'] != 'none':
            objects = self.masks.apply(node, objects, ctm, style, vp)
        if style['clip-path'] != 'none' and objects:
            objects = self.clips.apply(node, objects, ctm, style, vp)
        return objects

    # ---------------------------------------------------------- references

    def use(self, node, ctm, style, vp):
        ref_id = values.href_id(node.href())
        ref = self.lookup(ref_id)
        if ref is None:
            if ref_id:
                self.warn(_("Reference to an unknown element ignored"))
            return []
        if ref in self.use_stack or len(self.use_stack) > MAX_USE_DEPTH:
            self.warn(_("Recursive references ignored"))
            return []
        fs = style['font-size']
        x = values.length(node.get('x'), vp[0], fs, 0.0)
        y = values.length(node.get('y'), vp[1], fs, 0.0)
        ctm = mul(ctm, values.translate(x, y))
        self.use_stack.append(ref)
        try:
            if ref.tag in ('symbol', 'svg'):
                ref_style = self.cascade.compute(ref, style)
                if ref_style['display'] == 'none':
                    return []
                w = node.get('width') or ref.get('width')
                h = node.get('height') or ref.get('height')
                width = values.length(w or '100%', vp[0], fs)
                height = values.length(h or '100%', vp[1], fs)
                if ref.tag == 'symbol':
                    rx = values.length(ref.get('x'), vp[0], fs, 0.0)
                    ry = values.length(ref.get('y'), vp[1], fs, 0.0)
                    ctm = mul(ctm, values.translate(rx, ry))
                    m = values.parse_transform(ref.get('transform'))
                    if m:
                        ctm = mul(ctm, m)
                objects = self.viewport(ref, ctm, ref_style, vp, width,
                                        height)
                if ref.tag == 'symbol' and len(objects) > 1:
                    objects = [Group(objects)]
                return self.effects(ref, objects, ctm, ref_style, vp) \
                       if objects else objects
            return self.render(ref, ctm, style, vp)
        finally:
            self.use_stack.pop()

    def nested_svg(self, node, ctm, style, vp):
        fs = style['font-size']
        x = values.length(node.get('x'), vp[0], fs, 0.0)
        y = values.length(node.get('y'), vp[1], fs, 0.0)
        width = values.length(node.get('width', '100%'), vp[0], fs)
        height = values.length(node.get('height', '100%'), vp[1], fs)
        objects = self.viewport(node, mul(ctm, values.translate(x, y)),
                                style, vp, width, height)
        if len(objects) > 1:
            objects = [Group(objects)]
        return objects

    def viewport(self, node, ctm, style, vp, width, height):
        """Render the children of the viewport element NODE (svg,
        symbol) of size WIDTH x HEIGHT at the origin of CTM."""
        if width is None or height is None or width <= 0 or height <= 0:
            return []
        viewbox = parse_viewbox(node.get('viewBox'))
        inner = ctm
        if viewbox:
            inner = mul(ctm, viewbox_transform(
                viewbox, node.get('preserveAspectRatio'), width, height))
            new_vp = viewbox[2:]
        else:
            new_vp = (width, height)
        objects = self.children(node, inner, style, new_vp)
        if objects and style['overflow'] in ('hidden', 'scroll', 'auto'):
            objects = self.clips.clip_rect(objects, ctm, 0, 0, width, height)
        return objects

    # -------------------------------------------------------------- shapes

    def shape(self, node, ctm, style, vp):
        if style['visibility'] in ('hidden', 'collapse'):
            return []
        self.current_vp = vp
        tag = node.tag
        fs = style['font-size']
        def length(name, ref, default = 0.0):
            return values.length(node.get(name), ref, fs, default)
        diag = math.hypot(vp[0], vp[1]) / math.sqrt(2)
        if tag == 'rect':
            x = length('x', vp[0]); y = length('y', vp[1])
            w = length('width', vp[0]); h = length('height', vp[1])
            if w <= 0 or h <= 0:
                return []
            rx = length('rx', vp[0], None)
            ry = length('ry', vp[1], None)
            if rx is None or rx < 0:
                rx = ry if ry is not None and ry >= 0 else 0.0
            if ry is None or ry < 0:
                ry = rx
            rx = min(rx, w / 2); ry = min(ry, h / 2)
            return self.rectangle(node, ctm, style, x, y, w, h, rx, ry)
        if tag in ('circle', 'ellipse'):
            cx = length('cx', vp[0]); cy = length('cy', vp[1])
            if tag == 'circle':
                rx = ry = length('r', diag)
            else:
                rx = length('rx', vp[0], None)
                ry = length('ry', vp[1], None)
                if rx is None or node.get('rx') == 'auto':
                    rx = ry
                if ry is None or node.get('ry') == 'auto':
                    ry = rx
            if not rx or not ry or rx <= 0 or ry <= 0:
                return []
            return self.ellipse(node, ctm, style, cx, cy, rx, ry)
        if tag == 'line':
            sub = pathdata.SubPath(length('x1', vp[0]), length('y1', vp[1]))
            sub.segments.append(('L', length('x2', vp[0]),
                                 length('y2', vp[1])))
            subpaths = [sub]
        elif tag in ('polyline', 'polygon'):
            subpaths = pathdata.polyline(node.get('points'),
                                         tag == 'polygon')
        else:
            subpaths = pathdata.parse(node.get('d'))
        if not subpaths:
            return []
        return self.path(node, ctm, style, subpaths, fill = tag != 'line')

    def rectangle(self, node, ctm, style, x, y, w, h, rx, ry):
        m = mul(ctm, (w, 0.0, 0.0, h, x, y))
        if values.det(m) < 0:
            m = mul(m, (1.0, 0.0, 0.0, -1.0, 0.0, 1.0))
        if abs(values.det(m)) < 1e-12:
            return []
        r1 = rx / w if rx > 0 and ry > 0 else 0
        r2 = ry / h if rx > 0 and ry > 0 else 0
        def make(properties):
            return Rectangle(Trafo(*m), radius1 = r1, radius2 = r2,
                             properties = properties)
        return self.finish_shape(node, ctm, style, make,
                                 user_box = (x, y, x + w, y + h))

    def ellipse(self, node, ctm, style, cx, cy, rx, ry):
        m = mul(ctm, (rx, 0.0, 0.0, ry, cx, cy))
        if values.det(m) < 0:
            m = mul(m, (1.0, 0.0, 0.0, -1.0, 0.0, 0.0))
        if abs(values.det(m)) < 1e-12:
            return []
        def make(properties):
            return Ellipse(Trafo(*m), properties = properties)
        return self.finish_shape(node, ctm, style, make,
                                 user_box = (cx - rx, cy - ry,
                                             cx + rx, cy + ry))

    def path(self, node, ctm, style, subpaths, fill = 1):
        """Objects for the SUBPATHS (user space) of NODE."""
        doc = [sub.transformed(ctm) for sub in subpaths]
        dots = [sub for sub in doc if not sub.segments or sub.is_degenerate()]
        doc = [sub for sub in doc if sub.segments and not sub.is_degenerate()]
        if self.clips.clip_mode:
            # a child of a clip path: only the geometry matters
            if not doc:
                return []
            from .clip import empty_properties
            return [PolyBezier(paths = tuple(make_path(sub) for sub in doc),
                               properties = empty_properties())]
        objects = []
        if doc:
            user_box = pathdata.bbox(subpaths)
            fill_paths = stroke_paths = doc
            filled = fill and self.has_paint(style, 'fill')
            if filled and len(doc) > 1:
                rule = style['fill-rule']
                fill_paths = self.fillrule.even_odd_equivalent(
                    doc, rule, self.warn)
                if len(fill_paths) == len(doc):
                    fill_paths = doc
                elif not self.has_paint(style, 'stroke'):
                    # the dropped subpaths are not needed for a line
                    doc = stroke_paths = fill_paths
            def make(properties, paths = None):
                paths = tuple(make_path(sub) for sub in (paths or doc))
                obj = PolyBezier(paths = paths, properties = properties)
                obj.guess_continuity()
                return obj
            if fill_paths is stroke_paths:
                objects = self.finish_shape(node, ctm, style, make,
                                            fill = fill, user_box = user_box)
            else:
                # the stroke needs the original subpaths
                objects = self.finish_shape(
                    node, ctm, style,
                    lambda props: make(props, fill_paths), fill = fill,
                    stroke = 0, user_box = user_box) \
                    + self.finish_shape(node, ctm, style, make, fill = 0,
                                        user_box = user_box)
                if len(objects) > 1:
                    objects = [Group(objects)]
        if dots:
            objects = objects + self.dots(style, ctm, dots)
        objects = self.markers.apply(node, objects, ctm, style, subpaths)
        return objects

    def dots(self, style, ctm, dots):
        """Zero-length subpaths: drawn by round and square caps."""
        cap = style['stroke-linecap']
        if cap not in ('round', 'square') or not self.has_paint(style,
                                                                'stroke'):
            return []
        width = self.line_width(style, ctm)
        if width <= 0:
            return []
        color = self.solid_color(style, 'stroke')
        if color is None:
            return []
        objects = []
        props = self.properties(fill = paint.solid(color),
                                line = EmptyPattern)
        r = width / 2
        for sub in dots:
            x, y = sub.start
            if cap == 'round':
                obj = Ellipse(Trafo(r, 0, 0, r, x, y),
                              properties = props.Duplicate())
            else:
                obj = Rectangle(Trafo(width, 0, 0, width, x - r, y - r),
                                properties = props.Duplicate())
            objects.append(obj)
        return objects

    # ---------------------------------------------------------- properties

    def properties(self, **kw):
        base = factory_defaults.Copy()
        for key, value in kw.items():
            setattr(base, key + '_pattern' if key in ('fill', 'line')
                    else key, value)
        return PropertyStack(base = base)

    def opacity(self, style, which):
        alpha = tree.number(style[which + '-opacity'], 1.0)
        return min(max(alpha, 0.0), 1.0) * style['_opacity']

    def has_paint(self, style, which):
        value = values.paint(style[which])
        return value not in (None, 'invalid') \
               and self.opacity(style, which) > paint.MIN_ALPHA

    def resolve_paint(self, style, which):
        """The paint of STYLE for WHICH ('fill' or 'stroke'): None, a
        color tuple (r, g, b, a) or a gradient/pattern Node."""
        value = values.paint(style[which])
        if value == 'invalid':
            # an invalid value is ignored: the default (fill black,
            # stroke none)
            value = values.paint(tree.INHERITED[which])
        if value == 'currentColor':
            value = paint.current_color(style)
        if isinstance(value, tuple) and value[0] == 'url':
            ref = self.lookup(value[1])
            if ref is not None and ref.tag in ('linearGradient',
                                               'radialGradient', 'pattern'):
                return ref
            value = value[2]
            if value == 'currentColor':
                value = paint.current_color(style)
            if value is None or value == 'invalid':
                return None
        return value

    def solid_color(self, style, which):
        """A solid color (r, g, b) for WHICH, opacity blended, or None
        for no paint.  Paint servers give their mean color."""
        value = self.resolve_paint(style, which)
        if value is None:
            return None
        if not isinstance(value, tuple):
            value = self.gradients.mean_color(value, style)
            if value is None:
                return None
        alpha = value[3] * self.opacity(style, which)
        if alpha <= paint.MIN_ALPHA:
            return None
        return paint.blend(value, alpha, self.background)

    def line_width(self, style, ctm):
        width = values.length(style['stroke-width'], 0.0, style['font-size'])
        if width is None:
            width = 1.0
        if style['vector-effect'] == 'non-scaling-stroke':
            width = width * self.root_scale
        else:
            width = width * values.mean_scale(ctm)
        # avoid 1.9999999999 in the line width dialog
        return round(width, 6)

    def line_properties(self, style, ctm):
        """The Sketch line properties as a dict, or None for no stroke."""
        color = self.solid_color(style, 'stroke')
        if color is None:
            return None
        if not isinstance(self.resolve_paint(style, 'stroke'), tuple):
            self.warn(_("Gradient or pattern strokes drawn in a solid "
                        "color"))
        width = self.line_width(style, ctm)
        if width <= 0:
            return None
        if style['vector-effect'] != 'non-scaling-stroke' \
           and values.anisotropy(ctm) > 1.05:
            self.warn(_("Line widths of non-uniformly scaled objects "
                        "approximated"))
        cap = paint.CAPS.get(style['stroke-linecap'], const.CapButt)
        join = paint.JOINS.get(style['stroke-linejoin'], const.JoinMiter)
        if join == const.JoinMiter \
           and tree.number(style['stroke-miterlimit'], 4.0) < 2.0:
            join = const.JoinBevel
        scale = values.mean_scale(ctm) \
                if style['vector-effect'] != 'non-scaling-stroke' \
                else self.root_scale
        return dict(line_pattern = paint.solid(color), line_width = width,
                    line_cap = cap, line_join = join,
                    line_dashes = paint.dashes(style, width, scale, cap))

    def finish_shape(self, node, ctm, style, make, fill = 1, stroke = 1,
                     user_box = None):
        """Create the object(s) with MAKE(properties).  USER_BOX is the
        geometric bounding box in user space (for paint servers)."""
        base = factory_defaults.Copy()
        base.fill_pattern = EmptyPattern
        fill_value = None
        if fill:
            fill_value = self.resolve_paint(style, 'fill')
            if isinstance(fill_value, tuple):
                alpha = fill_value[3] * self.opacity(style, 'fill')
                if alpha > paint.MIN_ALPHA:
                    base.fill_pattern = paint.solid(paint.blend(
                        fill_value, alpha, self.background))
                    if alpha < 1:
                        self.note_opacity()
                fill_value = None
        line = stroke and self.line_properties(style, ctm)
        if line:
            for key, value in line.items():
                setattr(base, key, value)
            if self.opacity(style, 'stroke') < 1:
                self.note_opacity()
        else:
            base.line_pattern = EmptyPattern
        order = style['paint-order'].split()
        if line and order and order[0] == 'stroke' \
           and (fill_value is not None
                or base.fill_pattern is not EmptyPattern):
            # the stroke below the fill: two objects
            fill_style = base.Copy()
            fill_style.line_pattern = EmptyPattern
            base.fill_pattern = EmptyPattern
            below = make(PropertyStack(base = base))
            above = [make(PropertyStack(base = fill_style))]
            if fill_value is not None:
                above = self.gradients.apply(above[0], fill_value, style,
                                             ctm, user_box)
            return [Group([below] + above)]
        obj = make(PropertyStack(base = base))
        if fill_value is not None:
            return self.gradients.apply(obj, fill_value, style, ctm,
                                        user_box)
        return [obj]

    def note_opacity(self):
        if self.background is paint.WHITE:
            self.warn(_("Transparent colors blended with white"))


def _point(x, y):
    from Sketch import Point
    return Point(x, y)
