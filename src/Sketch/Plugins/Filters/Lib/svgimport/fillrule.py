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

# SVG import: nonzero fills with Sketch's even-odd rule.
#
# Sketch fills curves with the even-odd rule only.  Most nonzero fills
# look the same under even-odd; they differ where a boundary separates
# two regions that are both filled (or both empty) under nonzero, e.g.
# a subpath nested in another one of the same orientation.  Such
# boundaries are dropped from the fill.  For subpaths that do not cross
# each other the result is exact; crossing ones are reported.
#
# The subpaths are flattened only for this analysis; the imported
# objects keep the original curves.

from Sketch import _

# line segments per bézier for the analysis
FLATTEN_STEPS = 8

def flatten(sub):
    pts = [sub.start]
    x0, y0 = sub.start
    for seg in sub.segments:
        if seg[0] == 'L':
            pts.append((seg[1], seg[2]))
            x0, y0 = seg[1], seg[2]
        else:
            x1, y1, x2, y2, x3, y3 = seg[1:]
            for i in range(1, FLATTEN_STEPS + 1):
                t = i / float(FLATTEN_STEPS)
                s = 1 - t
                a = s * s * s; b = 3 * s * s * t; c = 3 * s * t * t
                d = t * t * t
                pts.append((a * x0 + b * x1 + c * x2 + d * x3,
                            a * y0 + b * y1 + c * y2 + d * y3))
            x0, y0 = x3, y3
    return pts


class Polygon:

    def __init__(self, sub):
        self.pts = flatten(sub)
        xs = [p[0] for p in self.pts]
        ys = [p[1] for p in self.pts]
        self.box = (min(xs), min(ys), max(xs), max(ys))

    def crossings(self, y):
        """The crossings of the horizontal line at Y as (x, direction)."""
        result = []
        pts = self.pts
        n = len(pts)
        for i in range(n):
            x1, y1 = pts[i - 1]
            x2, y2 = pts[i]
            if (y1 <= y) != (y2 <= y):
                x = x1 + (y - y1) * (x2 - x1) / (y2 - y1)
                result.append((x, 1 if y2 > y1 else -1))
        return result

    def winding(self, x, y):
        if not (self.box[0] <= x <= self.box[2]
                and self.box[1] <= y <= self.box[3]):
            return 0
        w = 0
        for cx, d in self.crossings(y):
            if cx > x:
                w += d
        return w


def scanline(i, polygons):
    """The crossings of a horizontal line through the middle of polygon
    I: (y, own, all) with OWN the x of the crossings of polygon I and
    ALL those of all polygons, sorted.  None if I is degenerate."""
    poly = polygons[i]
    l, b, r, t = poly.box
    if t - b <= 0 or r - l <= 0:
        return None
    # an irrational fraction avoids running through vertices
    y = b + (t - b) * 0.5137
    own = sorted(x for x, d in poly.crossings(y))
    if len(own) < 2:
        return None
    others = sorted(x for p in polygons if p.box[1] <= y <= p.box[3]
                    for x, d in p.crossings(y))
    return y, own, others


def even_odd_equivalent(subpaths, rule, warn, groups = None):
    """The subset of SUBPATHS (document space SubPaths) whose even-odd
    fill equals the fill of SUBPATHS with RULE ('nonzero' or 'evenodd').

    GROUPS, if given, is a list of (subpaths, rule) whose union is to be
    filled (clip paths with several children); SUBPATHS and RULE are
    then ignored.

    A subpath is kept if, on a horizontal line through it, one of its
    crossings separates a filled from an empty region.  The even-odd
    fill of the kept subpaths is then checked in all intervals of these
    lines."""
    if groups is None:
        if rule != 'nonzero' or len(subpaths) < 2:
            return subpaths
        groups = [(subpaths, rule)]
    elif len(groups) == 1 and (groups[0][1] != 'nonzero'
                               or len(groups[0][0]) < 2):
        return groups[0][0]
    allsubs = []
    polys = []
    ranges = []
    for subs, r in groups:
        ranges.append((len(polys), len(polys) + len(subs), r))
        for sub in subs:
            allsubs.append(sub)
            polys.append(Polygon(sub))
    def inside(x, y):
        for s, e, r in ranges:
            w = 0
            for j in range(s, e):
                wj = polys[j].winding(x, y)
                w += wj if r == 'nonzero' else (wj & 1)
            if (w != 0) if r == 'nonzero' else (w & 1):
                return True
        return False
    keep = []
    checks = []
    for i in range(len(polys)):
        line = scanline(i, polys)
        if line is None:
            continue
        y, own, xs = line
        # the fill of the intervals between the crossings of the line
        mids = [xs[0] - 1.0] + [(xs[k] + xs[k + 1]) / 2
                                for k in range(len(xs) - 1)] \
               + [xs[-1] + 1.0]
        fills = [inside(x, y) for x in mids]
        checks.extend(zip(mids, [y] * len(mids), fills))
        visible = False
        for x in own:
            k = xs.index(x)
            # the intervals left and right of crossing k are k and k+1
            if fills[k] != fills[k + 1]:
                visible = True
                break
        if visible:
            keep.append(i)
    kept = [polys[i] for i in keep]
    for x, y, filled in checks:
        parity = sum(p.winding(x, y) & 1 for p in kept) & 1
        if bool(parity) != filled:
            warn(_("Fill of crossing subpaths approximated "
                   "(nonzero fill rule)"))
            break
    return [allsubs[i] for i in keep]


def self_intersecting(sub):
    """Whether the nonzero fill of the single subpath SUB differs from its
    even-odd fill (winding numbers beyond +-1)."""
    poly = Polygon(sub)
    l, b, r, t = poly.box
    for f in (0.2137, 0.5137, 0.8137):
        y = b + (t - b) * f
        w = 0
        for x, d in sorted(poly.crossings(y)):
            w += d
            if abs(w) > 1:
                return True
    return False
