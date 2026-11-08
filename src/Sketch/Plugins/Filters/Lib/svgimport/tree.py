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

# SVG import: the document tree and the style cascade.
#
# The XML tree is converted into Node objects with parent links and
# normalized names: elements of the SVG namespace (or of no namespace)
# by their local name, those of the known editor namespaces as
# `prefix:name'; attributes likewise (`xlink:href', `xml:space',
# `inkscape:label', ...).

import xml.etree.ElementTree as ET

from . import css, values

NAMESPACES = {
    'http://www.w3.org/2000/svg': '',
    'http://www.w3.org/1999/xlink': 'xlink',
    'http://www.w3.org/XML/1998/namespace': 'xml',
    'http://sodipodi.sourceforge.net/DTD/sodipodi-0.dtd': 'sodipodi',
    'http://inkscape.sourceforge.net/DTD/sodipodi-0.dtd': 'sodipodi',
    'http://www.inkscape.org/namespaces/inkscape': 'inkscape',
    'http://www.iki.fi/pav/software/textext/': 'textext',
    'http://www.skencil.org/namespaces/skencil': 'skencil',
}

def normalize(name):
    if name[0] != '{':
        return name
    ns, local = name[1:].split('}', 1)
    prefix = NAMESPACES.get(ns)
    if prefix is None:
        return name
    if prefix:
        return prefix + ':' + local
    return local


class Node:

    def __init__(self, element, parent):
        self.tag = normalize(element.tag) if isinstance(element.tag, str) \
                   else '#comment'
        self.attrib = dict((normalize(k), v)
                           for k, v in element.attrib.items())
        self.parent = parent
        self.element = element
        self.text = element.text or ''
        self.tail = element.tail or ''
        self.children = [Node(child, self) for child in element
                         if isinstance(child.tag, str)]
        self.decls = None       # the declarations from the style sheet

    def get(self, name, default = None):
        return self.attrib.get(name, default)

    def href(self):
        return self.attrib.get('href') or self.attrib.get('xlink:href')

    def iter(self):
        yield self
        for child in self.children:
            for node in child.iter():
                yield node

    def __repr__(self):
        id = self.get('id')
        return '<%s%s>' % (self.tag, id and ' #' + id or '')


def parse(data):
    """Parse the SVG document DATA (bytes).  Returns the root Node."""
    parser = ET.XMLParser()
    # entities of DTDs (e.g. the &ns_svg; of Illustrator files)
    # are declared in the internal subset, which expat handles; external
    # DTDs are not loaded.
    root = ET.fromstring(data, parser = parser)
    return Node(root, None)


# ------------------------------------------------------------------ styles

INHERITED = {
    'fill': 'black', 'fill-opacity': '1', 'fill-rule': 'nonzero',
    'stroke': 'none', 'stroke-width': '1', 'stroke-opacity': '1',
    'stroke-linecap': 'butt', 'stroke-linejoin': 'miter',
    'stroke-miterlimit': '4', 'stroke-dasharray': 'none',
    'stroke-dashoffset': '0', 'color': 'black', 'visibility': 'visible',
    # the initial font is up to the user agent: Inkscape's, which
    # converts the text (text.py)
    'font-family': 'sans-serif', 'font-size': 'medium',
    'font-style': 'normal',
    'font-weight': 'normal', 'font-variant': 'normal',
    'font-stretch': 'normal', 'text-anchor': 'start',
    'clip-rule': 'nonzero', 'marker-start': 'none', 'marker-mid': 'none',
    'marker-end': 'none', 'letter-spacing': 'normal',
    'word-spacing': 'normal', 'writing-mode': 'lr-tb',
    'direction': 'ltr', 'paint-order': 'normal',
    'image-rendering': 'auto', 'shape-rendering': 'auto',
    'text-rendering': 'auto', 'font-kerning': 'auto',
    'font-feature-settings': 'normal', 'font-variant-ligatures': 'normal',
}

NOT_INHERITED = {
    'opacity': '1', 'display': 'inline', 'clip-path': 'none',
    'mask': 'none', 'filter': 'none', 'overflow': 'visible',
    'stop-color': 'black', 'stop-opacity': '1', 'vector-effect': 'none',
    'mask-type': 'luminance', 'text-decoration': 'none',
    'dominant-baseline': 'auto', 'alignment-baseline': 'auto',
    'baseline-shift': 'baseline', 'mix-blend-mode': 'normal',
}

PROPERTIES = set(INHERITED) | set(NOT_INHERITED) | set(['marker', 'font'])

# the user agent style sheet: elements that establish a viewport clip
OVERFLOW_HIDDEN = ('svg', 'symbol', 'marker', 'pattern', 'image')

FONT_SIZES = {'xx-small': 9, 'x-small': 10, 'small': 13, 'medium': 16,
              'large': 18, 'x-large': 24, 'xx-large': 32}

ROOT_STYLE = dict(INHERITED)
ROOT_STYLE.update(NOT_INHERITED)
ROOT_STYLE['font-size'] = 16.0
ROOT_STYLE['_opacity'] = 1.0


class Cascade:

    def __init__(self, root):
        self.sheet = css.StyleSheet()
        for node in root.iter():
            if node.tag == 'style':
                type = node.get('type', 'text/css')
                if type in ('text/css', ''):
                    self.sheet.add(node.text + ''.join(child.text + child.tail
                                                       for child in
                                                       node.children))
        self.sheet.finish()

    def declarations(self, node):
        """The declarations applying to NODE in increasing priority."""
        if node.decls is None:
            normal = []
            important = []
            for name, value in node.attrib.items():
                if name in PROPERTIES:
                    normal.append((name, value.strip()))
            for name, value, imp in self.sheet.match(node):
                (important if imp else normal).append((name, value))
            for name, value, imp in css.declarations(node.get('style')):
                (important if imp else normal).append((name, value))
            node.decls = normal + important
        return node.decls

    def compute(self, node, parent):
        """The computed style of NODE given the computed style PARENT
        of its (rendering) parent."""
        style = dict(parent)
        style.update(NOT_INHERITED)
        if node.tag in OVERFLOW_HIDDEN:
            style['overflow'] = 'hidden'
        for name, value in self.declarations(node):
            if name == 'marker':
                for key in ('marker-start', 'marker-mid', 'marker-end'):
                    style[key] = parent[key] if value == 'inherit' else value
                continue
            if name == 'font':
                continue        # the shorthand is rare in SVG files
            if value == 'inherit':
                style[name] = parent.get(name, ROOT_STYLE.get(name))
            elif name == 'font-size':
                style[name] = font_size(value, parent['font-size'])
            else:
                style[name] = value
        opacity = number(style['opacity'], 1.0)
        style['_opacity'] = parent['_opacity'] * min(max(opacity, 0.0), 1.0)
        return style


def font_size(value, parent_size):
    value = value.strip().lower()
    if value in FONT_SIZES:
        return float(FONT_SIZES[value])
    if value == 'larger':
        return parent_size * 1.2
    if value == 'smaller':
        return parent_size / 1.2
    size = values.length(value, parent_size, parent_size)
    if size is None or size < 0:
        return parent_size
    return size

def number(text, default):
    try:
        value = float(text.strip().rstrip('%'))
        if text.strip().endswith('%'):
            value = value / 100.0
        return value
    except (ValueError, AttributeError):
        return default
