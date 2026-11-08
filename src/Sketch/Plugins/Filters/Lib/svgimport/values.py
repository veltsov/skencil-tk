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

# SVG import: attribute values -- numbers, lengths, colors, transforms.
#
# Matrices are 6-tuples (a, b, c, d, e, f) in the order of SVG's
# matrix(): x' = a x + c y + e, y' = b x + d y + f.  This is also the
# argument order of Sketch's Trafo(m11, m21, m12, m22, v1, v2).

import math
import re

rx_number = re.compile(r'[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?')

def numbers(text):
    """All numbers in TEXT (separated by whitespace and/or commas,
    or by nothing, as in the path data `.5.5' or `1-2')."""
    if not text:
        return []
    return [float(s) for s in rx_number.findall(text)]


# ---------------------------------------------------------------- matrices

IDENTITY = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)

def mul(m, n):
    """The matrix applying N first, then M."""
    a, b, c, d, e, f = m
    A, B, C, D, E, F = n
    return (a * A + c * B, b * A + d * B,
            a * C + c * D, b * C + d * D,
            a * E + c * F + e, b * E + d * F + f)

def translate(x, y):
    return (1.0, 0.0, 0.0, 1.0, x, y)

def scale(sx, sy = None):
    if sy is None:
        sy = sx
    return (sx, 0.0, 0.0, sy, 0.0, 0.0)

def rotate(degrees):
    a = math.radians(degrees)
    c = math.cos(a); s = math.sin(a)
    return (c, s, -s, c, 0.0, 0.0)

def apply(m, x, y):
    a, b, c, d, e, f = m
    return (a * x + c * y + e, b * x + d * y + f)

def apply_vector(m, x, y):
    a, b, c, d, e, f = m
    return (a * x + c * y, b * x + d * y)

def det(m):
    return m[0] * m[3] - m[1] * m[2]

def inverse(m):
    a, b, c, d, e, f = m
    D = a * d - b * c
    if D == 0:
        return None
    ia = d / D; ib = -b / D; ic = -c / D; id = a / D
    return (ia, ib, ic, id, -(ia * e + ic * f), -(ib * e + id * f))

def mean_scale(m):
    """The scale factor of lengths under M (sqrt |det|)."""
    return math.sqrt(abs(det(m)))

def anisotropy(m):
    """The ratio of the largest and the smallest singular value of the
    linear part of M (1 for similarities)."""
    a, b, c, d = m[:4]
    s1 = math.hypot(a + d, b - c)
    s2 = math.hypot(a - d, b + c)
    big = (s1 + s2) / 2; small = abs(s1 - s2) / 2
    if small < 1e-12:
        return float('inf')
    return big / small


rx_transform = re.compile(r'\s*([a-zA-Z]+)\s*\(([^)]*)\)\s*,?')

def parse_transform(text):
    """The matrix of an SVG transform list; None if it is malformed
    (the attribute is then ignored, as in browsers)."""
    m = IDENTITY
    if not text:
        return m
    pos = 0
    text = text.strip()
    while pos < len(text):
        match = rx_transform.match(text, pos)
        if not match:
            return None
        pos = match.end()
        name = match.group(1)
        args = numbers(match.group(2))
        n = len(args)
        if name == 'matrix' and n == 6:
            t = tuple(args)
        elif name == 'translate' and n in (1, 2):
            t = translate(args[0], args[1] if n == 2 else 0.0)
        elif name == 'scale' and n in (1, 2):
            t = scale(*args)
        elif name == 'rotate' and n in (1, 3):
            t = rotate(args[0])
            if n == 3:
                t = mul(translate(args[1], args[2]),
                        mul(t, translate(-args[1], -args[2])))
        elif name == 'skewX' and n == 1:
            t = (1.0, 0.0, math.tan(math.radians(args[0])), 1.0, 0.0, 0.0)
        elif name == 'skewY' and n == 1:
            t = (1.0, math.tan(math.radians(args[0])), 0.0, 1.0, 0.0, 0.0)
        else:
            return None
        m = mul(m, t)
    return m


# ----------------------------------------------------------------- lengths

# user units per unit; the user unit is the CSS px (1/96 in), which is
# mapped to 0.75 pt by the root transformation
UNITS = {'': 1.0, 'px': 1.0, 'pt': 96 / 72.0, 'pc': 16.0, 'in': 96.0,
         'cm': 96 / 2.54, 'mm': 96 / 25.4, 'q': 96 / 101.6}

rx_length = re.compile(r'\s*([-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?)'
                       r'\s*([a-zA-Z]*|%)\s*$')

def length(text, reference = 0.0, font_size = 16.0, default = None):
    """The length TEXT in user units.  Percentages are relative to
    REFERENCE, em/ex to FONT_SIZE.  DEFAULT is returned for missing or
    malformed values."""
    if text is None:
        return default
    match = rx_length.match(text)
    if not match:
        return default
    value = float(match.group(1))
    unit = match.group(2).lower()
    if unit == '%':
        return value * reference / 100.0
    if unit == 'em':
        return value * font_size
    if unit == 'ex':
        return value * font_size / 2
    factor = UNITS.get(unit)
    if factor is None:
        return default
    return value * factor

def length_unit(text):
    """The unit of the length TEXT ('' for user units), or None."""
    match = rx_length.match(text or '')
    return match and match.group(2).lower()


# ------------------------------------------------------------------ colors

def _named(spec):
    table = {}
    for item in spec.split():
        name, hex = item.split('=')
        table[name] = (int(hex[0:2], 16) / 255.0, int(hex[2:4], 16) / 255.0,
                       int(hex[4:6], 16) / 255.0)
    return table

NAMED_COLORS = _named('''
    aliceblue=f0f8ff antiquewhite=faebd7 aqua=00ffff aquamarine=7fffd4
    azure=f0ffff beige=f5f5dc bisque=ffe4c4 black=000000
    blanchedalmond=ffebcd blue=0000ff blueviolet=8a2be2 brown=a52a2a
    burlywood=deb887 cadetblue=5f9ea0 chartreuse=7fff00 chocolate=d2691e
    coral=ff7f50 cornflowerblue=6495ed cornsilk=fff8dc crimson=dc143c
    cyan=00ffff darkblue=00008b darkcyan=008b8b darkgoldenrod=b8860b
    darkgray=a9a9a9 darkgreen=006400 darkgrey=a9a9a9 darkkhaki=bdb76b
    darkmagenta=8b008b darkolivegreen=556b2f darkorange=ff8c00
    darkorchid=9932cc darkred=8b0000 darksalmon=e9967a darkseagreen=8fbc8f
    darkslateblue=483d8b darkslategray=2f4f4f darkslategrey=2f4f4f
    darkturquoise=00ced1 darkviolet=9400d3 deeppink=ff1493
    deepskyblue=00bfff dimgray=696969 dimgrey=696969 dodgerblue=1e90ff
    firebrick=b22222 floralwhite=fffaf0 forestgreen=228b22 fuchsia=ff00ff
    gainsboro=dcdcdc ghostwhite=f8f8ff gold=ffd700 goldenrod=daa520
    gray=808080 green=008000 greenyellow=adff2f grey=808080 honeydew=f0fff0
    hotpink=ff69b4 indianred=cd5c5c indigo=4b0082 ivory=fffff0 khaki=f0e68c
    lavender=e6e6fa lavenderblush=fff0f5 lawngreen=7cfc00
    lemonchiffon=fffacd lightblue=add8e6 lightcoral=f08080 lightcyan=e0ffff
    lightgoldenrodyellow=fafad2 lightgray=d3d3d3 lightgreen=90ee90
    lightgrey=d3d3d3 lightpink=ffb6c1 lightsalmon=ffa07a
    lightseagreen=20b2aa lightskyblue=87cefa lightslategray=778899
    lightslategrey=778899 lightsteelblue=b0c4de lightyellow=ffffe0
    lime=00ff00 limegreen=32cd32 linen=faf0e6 magenta=ff00ff maroon=800000
    mediumaquamarine=66cdaa mediumblue=0000cd mediumorchid=ba55d3
    mediumpurple=9370db mediumseagreen=3cb371 mediumslateblue=7b68ee
    mediumspringgreen=00fa9a mediumturquoise=48d1cc mediumvioletred=c71585
    midnightblue=191970 mintcream=f5fffa mistyrose=ffe4e1 moccasin=ffe4b5
    navajowhite=ffdead navy=000080 oldlace=fdf5e6 olive=808000
    olivedrab=6b8e23 orange=ffa500 orangered=ff4500 orchid=da70d6
    palegoldenrod=eee8aa palegreen=98fb98 paleturquoise=afeeee
    palevioletred=db7093 papayawhip=ffefd5 peachpuff=ffdab9 peru=cd853f
    pink=ffc0cb plum=dda0dd powderblue=b0e0e6 purple=800080 red=ff0000
    rosybrown=bc8f8f royalblue=4169e1 saddlebrown=8b4513 salmon=fa8072
    sandybrown=f4a460 seagreen=2e8b57 seashell=fff5ee sienna=a0522d
    silver=c0c0c0 skyblue=87ceeb slateblue=6a5acd slategray=708090
    slategrey=708090 snow=fffafa springgreen=00ff7f steelblue=4682b4
    tan=d2b48c teal=008080 thistle=d8bfd8 tomato=ff6347 turquoise=40e0d0
    violet=ee82ee wheat=f5deb3 white=ffffff whitesmoke=f5f5f5 yellow=ffff00
    yellowgreen=9acd32
''')

def _channel(text, scale = 255.0):
    text = text.strip()
    if text.endswith('%'):
        value = float(text[:-1]) / 100.0
    else:
        value = float(text) / scale
    return min(max(value, 0.0), 1.0)

def _hsl(h, s, l):
    h = (h % 360) / 360.0
    if s == 0:
        return (l, l, l)
    q = l * (1 + s) if l < 0.5 else l + s - l * s
    p = 2 * l - q
    def hue(t):
        t = t % 1.0
        if t < 1 / 6.0: return p + (q - p) * 6 * t
        if t < 0.5: return q
        if t < 2 / 3.0: return p + (q - p) * (2 / 3.0 - t) * 6
        return p
    return (hue(h + 1 / 3.0), hue(h), hue(h - 1 / 3.0))

rx_function = re.compile(r'\s*(rgba?|hsla?)\s*\(([^)]*)\)\s*$', re.I)

def color(text):
    """Parse a CSS color: return (r, g, b, alpha) with components in
    0..1, the string 'currentColor', or None if TEXT is not a color."""
    if text is None:
        return None
    text = text.strip()
    lower = text.lower()
    if lower == 'currentcolor':
        return 'currentColor'
    if lower == 'transparent':
        return (0.0, 0.0, 0.0, 0.0)
    if lower in NAMED_COLORS:
        return NAMED_COLORS[lower] + (1.0,)
    if text.startswith('#'):
        hex = text[1:]
        try:
            if len(hex) in (3, 4):
                values = [int(c * 2, 16) / 255.0 for c in hex]
            elif len(hex) in (6, 8):
                values = [int(hex[i:i + 2], 16) / 255.0
                          for i in range(0, len(hex), 2)]
            else:
                return None
        except ValueError:
            return None
        if len(values) == 3:
            values.append(1.0)
        return tuple(values)
    match = rx_function.match(text)
    if match:
        args = [a for a in re.split(r'[\s,/]+', match.group(2).strip()) if a]
        try:
            if match.group(1).lower().startswith('rgb'):
                if len(args) not in (3, 4):
                    return None
                rgb = tuple(_channel(a) for a in args[:3])
            else:
                if len(args) not in (3, 4):
                    return None
                h = float(re.sub('deg$', '', args[0]))
                rgb = _hsl(h, _channel(args[1], 100.0),
                           _channel(args[2], 100.0))
            alpha = _channel(args[3], 1.0) if len(args) == 4 else 1.0
        except ValueError:
            return None
        return rgb + (alpha,)
    return None


rx_url = re.compile(r'\s*url\(\s*[\'"]?\s*#([^\'")\s]+)\s*[\'"]?\s*\)\s*(.*)$')

def paint(text):
    """Parse a fill/stroke value.  Returns None (no paint), a color
    tuple, 'currentColor', ('url', id, fallback) with FALLBACK a paint
    value itself, or 'invalid'."""
    if text is None:
        return 'invalid'
    text = text.strip()
    if text == 'none':
        return None
    match = rx_url.match(text)
    if match:
        fallback = match.group(2).strip()
        return ('url', match.group(1), paint(fallback) if fallback else None)
    value = color(text)
    if value is None:
        return 'invalid'
    return value

def url_id(text):
    """The id referenced by a `url(#id)' value, or None."""
    if not text:
        return None
    match = rx_url.match(text)
    return match and match.group(1)

def href_id(text):
    """The id of a local `#id' reference, or None."""
    if text and text.strip().startswith('#'):
        return text.strip()[1:]
    return None
