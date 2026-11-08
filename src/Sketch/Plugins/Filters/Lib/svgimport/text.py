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
# SVG import: text, imported as curves.
#
# Sketch's text model cannot represent SVG text (fonts, per-glyph
# positions, tspans), so text is converted to curves:
#
# - text in SVG fonts (<font> with <glyph> outlines; dvisvgm's default
#   output) is laid out here: one glyph per character at the positions
#   of the x/y/dx/dy lists and the advances;
# - all other text is converted by Inkscape (`inkscape -T'), once for
#   the whole document: every text element is copied, with its font
#   properties made explicit, into a temporary SVG file; the converted
#   groups (one path per tspan, carrying the tspan's own style) replace
#   the text elements and are imported like any other content, so the
#   paint still comes from the cascade of the original document;
# - without Inkscape, each text chunk becomes a SimpleText in the
#   fallback font with the size, color and alignment of the text.

import copy
import os
import shutil
import subprocess
import tempfile
import xml.etree.ElementTree as ET

from Sketch import _, Trafo, SimpleText, Group, PropertyStack, GetFont
from Sketch.Base import config
from Sketch.Graphics.properties import factory_text_style

from . import values, pathdata, paint, tree
from .values import mul

SVG_NS = 'http://www.w3.org/2000/svg'
XLINK_NS = 'http://www.w3.org/1999/xlink'

# the inherited properties that determine the shape of text
FONT_PROPERTIES = ('font-family', 'font-style', 'font-weight',
                   'font-variant', 'font-stretch', 'letter-spacing',
                   'word-spacing', 'text-anchor', 'writing-mode', 'direction',
                   'font-kerning', 'font-feature-settings',
                   'font-variant-ligatures', 'text-rendering')

INKSCAPE_TIMEOUT = 120

def inkscape_command():
    return os.environ.get('INKSCAPE') or 'inkscape'


def font_style_string(style):
    items = ['font-size:%gpx' % style['font-size']]
    for name in FONT_PROPERTIES:
        value = style.get(name)
        if value is not None:
            items.append('%s:%s' % (name, value))
    return ';'.join(items)


def families(style):
    return [f.strip().strip('\'"') for f in style['font-family'].split(',')]


# --------------------------------------------------------------- SVG fonts

class SVGFont:

    def __init__(self, node):
        self.node = node
        face = None
        for child in node.children:
            if child.tag == 'font-face':
                face = child
        self.family = face is not None and face.get('font-family') \
                      or node.get('id')
        self.units = tree.number(face.get('units-per-em', '1000'), 1000.0) \
                     if face is not None else 1000.0
        self.advance = tree.number(node.get('horiz-adv-x', '0'), 0.0)
        self.glyphs = {}
        self.missing = None
        self.max_len = 1
        for child in node.children:
            if child.tag == 'glyph':
                code = child.get('unicode')
                if code:
                    self.glyphs.setdefault(code, child)
                    self.max_len = max(self.max_len, len(code))
            elif child.tag == 'missing-glyph':
                self.missing = child
        self.cache = {}

    def outline(self, glyph):
        """The subpaths (font units, y up) and the advance of GLYPH."""
        result = self.cache.get(id(glyph))
        if result is None:
            adv = tree.number(glyph.get('horiz-adv-x'), self.advance) \
                  if glyph.get('horiz-adv-x') is not None else self.advance
            result = self.cache[id(glyph)] = (pathdata.parse(glyph.get('d')),
                                             adv)
        return result

    def lookup(self, text, i, limit = None):
        """The glyph for the characters of TEXT at I and their number (at
        most LIMIT: ligatures do not cross element boundaries)."""
        if limit is None:
            limit = len(text) - i
        for n in range(min(self.max_len, limit), 0, -1):
            glyph = self.glyphs.get(text[i:i + n])
            if glyph is not None:
                return glyph, n
        return self.missing, 1


# ----------------------------------------------------------------- layout

class Char:

    def __init__(self, char, elements):
        self.char = char
        self.elements = elements    # the text/tspan stack, innermost last


def collect_chars(node):
    """The characters of the text element NODE with their element
    stacks, white space handled (xml:space)."""
    chars = []
    def walk(elem, stack, preserve):
        space = elem.get('xml:space')
        if space:
            preserve = space == 'preserve'
        stack = stack + [elem]
        def add(text):
            for c in text:
                chars.append((Char(c, stack), preserve))
        add(elem.text)
        for child in elem.children:
            if child.tag in ('tspan', 'a', 'textPath', 'tref'):
                walk(child, stack, preserve)
            add(child.tail)
    walk(node, [], False)
    # white space: newlines removed, tabs to spaces, runs collapsed,
    # leading and trailing spaces removed (xml:space="default")
    result = []
    for ch, preserve in chars:
        c = ch.char
        if preserve:
            if c in '\n\r\t':
                c = ' '
        else:
            if c in '\n\r':
                continue
            if c == '\t':
                c = ' '
            if c == ' ' and (not result or result[-1][0].char == ' '):
                continue
        ch.char = c
        result.append((ch, preserve))
    while result and result[-1][0].char == ' ' and not result[-1][1]:
        result.pop()
    return [ch for ch, preserve in result]


def position_lists(chars, style_of, vp):
    """Assign the x/y/dx/dy/rotate list values to CHARS: each element's
    lists apply to its own characters in order (inner elements win)."""
    counters = {}
    lists = {}
    for ch in chars:
        ch.x = ch.y = None
        ch.dx = ch.dy = 0.0
        ch.rotate = None
        for elem in ch.elements:
            key = id(elem)
            index = counters.get(key, 0)
            counters[key] = index + 1
            if key not in lists:
                fs = style_of(elem)['font-size']
                def get(name, ref):
                    return [values.length(item, ref, fs, 0.0) for item in
                            (elem.get(name) or '').replace(',', ' ').split()]
                lists[key] = (get('x', vp[0]), get('y', vp[1]),
                              get('dx', vp[0]), get('dy', vp[1]),
                              values.numbers(elem.get('rotate')))
            xs, ys, dxs, dys, rotates = lists[key]
            if index < len(xs):
                ch.x = xs[index]
            if index < len(ys):
                ch.y = ys[index]
            if index < len(dxs):
                ch.dx = dxs[index]
            if index < len(dys):
                ch.dy = dys[index]
            if rotates:
                ch.rotate = rotates[min(index, len(rotates) - 1)]


class TextConverter:

    def __init__(self, builder):
        self.builder = builder
        self.prepared = False
        self.fonts = {}
        self.converted = {}
        self.inkscape_failed = None

    # ------------------------------------------------------- preparation

    def prepare(self):
        if self.prepared:
            return
        self.prepared = True
        b = self.builder
        texts = []
        for node in b.root.iter():
            if node.tag == 'font':
                font = SVGFont(node)
                if font.family and font.family not in self.fonts:
                    self.fonts[font.family] = font
            elif node.tag in ('text', 'flowRoot'):
                texts.append(node)
        texts = [node for node in texts
                 if self.svg_font(b.tree_style(node)) is None]
        if texts:
            self.convert_with_inkscape(texts)

    def svg_font(self, style):
        for family in families(style):
            font = self.fonts.get(family)
            if font is not None:
                return font
        return None

    def convert_with_inkscape(self, texts):
        b = self.builder
        ET.register_namespace('', SVG_NS)
        ET.register_namespace('xlink', XLINK_NS)
        root = ET.Element('{%s}svg' % SVG_NS)
        root.set('width', '100'); root.set('height', '100')
        defs = ET.SubElement(root, '{%s}defs' % SVG_NS)
        referenced = set()
        for node in b.root.iter():
            if node.tag in ('style', 'font'):
                defs.append(detached(node.element))
        for i, node in enumerate(texts):
            for sub in node.iter():
                if sub.tag in ('textPath', 'tref'):
                    ref = b.lookup(values.href_id(sub.href()))
                    if ref is not None and id(ref) not in referenced:
                        referenced.add(id(ref))
                        copy_ = detached(ref.element)
                        copy_.attrib.pop('transform', None)
                        defs.append(copy_)
            wrapper = ET.SubElement(root, '{%s}g' % SVG_NS)
            wrapper.set('id', 'sktext%d' % i)
            parent_style = b.tree_style(node.parent) if node.parent \
                           else tree.ROOT_STYLE
            wrapper.set('style', font_style_string(parent_style))
            element = detached(node.element)
            # the font properties from style sheets made explicit
            own = font_style_string(b.tree_style(node))
            if element.get('style'):
                own = own + ';' + element.get('style')
            element.set('style', own)
            space = self.inherited_space(node)
            if space and element.get('{http://www.w3.org/XML/1998/'
                                     'namespace}space') is None:
                element.set('{http://www.w3.org/XML/1998/namespace}space',
                            space)
            wrapper.append(element)
        tmpdir = tempfile.mkdtemp(prefix = 'sksvg')
        try:
            infile = os.path.join(tmpdir, 'text.svg')
            outfile = os.path.join(tmpdir, 'paths.svg')
            ET.ElementTree(root).write(infile, encoding = 'utf-8',
                                       xml_declaration = True)
            try:
                subprocess.run([inkscape_command(), '-T', '-o', outfile,
                                infile], stdout = subprocess.DEVNULL,
                               stderr = subprocess.DEVNULL,
                               timeout = INKSCAPE_TIMEOUT, check = True)
                result = tree.parse(open(outfile, 'rb').read())
            except (OSError, subprocess.SubprocessError, ET.ParseError):
                self.inkscape_failed = True
                return
        finally:
            shutil.rmtree(tmpdir, ignore_errors = True)
        wrappers = {}
        for node in result.iter():
            name = node.get('id') or ''
            if node.tag == 'g' and name.startswith('sktext'):
                wrappers[name] = node
        for i, node in enumerate(texts):
            wrapper = wrappers.get('sktext%d' % i)
            if wrapper is None:
                continue
            groups = [c for c in wrapper.children if c.tag == 'g']
            if len(groups) == 1 and len(wrapper.children) == 1:
                converted = groups[0]
            else:
                converted = wrapper
                converted.attrib = {}
                converted.decls = []
            converted.tag = 'g'
            converted.parent = node.parent
            # the original's style (sheet, attributes) and transform
            converted.decls = b.cascade.declarations(node)
            if node.get('transform') is not None:
                converted.attrib['transform'] = node.get('transform')
            else:
                converted.attrib.pop('transform', None)
            for sub in converted.iter():
                if sub is not converted:
                    # no clip-paths, masks etc. of the temporary file
                    for name in ('clip-path', 'mask', 'filter'):
                        sub.attrib.pop(name, None)
            self.converted[id(node)] = converted

    def inherited_space(self, node):
        while node is not None:
            space = node.get('xml:space')
            if space:
                return space
            node = node.parent
        return None

    # ------------------------------------------------------------ render

    def replacement(self, node):
        """The converted group replacing the text element NODE, or
        None."""
        self.prepare()
        return self.converted.get(id(node))

    def text(self, node, ctm, style, vp):
        self.prepare()
        if style['visibility'] in ('hidden', 'collapse'):
            return []
        font = self.svg_font(style)
        if font is not None:
            return self.svg_font_text(node, ctm, style, vp, font)
        return self.fallback(node, ctm, style, vp)

    def flow(self, node, ctm, style, vp):
        self.prepare()
        b = self.builder
        if self.inkscape_failed:
            b.warn(_("Flowed text ignored: inkscape not found"))
        return []

    def child_style(self, node, style, chars = None):
        """A function returning the computed style of the elements of the
        text NODE (computed STYLE)."""
        b = self.builder
        styles = {id(node): style}
        def style_of(elem):
            s = styles.get(id(elem))
            if s is None:
                s = styles[id(elem)] = b.cascade.compute(
                    elem, style_of(elem.parent))
            return s
        return style_of

    def layout(self, node, chars, style, vp, advance):
        """Lay out the characters CHARS (collect_chars) of NODE.
        ADVANCE(char, style) gives the advance width of a character.
        Returns a list of [char, style, x, y] with the text anchors
        applied."""
        style_of = self.child_style(node, style, chars)
        position_lists(chars, style_of, vp)
        x = y = 0.0
        placed = []
        chunks = []
        for ch in chars:
            s = style_of(ch.elements[-1])
            if ch.x is not None or ch.y is not None or not chunks:
                chunks.append([])
            if ch.x is not None:
                x = ch.x
            if ch.y is not None:
                y = ch.y
            x += ch.dx; y += ch.dy
            item = [ch, s, x, y]
            placed.append(item)
            chunks[-1].append(item)
            x += advance(ch, s)
        for chunk in chunks:
            if not chunk:
                continue
            anchor = chunk[0][1]['text-anchor']
            if anchor not in ('middle', 'end'):
                continue
            last = chunk[-1]
            width = last[2] + advance(last[0], last[1]) - chunk[0][2]
            shift = width if anchor == 'end' else width / 2
            for item in chunk:
                item[2] -= shift
        return placed

    def svg_font_text(self, node, ctm, style, vp, font):
        b = self.builder
        def advance(ch, s):
            glyph = ch.glyph
            if glyph is None:
                return 0.0
            outline, adv = font.outline(glyph)
            spacing = values.length(s['letter-spacing'], 0, s['font-size'],
                                    0.0) if s['letter-spacing'] != 'normal' \
                      else 0.0
            if ch.char == ' ' and s['word-spacing'] != 'normal':
                spacing += values.length(s['word-spacing'], 0,
                                         s['font-size'], 0.0)
            return adv * s['font-size'] / font.units + spacing
        chars = collect_chars(node)
        # glyph lookup, ligatures included
        string = ''.join(ch.char for ch in chars)
        i = 0
        missing = 0
        while i < len(chars):
            same = 1
            while i + same < len(chars) \
                  and chars[i + same].elements is chars[i].elements:
                same += 1
            glyph, n = font.lookup(string, i, same)
            chars[i].glyph = glyph
            if glyph is None and chars[i].char != ' ':
                missing += 1
            for k in range(1, n):
                chars[i + k].glyph = None
                chars[i + k].skip = True
            i += n
        if missing:
            b.warn(_("Characters missing in SVG fonts ignored"))
        chars = [ch for ch in chars if not getattr(ch, 'skip', False)]
        placed = self.layout(node, chars, style, vp, advance)
        # one path per run of characters with the same style
        runs = []
        for ch, s, x, y in placed:
            if ch.glyph is None:
                continue
            outline, adv = font.outline(ch.glyph)
            if not outline:
                continue
            k = s['font-size'] / font.units
            m = values.translate(x, y)
            if ch.rotate:
                m = mul(m, values.rotate(ch.rotate))
            m = mul(m, (k, 0.0, 0.0, -k, 0.0, 0.0))
            subs = [sub.transformed(m) for sub in outline]
            if runs and runs[-1][0] is s:
                runs[-1][1].extend(subs)
            else:
                runs.append((s, subs))
        objects = []
        for s, subs in runs:
            objects.extend(b.path(node, ctm, s, subs))
        if len(objects) > 1:
            objects = [Group(objects)]
        return objects

    # ---------------------------------------------------------- fallback

    def fallback(self, node, ctm, style, vp):
        """SimpleTexts in the fallback font, one per text chunk."""
        b = self.builder
        font = GetFont(config.preferences.fallback_font)
        names = font.glyph_names
        from Sketch.Lib.glyphnames import unicode_to_glyphnames
        def has_glyph(c):
            return c == ' ' or any(n in names
                                   for n in unicode_to_glyphnames(c) or ())
        chars = collect_chars(node)
        style_of = self.child_style(node, style, chars)
        position_lists(chars, style_of, vp)
        # runs of characters with one style and consecutive positions,
        # grouped into the anchored chunks (absolute positions)
        anchored = []
        x = y = 0.0
        dropped = 0
        for ch in chars:
            s = style_of(ch.elements[-1])
            if ch.x is not None or ch.y is not None or not anchored:
                anchored.append([])
            if ch.x is not None:
                x = ch.x
            if ch.y is not None:
                y = ch.y
            runs = anchored[-1]
            if ch.dx or ch.dy or not runs or runs[-1][2] is not s:
                x += ch.dx; y += ch.dy
                runs.append([x, y, s, ''])
            if has_glyph(ch.char):
                runs[-1][3] += ch.char
                x += font.TextCoordBox(ch.char, s['font-size'])[2]
            else:
                dropped += 1
        objects = []
        k = values.mean_scale(ctm)
        for runs in anchored:
            if not runs:
                continue
            anchor = runs[0][2]['text-anchor']
            shift = 0.0
            if anchor in ('middle', 'end'):
                last = runs[-1]
                width = last[0] + font.TextCoordBox(
                    last[3], last[2]['font-size'])[2] - runs[0][0]
                shift = width if anchor == 'end' else width / 2
            for x, y, s, string in runs:
                if not string.strip():
                    continue
                color = b.solid_color(s, 'fill')
                if color is None:
                    continue
                base = factory_text_style.Copy()
                base.font = font
                base.font_size = round(s['font-size'] * k, 6)
                base.fill_pattern = paint.solid(color)
                m = mul(ctm, mul(values.translate(x - shift, y),
                                 (1 / k, 0.0, 0.0, -1 / k, 0.0, 0.0)))
                objects.append(SimpleText(Trafo(*m), string,
                                          properties = PropertyStack(
                                              base = base)))
        if objects:
            b.warn(_("Text imported in the font %s (inkscape not found)")
                   % font.PostScriptName())
        if dropped:
            b.warn(_("Characters missing in the font %s ignored")
                   % font.PostScriptName())
        if len(objects) > 1:
            objects = [Group(objects)]
        return objects


def detached(element):
    """A copy of ELEMENT without its tail."""
    result = copy.deepcopy(element)
    result.tail = None
    return result
