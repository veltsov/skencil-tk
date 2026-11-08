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

# SVG import: paint -- colors, opacity, line properties.
#
# Sketch has no opacity: a color with opacity alpha is blended toward
# white (exact over a white background).  Gradients and patterns are
# mapped in gradient.py.

import math

from Sketch import CreateRGBColor, SolidPattern, EmptyPattern
from Sketch.Base import const

from . import values

# below this opacity a paint is not drawn at all
MIN_ALPHA = 0.002

_colors = {}

def rgb_color(r, g, b):
    # share the color objects (and their solid patterns): Sketch
    # compares solid patterns by the identity of the color
    key = (round(r, 3), round(g, 3), round(b, 3))
    color = _colors.get(key)
    if color is None:
        color = _colors[key] = CreateRGBColor(*key)
    return color

_patterns = {}

def solid(rgb):
    key = (round(rgb[0], 3), round(rgb[1], 3), round(rgb[2], 3))
    pattern = _patterns.get(key)
    if pattern is None:
        pattern = _patterns[key] = SolidPattern(rgb_color(*key))
    return pattern

def blend(rgb, alpha):
    """RGB with opacity ALPHA over white."""
    if alpha >= 1.0:
        return tuple(rgb[:3])
    return tuple(c * alpha + 1.0 - alpha for c in rgb[:3])

def current_color(style):
    value = values.color(style.get('color'))
    if value is None or value == 'currentColor':
        return (0.0, 0.0, 0.0, 1.0)
    return value


CAPS = {'butt': const.CapButt, 'round': const.CapRound,
        'square': const.CapProjecting}
JOINS = {'miter': const.JoinMiter, 'miter-clip': const.JoinMiter,
         'round': const.JoinRound, 'arcs': const.JoinRound,
         'bevel': const.JoinBevel}


def dashes(style, width, scale, cap = const.CapButt):
    """The Sketch dash pattern (in units of max(width, 1)) of the
    stroke-dasharray and -offset of STYLE.  SCALE converts user units to
    points; WIDTH is the line width in points."""
    text = style.get('stroke-dasharray', 'none')
    if not text or text.strip() == 'none':
        return ()
    fs = style.get('font-size', 16.0)
    items = [values.length(item, 0.0, fs)
             for item in text.replace(',', ' ').split()]
    if not items or None in items or min(items) < 0 or sum(items) <= 0:
        return ()
    if len(items) % 2:
        items = items * 2
    items = [item * scale for item in items]
    offset = (values.length(style.get('stroke-dashoffset', '0'), 0.0, fs)
              or 0.0) * scale
    if offset:
        items = shift_dashes(items, offset, cap == const.CapButt)
    unit = max(width, 1.0)
    return tuple(item / unit for item in items)

def shift_dashes(items, offset, exact = True):
    """The dash pattern ITEMS (even length) started OFFSET into the
    pattern; Sketch has no dash offset.  A pattern starting inside a
    gap needs a zero-length dash in front, which round and square caps
    draw as a dot: unless EXACT, it then starts at the next dash
    instead (shifted by the rest of the gap)."""
    period = sum(items)
    offset = offset % period
    pos = 0.0
    for i, item in enumerate(items):
        if pos + item > offset:
            break
        pos += item
    head = pos + item - offset         # the rest of item i
    tail = offset - pos                # the beginning of item i
    if tail <= 0:
        if i % 2 == 0:
            return items[i:] + items[:i]
        # at the start of a gap: a zero dash in front, joined to the
        # last dash by a zero gap
        return [0.0] + items[i:] + items[:i] + [0.0]
    if i % 2 == 0:
        # inside a dash: the dash is split into a head and a tail
        # joined by a zero gap
        return [head] + items[i + 1:] + items[:i] + [tail, 0.0]
    if exact:
        return [0.0, head] + items[i + 1:] + items[:i] + [tail]
    return items[i + 1:] + items[:i] + [tail + head]
