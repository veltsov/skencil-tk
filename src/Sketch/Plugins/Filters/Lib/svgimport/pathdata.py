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

# SVG import: path data.
#
# parse() turns the `d' attribute (or the points of polyline/polygon)
# into a list of subpaths in user space.  A subpath is a SubPath
# with a start point and a list of segments, each ('L', x, y) or
# ('C', x1, y1, x2, y2, x, y): quadratic béziers and elliptical arcs
# are converted to cubics.  Errors end the parsing at the last valid
# command, as the SVG specification requires.

import math
import re

class SubPath:

    def __init__(self, x, y):
        self.start = (x, y)
        self.segments = []
        self.closed = False

    def end(self):
        if self.segments:
            return self.segments[-1][-2:]
        return self.start

    def transformed(self, m):
        a, b, c, d, e, f = m
        def t(x, y):
            return (a * x + c * y + e, b * x + d * y + f)
        result = SubPath(*t(*self.start))
        for seg in self.segments:
            if seg[0] == 'L':
                result.segments.append(('L',) + t(seg[1], seg[2]))
            else:
                result.segments.append(('C',) + t(seg[1], seg[2])
                                       + t(seg[3], seg[4]) + t(seg[5], seg[6]))
        result.closed = self.closed
        return result

    def points(self):
        """Start, all control points and end points (for bounding
        boxes; a superset of the curve's hull)."""
        pts = [self.start]
        for seg in self.segments:
            for i in range(1, len(seg), 2):
                pts.append((seg[i], seg[i + 1]))
        return pts

    def is_degenerate(self):
        x0, y0 = self.start
        for x, y in self.points():
            if x != x0 or y != y0:
                return False
        return True


rx_token = re.compile(r'\s*,?\s*(?:([MmZzLlHhVvCcSsQqTtAa])|'
                      r'([-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?))')
rx_flag = re.compile(r'\s*,?\s*([01])')

ARGS = {'M': 2, 'L': 2, 'H': 1, 'V': 1, 'C': 6, 'S': 4, 'Q': 4, 'T': 2,
        'A': 7, 'Z': 0}


def tokenize(d):
    """Yield commands (str) and arguments (float).  The flags of arcs
    may be written without separators (`a1 1 0 001 1'), so the arc
    arguments are read separately."""
    pos = 0
    n = len(d)
    command = None
    index = 0
    while pos < n:
        if command and command in 'Aa' and index % 7 in (3, 4):
            match = rx_flag.match(d, pos)
            if not match:
                return
            pos = match.end()
            index += 1
            yield float(match.group(1))
            continue
        match = rx_token.match(d, pos)
        if not match:
            return
        pos = match.end()
        if match.group(1):
            command = match.group(1)
            index = 0
            yield command
        else:
            index += 1
            yield float(match.group(2))


def parse(d):
    tokens = list(tokenize(d or ''))
    paths = []
    current = None
    x = y = 0.0
    start = (0.0, 0.0)
    last_cubic = last_quad = None   # reflected control point candidates
    i = 0
    n = len(tokens)
    command = None
    while i < n:
        tok = tokens[i]
        if isinstance(tok, str):
            command = tok
            i += 1
            if command in 'Zz':
                if current is not None:
                    current.closed = True
                    x, y = start
                    current = None
                last_cubic = last_quad = None
                continue
        elif command is None or command in 'Zz':
            # numbers after Z (or before any command) are an error
            break
        upper = command.upper()
        count = ARGS[upper]
        args = tokens[i:i + count]
        if len(args) < count or any(isinstance(a, str) for a in args):
            break
        i += count
        rel = command.islower()
        if current is None and upper != 'M':
            # a drawing command after Z (or at the start): continue
            # from the current point
            current = SubPath(x, y)
            start = (x, y)
            paths.append(current)
        if upper == 'M':
            if rel:
                x += args[0]; y += args[1]
            else:
                x, y = args
            current = SubPath(x, y)
            start = (x, y)
            paths.append(current)
            # further pairs are implicit linetos
            command = rel and 'l' or 'L'
            last_cubic = last_quad = None
            continue
        if upper in 'LHV':
            if upper == 'L':
                if rel:
                    x += args[0]; y += args[1]
                else:
                    x, y = args
            elif upper == 'H':
                x = x + args[0] if rel else args[0]
            else:
                y = y + args[0] if rel else args[0]
            current.segments.append(('L', x, y))
            last_cubic = last_quad = None
        elif upper in 'CS':
            if upper == 'C':
                x1, y1, x2, y2, ex, ey = args
                if rel:
                    x1 += x; y1 += y; x2 += x; y2 += y; ex += x; ey += y
            else:
                x2, y2, ex, ey = args
                if rel:
                    x2 += x; y2 += y; ex += x; ey += y
                if last_cubic:
                    x1 = 2 * x - last_cubic[0]; y1 = 2 * y - last_cubic[1]
                else:
                    x1, y1 = x, y
            current.segments.append(('C', x1, y1, x2, y2, ex, ey))
            last_cubic = (x2, y2); last_quad = None
            x, y = ex, ey
        elif upper in 'QT':
            if upper == 'Q':
                qx, qy, ex, ey = args
                if rel:
                    qx += x; qy += y; ex += x; ey += y
            else:
                ex, ey = args
                if rel:
                    ex += x; ey += y
                if last_quad:
                    qx = 2 * x - last_quad[0]; qy = 2 * y - last_quad[1]
                else:
                    qx, qy = x, y
            current.segments.append(('C', x + 2 * (qx - x) / 3,
                                     y + 2 * (qy - y) / 3,
                                     ex + 2 * (qx - ex) / 3,
                                     ey + 2 * (qy - ey) / 3, ex, ey))
            last_quad = (qx, qy); last_cubic = None
            x, y = ex, ey
        elif upper == 'A':
            rx, ry, phi, large, sweep, ex, ey = args
            if rel:
                ex += x; ey += y
            current.segments.extend(arc_segments(x, y, rx, ry, phi,
                                                 large, sweep, ex, ey))
            x, y = ex, ey
            last_cubic = last_quad = None
    return paths


def arc_segments(x1, y1, rx, ry, phi, large, sweep, x2, y2):
    """The elliptical arc (SVG endpoint parametrization) as segments
    (implementation notes of SVG 1.1, F.6)."""
    if x1 == x2 and y1 == y2:
        return []
    rx = abs(rx); ry = abs(ry)
    if rx == 0 or ry == 0:
        return [('L', x2, y2)]
    phi = math.radians(phi % 360)
    cos_phi = math.cos(phi); sin_phi = math.sin(phi)
    dx = (x1 - x2) / 2; dy = (y1 - y2) / 2
    x1p = cos_phi * dx + sin_phi * dy
    y1p = -sin_phi * dx + cos_phi * dy
    lam = (x1p / rx) ** 2 + (y1p / ry) ** 2
    if lam > 1:
        s = math.sqrt(lam)
        rx *= s; ry *= s
    num = rx * rx * ry * ry - rx * rx * y1p * y1p - ry * ry * x1p * x1p
    den = rx * rx * y1p * y1p + ry * ry * x1p * x1p
    coef = math.sqrt(max(num, 0) / den) if den else 0
    if bool(large) == bool(sweep):
        coef = -coef
    cxp = coef * rx * y1p / ry
    cyp = -coef * ry * x1p / rx
    cx = cos_phi * cxp - sin_phi * cyp + (x1 + x2) / 2
    cy = sin_phi * cxp + cos_phi * cyp + (y1 + y2) / 2
    def angle(ux, uy, vx, vy):
        return math.atan2(ux * vy - uy * vx, ux * vx + uy * vy)
    theta1 = angle(1, 0, (x1p - cxp) / rx, (y1p - cyp) / ry)
    dtheta = angle((x1p - cxp) / rx, (y1p - cyp) / ry,
                   (-x1p - cxp) / rx, (-y1p - cyp) / ry)
    if not sweep and dtheta > 0:
        dtheta -= 2 * math.pi
    elif sweep and dtheta < 0:
        dtheta += 2 * math.pi
    nseg = max(1, int(math.ceil(abs(dtheta) / (math.pi / 2) - 1e-9)))
    delta = dtheta / nseg
    k = 4.0 / 3.0 * math.tan(delta / 4)
    def point(t):
        ct = math.cos(t); st = math.sin(t)
        return (cx + rx * ct * cos_phi - ry * st * sin_phi,
                cy + rx * ct * sin_phi + ry * st * cos_phi)
    def deriv(t):
        ct = math.cos(t); st = math.sin(t)
        return (-rx * st * cos_phi - ry * ct * sin_phi,
                -rx * st * sin_phi + ry * ct * cos_phi)
    result = []
    t = theta1
    px, py = x1, y1
    for i in range(nseg):
        t2 = t + delta
        d1 = deriv(t); d2 = deriv(t2)
        if i == nseg - 1:
            qx, qy = x2, y2
        else:
            qx, qy = point(t2)
        result.append(('C', px + k * d1[0], py + k * d1[1],
                       qx - k * d2[0], qy - k * d2[1], qx, qy))
        px, py = qx, qy
        t = t2
    return result


def polyline(points, close):
    """The subpath of a polyline or polygon `points' attribute."""
    from .values import numbers
    values = numbers(points)
    if len(values) % 2:
        values = values[:-1]
    if len(values) < 2:
        return []
    path = SubPath(values[0], values[1])
    for i in range(2, len(values), 2):
        path.segments.append(('L', values[i], values[i + 1]))
    path.closed = close
    return [path]
