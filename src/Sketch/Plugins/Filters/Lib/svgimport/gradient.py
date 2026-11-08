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
# SVG import: gradients and patterns.
#
# Sketch's gradients are defined relative to the bounding rect of the
# object (see Graphics/pattern.py):
#
# - LinearGradient(gradient, direction, border): position 0 at
#   center + direction * L/2, position 1 at center - direction * L/2,
#   with L the extent of the rect along the direction times (1 - border);
#   padded beyond.
# - RadialGradient(gradient, center, border): a circle around CENTER
#   (relative to the rect), position 0 at the radius R (the distance to
#   the farthest corner times (1 - border)), 1 at the center.
#
# An SVG linear gradient stays linear under any affine transformation,
# so it maps exactly: the direction is the gradient's direction in
# document space, and the SVG gradient (with its spread method) is
# sampled at the positions where the stops fall within the object's
# extent.  Radial gradients are exact when their circle stays a circle
# and the focus is the center.
#
# Patterns: a single image filling the tile becomes an ImageTilePattern,
# the hatching of Sketch's own SVG export a HatchingPattern; other
# patterns are drawn as copies of the tile clipped by the object.

import math

from Sketch import _, Point, Trafo, MultiGradient, LinearGradient, \
     RadialGradient, HatchingPattern, ImageTilePattern, Group, MaskGroup, \
     EmptyPattern, ImageData

from . import values, paint, tree
from .values import mul

# the maximal number of repeats of reflect/repeat gradients and of
# pattern tiles drawn as copies
MAX_PERIODS = 200
MAX_TILES = 2000

GRADIENT_ATTRS = ('gradientUnits', 'gradientTransform', 'spreadMethod',
                  'x1', 'y1', 'x2', 'y2', 'cx', 'cy', 'r', 'fx', 'fy', 'fr')
PATTERN_ATTRS = ('patternUnits', 'patternContentUnits', 'patternTransform',
                 'x', 'y', 'width', 'height', 'viewBox',
                 'preserveAspectRatio')


class Server:

    """A paint server with its inherited attributes and children
    (xlink:href chains)."""

    def __init__(self, builder, node, names):
        self.node = node
        self.attrs = {}
        self.content = None     # the node whose children are used
        seen = []
        while node is not None and node not in seen:
            seen.append(node)
            for name in names:
                if name not in self.attrs and node.get(name) is not None:
                    self.attrs[name] = node.get(name)
            if self.content is None and node.children and \
               (node.tag == 'pattern' or
                any(child.tag == 'stop' for child in node.children)):
                self.content = node
            node = builder.lookup(values.href_id(node.href()))
            if node is not None and node.tag not in ('linearGradient',
                                                     'radialGradient',
                                                     'pattern'):
                break

    def get(self, name, default = None):
        return self.attrs.get(name, default)


def gradient_stops(builder, server):
    """The stops of a gradient: a list of (offset, (r, g, b, alpha))
    with increasing offsets."""
    stops = []
    if server.content is None:
        return stops
    last = 0.0
    for node in server.content.children:
        if node.tag != 'stop':
            continue
        style = builder.tree_style(node)
        offset = tree.number(node.get('offset', '0'), 0.0)
        offset = min(max(offset, last), 1.0)
        last = offset
        color = values.color(style['stop-color'])
        if color == 'currentColor':
            color = paint.current_color(style)
        if color is None:
            color = (0.0, 0.0, 0.0, 1.0)
        alpha = color[3] * min(max(tree.number(style['stop-opacity'], 1.0),
                                   0.0), 1.0)
        stops.append((offset, color[:3] + (alpha,)))
    return stops


def stop_color(stops, s):
    """The color of the (padded) gradient STOPS at position S."""
    if s <= stops[0][0]:
        return stops[0][1]
    for i in range(1, len(stops)):
        o2, c2 = stops[i]
        if s <= o2:
            o1, c1 = stops[i - 1]
            if o2 <= o1:
                return c2
            f = (s - o1) / (o2 - o1)
            return tuple(a + (b - a) * f for a, b in zip(c1, c2))
    return stops[-1][1]


def spread_positions(stops, spread, s0, s1):
    """The positions in [S0, S1] where the color of the gradient with
    STOPS and SPREAD method changes slope: the ends and the stops of
    all periods."""
    lo, hi = min(s0, s1), max(s0, s1)
    positions = [lo, hi]
    offsets = [o for o, c in stops]
    if spread in ('repeat', 'reflect'):
        first = int(math.floor(lo))
        last = int(math.ceil(hi))
        if last - first > MAX_PERIODS:
            last = first + MAX_PERIODS
        for n in range(first, last + 1):
            for o in offsets:
                if spread == 'reflect' and n % 2:
                    o = 1 - o
                positions.append(n + o)
    else:
        positions.extend(offsets)
    return sorted(set(p for p in positions if lo <= p <= hi))


def spread_color(stops, spread, s, left = False):
    """The color at S; LEFT asks for the limit from below (the end of a
    period of a repeating gradient)."""
    if spread == 'repeat':
        n = math.floor(s)
        s = s - n
        if left and s == 0:
            s = 1.0
    elif spread == 'reflect':
        n = math.floor(s)
        s = s - n
        if int(n) % 2:
            s = 1 - s
    return stop_color(stops, s)


def multigradient(builder, stops, spread, s_at_0, s_at_1, alpha):
    """A MultiGradient for Sketch positions 0..1 that correspond to the
    SVG gradient positions S_AT_0..S_AT_1.  ALPHA is the opacity of the
    painted element; colors are blended toward white."""
    # rounding avoids period boundaries just inside the range
    s_at_0 = round(s_at_0, 9)
    s_at_1 = round(s_at_1, 9)
    positions = spread_positions(stops, spread, s_at_0, s_at_1)
    if s_at_1 < s_at_0:
        positions.reverse()
    span = s_at_1 - s_at_0
    colors = []
    last_t = -1.0
    transparent = False
    increasing = s_at_1 >= s_at_0
    for s in positions:
        t = (s - s_at_0) / span if span else 0.0
        t = min(max(t, 0.0), 1.0)
        # at the upper end of the range: the limit from inside
        samples = [spread_color(stops, spread, s,
                                left = s == max(s_at_0, s_at_1))]
        if spread == 'repeat' and s == math.floor(s) \
           and min(s_at_0, s_at_1) < s < max(s_at_0, s_at_1):
            # a period boundary: the end color, then the start color
            # (in the direction of increasing t)
            end = spread_color(stops, spread, s, left = True)
            samples = [end, samples[0]] if increasing else [samples[0], end]
        for rgba in samples:
            a = rgba[3] * alpha
            if a < 1:
                transparent = True
            color = paint.rgb_color(*paint.blend(rgba, a,
                                                 builder.background))
            if t <= last_t:
                # Sketch's gradients do not allow equal positions
                t = last_t + 1e-6
            colors.append((t, color))
            last_t = t
    if transparent:
        builder.note_opacity()
    # exact ends, increasing positions
    colors[0] = (0.0, colors[0][1])
    if colors[-1][0] >= 1.0 or len(colors) == 1:
        colors[-1] = (1.0, colors[-1][1])
    else:
        colors.append((1.0, colors[-1][1]))
    for i in range(len(colors) - 2, 0, -1):
        if colors[i][0] >= colors[i + 1][0]:
            del colors[i]
    if len(colors) < 2:
        colors = [(0.0, colors[0][1]), (1.0, colors[0][1])]
    return MultiGradient(colors)


class Gradients:

    def __init__(self, builder):
        self.builder = builder

    def mean_color(self, node, style):
        """A solid color standing in for the paint server NODE: the
        color in the middle of a gradient, the mean color of a pattern
        image or its first solid fill."""
        b = self.builder
        if node.tag == 'pattern':
            server = Server(b, node, PATTERN_ATTRS)
            content = server.content
            if content is None:
                return None
            for child in content.iter():
                if child.tag == 'image':
                    try:
                        from .image import open_href, pil_image
                        data, mime = open_href(child.href(), b.base_dir)
                        image = pil_image(data).convert('RGBA')
                        r, g, bl, a = image.resize((1, 1)).getpixel((0, 0))
                        return (r / 255., g / 255., bl / 255., a / 255.)
                    except Exception:
                        continue
                if child.tag in ('rect', 'path', 'circle', 'ellipse',
                                 'polygon'):
                    value = b.resolve_paint(b.tree_style(child), 'fill')
                    if isinstance(value, tuple):
                        return value
            return None
        server = Server(b, node, GRADIENT_ATTRS)
        stops = gradient_stops(b, server)
        if not stops:
            return None
        return stop_color(stops, 0.5)

    def apply(self, obj, node, style, ctm, user_box):
        """Fill OBJ with the paint server NODE.  USER_BOX is the
        geometric bounding box of the element in its user space.
        Returns the list of objects replacing OBJ."""
        b = self.builder
        if node.tag == 'pattern':
            return self.pattern(obj, node, style, ctm, user_box)
        server = Server(b, node, GRADIENT_ATTRS)
        stops = gradient_stops(b, server)
        alpha = b.opacity(style, 'fill')
        if not stops:
            # no stops: no paint
            return [obj]
        if len(stops) == 1:
            return [self.solid(obj, stops[0][1], alpha)]
        m = values.parse_transform(server.get('gradientTransform'))
        if m is None:
            m = values.IDENTITY
        bbox_units = server.get('gradientUnits') != 'userSpaceOnUse'
        if bbox_units:
            if user_box is None:
                return [self.solid(obj, stop_color(stops, 0.5), alpha)]
            l, bt, r, t = user_box
            if r - l <= 0 or t - bt <= 0:
                # a bounding box without area: the paint is not drawn
                return [self.solid(obj, None, alpha)]
            m = mul((r - l, 0.0, 0.0, t - bt, l, bt), m)
            vp = (1.0, 1.0)
            fs = style['font-size']
        else:
            vp = b.current_vp
            fs = style['font-size']
        M = mul(ctm, m)
        spread = server.get('spreadMethod', 'pad')
        def length(name, ref, default):
            value = server.get(name)
            if value is None:
                return default
            if bbox_units and not value.strip().endswith('%'):
                return tree.number(value, default)
            return values.length(value, ref, fs, default)
        rect = obj.bounding_rect
        if node.tag == 'linearGradient':
            x1 = length('x1', vp[0], 0.0)
            y1 = length('y1', vp[1], 0.0)
            x2 = length('x2', vp[0], vp[0] if bbox_units else
                        values.length('100%', vp[0]))
            y2 = length('y2', vp[1], 0.0)
            pattern = self.linear(stops, spread, M, x1, y1, x2, y2, rect,
                                  alpha)
        else:
            diag = math.hypot(vp[0], vp[1]) / math.sqrt(2)
            cx = length('cx', vp[0], 0.5 * vp[0])
            cy = length('cy', vp[1], 0.5 * vp[1])
            r = length('r', diag, 0.5 * diag)
            fx = length('fx', vp[0], cx)
            fy = length('fy', vp[1], cy)
            pattern = self.radial(stops, spread, M, cx, cy, r, fx, fy, rect,
                                  alpha)
        if pattern is None:
            return [self.solid(obj, stops[-1][1], alpha)]
        obj.SetProperties(fill_pattern = pattern, fill_transform = 1)
        return [obj]

    def solid(self, obj, rgba, alpha):
        if rgba is None or rgba[3] * alpha <= paint.MIN_ALPHA:
            obj.SetProperties(fill_pattern = EmptyPattern)
        else:
            obj.SetProperties(fill_pattern = paint.solid(
                paint.blend(rgba, rgba[3] * alpha,
                            self.builder.background)))
        return obj

    def linear(self, stops, spread, M, x1, y1, x2, y2, rect, alpha):
        vx = x2 - x1; vy = y2 - y1
        n2 = vx * vx + vy * vy
        if n2 == 0:
            return None
        inv = values.inverse(M)
        if inv is None:
            return None
        # s(p) = ((M^-1 p - p1) . v) / |v|^2 is affine in p: its
        # gradient g in document space
        a, bb, c, d = inv[:4]
        gx = (a * vx + bb * vy) / n2
        gy = (c * vx + d * vy) / n2
        g = math.hypot(gx, gy)
        if g == 0:
            return None
        def s_at(px, py):
            qx, qy = values.apply(inv, px, py)
            return ((qx - x1) * vx + (qy - y1) * vy) / n2
        dirx, diry = -gx / g, -gy / g
        cx = (rect.left + rect.right) / 2
        cy = (rect.bottom + rect.top) / 2
        # the extent of the rect along the direction (border 0)
        extent = (rect.right - rect.left) * abs(dirx) \
                 + (rect.top - rect.bottom) * abs(diry)
        sc = s_at(cx, cy)
        s0 = sc - g * extent / 2
        s1 = sc + g * extent / 2
        gradient = multigradient(self.builder, stops, spread, s0, s1, alpha)
        return LinearGradient(gradient, Point(dirx, diry), 0)

    def radial(self, stops, spread, M, cx, cy, r, fx, fy, rect, alpha):
        if r <= 0:
            return None
        b = self.builder
        if abs(fx - cx) > 1e-6 * r or abs(fy - cy) > 1e-6 * r:
            b.warn(_("Focal points of radial gradients ignored"))
        a, bb, c, d = M[:4]
        # a circle stays a circle under a similarity
        if abs(math.hypot(a, bb) - math.hypot(c, d)) \
           > 1e-3 * math.hypot(a, bb) or abs(a * c + bb * d) \
           > 1e-3 * (a * a + bb * bb):
            b.warn(_("Elliptical radial gradients approximated"))
        k = values.mean_scale(M)
        rho = r * k
        Cx, Cy = values.apply(M, cx, cy)
        w = rect.right - rect.left
        h = rect.top - rect.bottom
        if w <= 0 or h <= 0 or rho <= 0:
            return None
        R = max(math.hypot(x - Cx, y - Cy) for x in (rect.left, rect.right)
                for y in (rect.bottom, rect.top))
        if R <= 0:
            return None
        # Sketch position t <-> distance (1 - t) R <-> SVG s = (1-t) R/rho
        gradient = multigradient(b, stops, spread, R / rho, 0.0, alpha)
        center = Point((Cx - rect.left) / w, (Cy - rect.bottom) / h)
        return RadialGradient(gradient, center, 0)

    # ------------------------------------------------------------ patterns

    def pattern(self, obj, node, style, ctm, user_box):
        b = self.builder
        server = Server(b, node, PATTERN_ATTRS)
        if server.content is None:
            obj.SetProperties(fill_pattern = EmptyPattern)
            return [obj]
        fs = style['font-size']
        vp = b.current_vp
        bbox_units = server.get('patternUnits') != 'userSpaceOnUse'
        def length(name, ref):
            value = server.get(name)
            if value is None:
                return 0.0
            if bbox_units and not value.strip().endswith('%'):
                return tree.number(value, 0.0)
            return values.length(value, ref, fs, 0.0)
        if bbox_units:
            x, y, w, h = [length(n, 1.0) for n in ('x', 'y', 'width',
                                                    'height')]
            if user_box is None:
                return [obj]
            l, bt, r, t = user_box
            bw, bh = r - l, t - bt
            x = l + x * bw; y = bt + y * bh; w = w * bw; h = h * bh
        else:
            x = length('x', vp[0]); y = length('y', vp[1])
            w = length('width', vp[0]); h = length('height', vp[1])
        if w <= 0 or h <= 0:
            obj.SetProperties(fill_pattern = EmptyPattern)
            return [obj]
        m = values.parse_transform(server.get('patternTransform')) \
            or values.IDENTITY
        tile = mul(ctm, mul(m, values.translate(x, y)))
        # the content's coordinates within the tile
        from .builder import parse_viewbox, viewbox_transform
        viewbox = parse_viewbox(server.get('viewBox'))
        if viewbox:
            content = viewbox_transform(viewbox,
                                        server.get('preserveAspectRatio'),
                                        w, h)
        elif server.get('patternContentUnits') == 'objectBoundingBox' \
             and user_box is not None:
            l, bt, r, t = user_box
            content = (r - l, 0.0, 0.0, t - bt, 0.0, 0.0)
        else:
            content = values.IDENTITY
        children = [c for c in server.content.children
                    if c.tag not in ('title', 'desc', 'metadata')]
        hatch = self.hatching(server, children, tile, w, h)
        if hatch is not None:
            obj.SetProperties(fill_pattern = hatch, fill_transform = 1)
            return [obj]
        tiled = self.image_tile(server, children, tile, content, w, h, obj)
        if tiled is not None:
            obj.SetProperties(fill_pattern = tiled, fill_transform = 1)
            return [obj]
        return self.tile_copies(obj, server, style, tile, content, w, h)

    def hatching(self, server, children, tile, w, h):
        """Sketch's own hatching (svgsaver): a background rect and a
        horizontal line rect across the tile."""
        if len(children) != 2 or w != h \
           or not (server.node.get('id') or '').startswith('hatch') \
           or any(c.tag != 'rect' for c in children):
            return None
        b = self.builder
        bg, line = children
        width = tree.number(line.get('height'), 0.0)
        fg_color = b.resolve_paint(b.tree_style(line), 'fill')
        bg_color = b.resolve_paint(b.tree_style(bg), 'fill')
        if not (isinstance(fg_color, tuple) and isinstance(bg_color, tuple)):
            return None
        a, bb, c, d = tile[:4]
        scale = values.mean_scale(tile)
        direction = Point(a, bb).normalized()
        return HatchingPattern(paint.rgb_color(*fg_color[:3]),
                               paint.rgb_color(*bg_color[:3]),
                               direction, w * scale, width * scale)

    def image_tile(self, server, children, tile, content, w, h, obj):
        """A single image filling the whole tile: an ImageTilePattern."""
        if len(children) != 1 or children[0].tag != 'image':
            return None
        b = self.builder
        node = children[0]
        from .image import open_href, pil_image, image_trafo
        try:
            data, mime = open_href(node.href(), b.base_dir)
            image = pil_image(data)
        except Exception:
            return None
        iw, ih = image.size
        fs = 16.0
        ix = values.length(node.get('x'), w, fs, 0.0)
        iy = values.length(node.get('y'), h, fs, 0.0)
        width = values.length(node.get('width'), w, fs, float(iw))
        height = values.length(node.get('height'), h, fs, float(ih))
        m = values.parse_transform(node.get('transform')) or values.IDENTITY
        # the image must cover the tile exactly
        corners = [values.apply(mul(content, m), px, py)
                   for px, py in ((ix, iy), (ix + width, iy + height))]
        if abs(corners[0][0]) > 1e-6 * w or abs(corners[0][1]) > 1e-6 * h \
           or abs(corners[1][0] - w) > 1e-6 * w \
           or abs(corners[1][1] - h) > 1e-6 * h:
            return None
        if image.mode == 'RGBA':
            b.warn(_("Transparency of pattern images ignored"))
        # pixel (col, row) -> document
        pix = mul(tile, mul(content, mul(m, (width / iw, 0.0, 0.0,
                                             height / ih, ix, iy))))
        rect = obj.bounding_rect
        pix = mul(values.translate(-rect.left, -rect.top), pix)
        return ImageTilePattern(ImageData(image), Trafo(*pix))

    def tile_copies(self, obj, server, style, tile, content, w, h):
        """Copies of the tile, clipped by the object, below its line."""
        b = self.builder
        inv = values.inverse(tile)
        if inv is None:
            return [obj]
        r = obj.coord_rect
        pts = [values.apply(inv, px, py) for px in (r.left, r.right)
               for py in (r.bottom, r.top)]
        eps = 1e-6
        i0 = int(math.floor(min(p[0] for p in pts) / w + eps))
        i1 = int(math.ceil(max(p[0] for p in pts) / w - eps))
        j0 = int(math.floor(min(p[1] for p in pts) / h + eps))
        j1 = int(math.ceil(max(p[1] for p in pts) / h - eps))
        if (i1 - i0) * (j1 - j0) > MAX_TILES:
            b.warn(_("Fine patterns drawn in a solid color"))
            color = self.mean_color(server.node, style)
            return [self.solid(obj, color, b.opacity(style, 'fill'))]
        pstyle = b.tree_style(server.content)
        pstyle = dict(pstyle, _opacity = pstyle['_opacity']
                      * b.opacity(style, 'fill'))
        clip_tiles = pstyle['overflow'] in ('hidden', 'scroll', 'auto')
        tiles = []
        b.use_stack.append(server.node)
        try:
            for i in range(i0, i1):
                for j in range(j0, j1):
                    m = mul(tile, values.translate(i * w, j * h))
                    objects = b.children(server.content, mul(m, content),
                                         pstyle, (w, h))
                    if clip_tiles and objects:
                        objects = b.clips.clip_rect(objects, m, 0, 0, w, h)
                    tiles.extend(objects)
        finally:
            b.use_stack.pop()
        if not tiles:
            obj.SetProperties(fill_pattern = EmptyPattern)
            return [obj]
        from .clip import empty_properties
        mask = obj.Duplicate()
        mask.SetProperties(fill_pattern = EmptyPattern,
                           line_pattern = EmptyPattern)
        obj.SetProperties(fill_pattern = EmptyPattern)
        clipped = b.clips.clip([Group(tiles)] if len(tiles) > 1 else tiles,
                               mask)
        if obj.Properties().HasLine():
            return [Group(clipped + [obj])]
        return clipped
