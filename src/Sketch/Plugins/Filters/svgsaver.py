# Sketch - A Python-based interactive drawing program
# Copyright (C) 1997, 1998, 1999, 2000, 2001, 2002, 2004 by Bernhard Herzog
# Part of the code for Arrow heads and text from Paul Giotta (2002)
# Rewritten 2026 by Vladimir Eltsov
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

# SVG export.  This module holds the shared saver and the "Inkscape
# SVG" export filter; svgsaverplain.py is the "Plain SVG" filter.
#
# Both reproduce the PostScript rendering (psdevice.py and
# Resources/Misc/sketch-proc.ps) as closely as SVG allows.  The
# Inkscape flavour additionally keeps the editing structure: layers
# with their names and state, guides, grid, clones as <use>, editable
# ellipse arcs, LaTeX objects as TexText groups, skencil:* metadata of
# plugin objects and text, optionally text as <text>.
# See devdocs/svg-export.md.

###Sketch Config
#type = Export
#tk_file_type = ("Inkscape SVG", '.svg')
#extensions = '.svg'
format_name = 'SVG-Inkscape'
#parameters = (\
#    ('box','choice',0,('Page','Bounding box'),'Export area'), \
#    ('text','choice',0,('Paths','Text'),'Text as'), \
#    ('eps','choice',0,('Vector','Image'),'EPS files'), \
#    ('eps_dpi','int',300,(30,2400),'EPS image resolution'), \
#    ('images','choice',0,('Embed','Link'),'Linked images'))
#unload = 1
###End

import os, re, base64, io, shutil, subprocess, tempfile
from math import atan2, hypot, pi, sqrt, cos, sin
import xml.etree.ElementTree as ET

from Sketch import Trafo, Rotation, Translation, Scale, Point, \
     SketchError, SketchVersion, _
from Sketch.Base import const, config
from Sketch.Base.warn import warn, USER, warn_tb
from Sketch.Graphics import font as font_module
from Sketch.Lib import glyphnames, util


SVG_NS = 'http://www.w3.org/2000/svg'
XLINK_NS = 'http://www.w3.org/1999/xlink'
SODIPODI_NS = 'http://sodipodi.sourceforge.net/DTD/sodipodi-0.dtd'
INKSCAPE_NS = 'http://www.inkscape.org/namespaces/inkscape'
TEXTEXT_NS = 'http://www.iki.fi/pav/software/textext/'
SKENCIL_NS = 'http://www.skencil.org/namespaces/skencil'

for _prefix, _uri in (('', SVG_NS), ('xlink', XLINK_NS),
                      ('sodipodi', SODIPODI_NS), ('inkscape', INKSCAPE_NS),
                      ('textext', TEXTEXT_NS), ('skencil', SKENCIL_NS)):
    ET.register_namespace(_prefix, _uri)

def svg(tag):
    return '{%s}%s' % (SVG_NS, tag)

XLINK_HREF = '{%s}href' % XLINK_NS

def sodipodi(name):
    return '{%s}%s' % (SODIPODI_NS, name)

def inkscape(name):
    return '{%s}%s' % (INKSCAPE_NS, name)

def textext(name):
    return '{%s}%s' % (TEXTEXT_NS, name)

def skencil(name):
    return '{%s}%s' % (SKENCIL_NS, name)


# PostScript draws lines of width 0 as the thinnest line the device
# can render.  SVG has no such notion; use a thin fixed width.
HAIRLINE_WIDTH = 0.3
# psdevice.py sets this globally
MITER_LIMIT = 10.433
# number of wedges approximating a conical gradient (PS: 50 steps)
CONICAL_STEPS = 128
# TexText version whose attribute conventions are written
TEXTEXT_VERSION = '1.9.0'


def num(value):
    """Format a coordinate: fixed precision, no trailing zeros."""
    s = '%.4f' % value
    if '.' in s:
        s = s.rstrip('0').rstrip('.')
    if s == '-0':
        s = '0'
    return s

def nums(*values):
    return ' '.join(map(num, values))

def matrix(trafo):
    return 'matrix(%s)' % nums(*trafo.coeff())

def csscolor(color):
    return '#%02x%02x%02x' % tuple(
        min(255, max(0, int(round(255 * c))))
        for c in (color.red, color.green, color.blue))

def style_string(style):
    return ';'.join(['%s:%s' % item for item in style])

def path_data(paths, trafo):
    """Return SVG path data for the Sketch paths PATHS transformed by
    TRAFO."""
    data = []
    for path in paths:
        items = path.get_save()
        if not items:
            continue
        x, y = trafo(items[0][0], items[0][1])
        data.append('M%s' % nums(x, y))
        for item in items[1:]:
            if len(item) == 3:
                x, y = trafo(item[0], item[1])
                data.append('L%s' % nums(x, y))
            else:
                x1, y1 = trafo(item[0], item[1])
                x2, y2 = trafo(item[2], item[3])
                x, y = trafo(item[4], item[5])
                data.append('C%s' % nums(x1, y1, x2, y2, x, y))
        if path.closed:
            data.append('Z')
    return ''.join(data)

def polygon_data(points):
    data = ['M%s' % nums(*points[0])]
    for p in points[1:]:
        data.append('L%s' % nums(*p))
    data.append('Z')
    return ''.join(data)

def is_unit(x, y, eps = 1e-9):
    return abs(x) < eps and abs(abs(y) - 1) < eps

def orthonormal_frame(c1, c2):
    """Return (u1, u2, l1, l2) if the vectors C1 and C2 are orthogonal
    and non-zero: their unit vectors and lengths.  Else None."""
    l1 = hypot(*c1); l2 = hypot(*c2)
    if l1 < 1e-9 or l2 < 1e-9:
        return None
    if abs(c1[0] * c2[0] + c1[1] * c2[1]) > 1e-7 * l1 * l2:
        return None
    return ((c1[0] / l1, c1[1] / l1), (c2[0] / l2, c2[1] / l2), l1, l2)

def ellipse_frame(m11, m21, m12, m22):
    """Singular value decomposition of the 2x2 matrix A = [[m11 m12]
    [m21 m22]] that maps the unit circle to an ellipse: return (u1,
    u2, s1, s2, phi) with A = U * diag(s1, s2) * R(phi)^T, U having the
    columns u1, u2 (orthonormal, possibly a reflection) and R(phi) the
    rotation by phi.  Return None for a degenerate matrix."""
    e = m11 * m11 + m21 * m21
    f = m11 * m12 + m21 * m22
    g = m12 * m12 + m22 * m22
    phi = 0.5 * atan2(2 * f, e - g)
    mean = (e + g) / 2
    root = hypot((e - g) / 2, f)
    s1 = sqrt(max(mean + root, 0))
    s2 = sqrt(max(mean - root, 0))
    if s2 < 1e-9:
        return None
    c = cos(phi); s = sin(phi)
    u1 = ((m11 * c + m12 * s) / s1, (m21 * c + m22 * s) / s1)
    u2 = ((-m11 * s + m12 * c) / s2, (-m21 * s + m22 * c) / s2)
    return u1, u2, s1, s2, phi


class Shape:

    """The geometry of a primitive, independent of its paint: a list of
    (tag, attributes) items, the transformation of the items' local
    coordinate system to the user space (None for baked coordinates)
    and the fill rule."""

    def __init__(self, items, local = None, fill_rule = 'evenodd',
                 attrs = None):
        self.items = items
        self.local = local
        self.fill_rule = fill_rule
        # extra attributes of the element (or the group for several
        # items), e.g. metadata
        self.attrs = attrs or {}


class _ParamCapture:

    """A fake .sk writer that records the arguments of the first
    BeginPluginCompound call (the class name and parameters of a
    plugin object)."""

    class Done(Exception):
        pass

    def __init__(self):
        self.args = None

    def BeginPluginCompound(self, *args, **kw):
        self.args = args
        raise self.Done

    def __getattr__(self, name):
        return lambda *args, **kw: None

def plugin_parameters(obj):
    capture = _ParamCapture()
    try:
        obj.SaveToFile(capture)
    except _ParamCapture.Done:
        pass
    except Exception:
        return None
    return capture.args


# Map the font families of the Type 1 fonts Skencil uses (sfd files)
# to the families of the URW base 35 OpenType fonts that current
# text renderers use, plus a generic fallback.
font_family_map = {
    'Nimbus Roman No9 L':     ('Nimbus Roman', 'serif'),
    'Times':                  ('Nimbus Roman', 'serif'),
    'Nimbus Sans L':          ('Nimbus Sans', 'sans-serif'),
    'Helvetica':              ('Nimbus Sans', 'sans-serif'),
    'Nimbus Mono L':          ('Nimbus Mono PS', 'monospace'),
    'Courier':                ('Nimbus Mono PS', 'monospace'),
    'URW Gothic L':           ('URW Gothic', 'sans-serif'),
    'ITC Avant Garde Gothic': ('URW Gothic', 'sans-serif'),
    'URW Bookman L':          ('URW Bookman', 'serif'),
    'ITC Bookman':            ('URW Bookman', 'serif'),
    'Century Schoolbook L':   ('C059', 'serif'),
    'New Century Schoolbook': ('C059', 'serif'),
    'URW Palladio L':         ('P052', 'serif'),
    'Palatino':               ('P052', 'serif'),
    'URW Chancery L':         ('Z003', 'cursive'),
    'ITC Zapf Chancery':      ('Z003', 'cursive'),
    'Standard Symbols L':     ('Standard Symbols PS', 'serif'),
    'Symbol':                 ('Standard Symbols PS', 'serif'),
    'Dingbats':               ('D050000L', 'fantasy'),
    'ITC Zapf Dingbats':      ('D050000L', 'fantasy'),
    'Bitstream Charter':      ('Bitstream Charter', 'serif'),
    'Utopia':                 ('Utopia', 'serif'),
    }

def font_style(font, size):
    """Return the CSS font properties for the Sketch font FONT."""
    family = font.family
    attrs = font.font_attrs.split()
    mapped, generic = font_family_map.get(family, (family, 'serif'))
    style = []
    if 'Condensed' in attrs or 'Narrow' in attrs:
        if mapped == 'Nimbus Sans':
            mapped = 'Nimbus Sans Narrow'
        else:
            style.append(('font-stretch', 'condensed'))
    style.insert(0, ('font-family', "'%s', %s" % (mapped, generic)))
    weight = 'normal'
    if 'Bold' in attrs:
        weight = 'bold'
        if 'Demi' in attrs:
            weight = '600'
    elif 'Demi' in attrs or 'DemiBold' in attrs:
        weight = '600'
    elif 'Medium' in attrs:
        # the bold weight of Nimbus Roman No9 L is called Medium
        weight = 'bold' if family in ('Nimbus Roman No9 L', 'Times') \
                 else '500'
    elif 'Light' in attrs:
        weight = '300'
    slant = 'normal'
    for attr in attrs:
        if attr.startswith('Ital'):
            slant = 'italic'
        elif attr.startswith('Obli'):
            slant = 'oblique'
    style.append(('font-weight', weight))
    style.append(('font-style', slant))
    style.append(('font-size', num(size) + 'px'))
    # glyphs are positioned individually; never let the renderer
    # build ligatures or kern
    style.append(('font-kerning', 'none'))
    style.append(('font-variant-ligatures', 'none'))
    style.append(('font-feature-settings', '"liga" 0, "clig" 0, "kern" 0'))
    return style


def find_ltx_preamble(document):
    """Return the name of the sk-ltx.tex file the LaTeX plugin would
    use for DOCUMENT, or ''."""
    try:
        from Sketch.Plugins.Objects import latextext
        filename = latextext.find_user_preamble(document)[0]
        return os.path.abspath(filename) if filename else ''
    except Exception:
        return ''

def textext_text(text):
    """Convert the source of a LaTeX object into the form TexText
    stores: a \\noskltx prefix is dropped (TexText has its own
    preamble handling) and a \\preamble<c>...<c> prefix is kept as a
    LaTeX comment, to be sorted out by the user."""
    if text.startswith('\\noskltx'):
        text = text[8:]
    if len(text) > 12 and text.startswith('\\preamble'):
        ie = text.find(text[9], 10)
        if ie > 10:
            text = '%' + text[:ie + 1].replace('\n', '\n%') + '\n' \
                   + text[ie + 1:]
    return text


class SVGSaver:

    def __init__(self, document, file, filename, options, inkscape_mode):
        self.document = document
        self.file = file
        self.filename = filename
        self.options = options
        self.inkscape = inkscape_mode
        self.counters = {}
        self.markers = {}
        # ids of the objects that clones refer to
        self.clone_originals = {}

    def new_id(self, prefix):
        count = self.counters.get(prefix, 0) + 1
        self.counters[prefix] = count
        return '%s%d' % (prefix, count)

    def option(self, name, default):
        value = self.options.get(name, default)
        return default if value is None else value

    #
    #   Document structure
    #

    def Save(self):
        doc = self.document
        rect = None
        if self.option('box', 0):
            rect = doc.BoundingRect(visible = 0, printable = 1)
        if rect is None:
            rect = doc.PageRect()
        left, bottom, right, top = rect
        width = right - left
        height = top - bottom
        self.rect = rect
        # document (pt, y up) -> SVG user space (pt, y down)
        self.trafo = Trafo(1, 0, 0, -1, -left, top)

        root = self.root = ET.Element(svg('svg'))
        root.set('version', '1.1')
        root.set('width', num(width) + 'pt')
        root.set('height', num(height) + 'pt')
        root.set('viewBox', nums(0, 0, width, height))
        root.set('stroke-miterlimit', num(MITER_LIMIT))
        if self.inkscape:
            root.set(inkscape('version'), '1.4')
            root.set(skencil('version'), SketchVersion)
        self.defs = ET.SubElement(root, svg('defs'))
        if self.inkscape:
            self.write_namedview(root)
            self.find_clones()

        for layer in doc.Layers():
            if layer.is_SpecialLayer:
                continue
            if self.inkscape:
                group = ET.SubElement(root, svg('g'))
                group.set('id', self.new_id('layer'))
                group.set(inkscape('groupmode'), 'layer')
                group.set(inkscape('label'), layer.Name())
                if not layer.Visible():
                    group.set('style', 'display:none')
                if layer.Locked():
                    group.set(sodipodi('insensitive'), 'true')
                group.set(skencil('printable'), str(int(layer.Printable())))
                if layer.Outlined():
                    group.set(skencil('outlined'), '1')
            elif layer.Printable():
                group = ET.SubElement(root, svg('g'))
            else:
                continue
            for obj in layer.GetObjects():
                self.save_object(group, obj)

        if not len(self.defs):
            root.remove(self.defs)
        tree = ET.ElementTree(root)
        if hasattr(ET, 'indent'):
            ET.indent(tree, space = ' ')
        tree.write(self.file, encoding = 'utf-8', xml_declaration = True)

    def write_namedview(self, root):
        doc = self.document
        view = ET.SubElement(root, sodipodi('namedview'))
        view.set('id', 'namedview1')
        view.set(inkscape('document-units'), 'pt')
        left, bottom, right, top = self.rect
        # sodipodi:guide positions are stored y up, relative to the
        # lower left corner of the page
        for guide in doc.GuideLines():
            pos, horizontal = guide.Coordinates()
            elem = ET.SubElement(view, sodipodi('guide'))
            elem.set('id', self.new_id('guide'))
            if horizontal:
                elem.set('position', '%s,%s' % (num(0), num(pos - bottom)))
                elem.set('orientation', '0,1')
            else:
                elem.set('position', '%s,%s' % (num(pos - left), num(0)))
                elem.set('orientation', '1,0')
            elem.set(inkscape('locked'), 'false')
        for layer in doc.Layers():
            if layer.is_GridLayer:
                xorig, yorig, xwidth, ywidth = layer.Geometry()
                grid = ET.SubElement(view, inkscape('grid'))
                grid.set('id', self.new_id('grid'))
                grid.set('type', 'xygrid')
                grid.set('units', 'pt')
                grid.set('originx', num(xorig - left))
                grid.set('originy', num(top - yorig))
                grid.set('spacingx', num(xwidth))
                grid.set('spacingy', num(ywidth))
                grid.set('empspacing', '1')
                color = csscolor(layer.OutlineColor())
                grid.set('color', color)
                grid.set('empcolor', color)
                grid.set('visible', 'true' if layer.Visible() else 'false')
                view.set('showgrid', 'true' if layer.Visible() else 'false')

    def find_clones(self):
        def walk(objects):
            for obj in objects:
                if obj.is_Clone:
                    self.clone_originals[id(obj._original)] = None
                elif obj.is_Compound or obj.is_Plugin:
                    walk(obj.GetObjects())
        for layer in self.document.Layers():
            if not layer.is_SpecialLayer:
                walk(layer.GetObjects())

    #
    #   Objects
    #

    def save_object(self, parent, obj):
        count = len(parent)
        try:
            elem = self.dispatch(parent, obj)
        except Exception:
            warn_tb(USER, _("SVG export: cannot export %s"), obj)
            # drop what was written of the object
            for child in list(parent)[count:]:
                parent.remove(child)
            return
        key = id(obj)
        if elem is not None and key in self.clone_originals:
            # a clone refers to this object; it may have been saved
            # (and assigned the id) already
            ref = self.clone_originals[key]
            if ref is None:
                ref = self.clone_originals[key] = self.new_id('clonesrc')
            elem.set('id', ref)

    def dispatch(self, parent, obj):
        if obj.is_Clone:
            return self.save_clone(parent, obj)
        if obj.is_Plugin:
            return self.save_plugin(parent, obj)
        if obj.is_MaskGroup:
            return self.save_mask_group(parent, obj)
        if obj.is_PathTextGroup:
            return self.save_path_text(parent, obj)
        if obj.is_Compound:
            group = ET.SubElement(parent, svg('g'))
            if self.inkscape:
                if obj.is_Blend:
                    group.set(skencil('blend'), '1')
                elif obj.is_BlendInterpolation:
                    group.set(skencil('blend-steps'), str(obj.Steps()))
            for child in obj.GetObjects():
                self.save_object(group, child)
            return group
        if obj.is_SimpleText:
            return self.save_simple_text(parent, obj)
        if obj.is_Image:
            return self.save_image(parent, obj)
        if obj.is_Eps:
            return self.save_eps(parent, obj)
        if obj.is_Bezier or obj.is_Rectangle or obj.is_Ellipse:
            return self.save_primitive(parent, obj, obj.Properties())
        if obj.is_GuideLine:
            return None
        warn(USER, _("SVG export: objects of type %s are not supported"),
             obj.__class__.__name__)
        return None

    def save_clone(self, parent, obj):
        dx, dy = obj._offset
        transform = 'translate(%s)' % nums(dx, -dy)
        if self.inkscape:
            original = self.clone_originals.get(id(obj._original))
            if original is None:
                # the original has not been saved yet; it gets this
                # id when it is (save_object)
                original = self.new_id('clonesrc')
                self.clone_originals[id(obj._original)] = original
            use = ET.SubElement(parent, svg('use'))
            use.set(XLINK_HREF, '#' + original)
            use.set('transform', transform)
            return use
        group = ET.SubElement(parent, svg('g'))
        group.set('transform', transform)
        self.dispatch(group, obj._original)
        return group

    def save_plugin(self, parent, obj):
        group = ET.SubElement(parent, svg('g'))
        if self.inkscape:
            args = plugin_parameters(obj)
            if args:
                group.set(skencil('plugin'), str(args[0]))
                group.set(skencil('params'), repr(args[1:]))
            if obj.class_name == 'LtxObj':
                group = self.set_textext_attrs(group, obj)
        for child in obj.GetObjects():
            self.save_object(group, child)
        return group

    def set_textext_attrs(self, group, obj):
        text = textext_text(obj.text)
        group.set(textext('version'), TEXTEXT_VERSION)
        group.set(textext('text'),
                  text.encode('unicode_escape').decode('utf-8'))
        group.set(textext('preamble'), find_ltx_preamble(self.document))
        group.set(textext('scale'), num(obj.size / 10.0))
        group.set(textext('alignment'), 'top left')
        group.set(textext('texconverter'), 'pdflatex')
        group.set(textext('pdfconverter'), 'inkscape')
        group.set(textext('stroke-to-path'), '0')
        group.set(textext('inkscapeversion'), '1.4')
        # TexText re-renders at the 10pt base size and places the result
        # with the old node's transform (times new scale / old scale), so
        # the group carries the transform that maps that rendering onto
        # the object: Sketch's trafo and the scale, y down.  The baked
        # children are kept in an inner group with the inverse.
        local = self.trafo(obj.trafo(Scale(obj.size / 10.0)(
            Trafo(1, 0, 0, -1, 0, 0))))
        m11, m21, m12, m22 = local.coeff()[:4]
        group.set('transform', matrix(local))
        group.set(textext('jacobian_sqrt'),
                  num(sqrt(abs(m11 * m22 - m12 * m21))))
        inner = ET.SubElement(group, svg('g'))
        inner.set('transform', matrix(local.inverse()))
        return inner

    def save_mask_group(self, parent, obj):
        objects = obj.GetObjects()
        if not objects:
            return None
        mask = objects[0]
        group = ET.SubElement(parent, svg('g'))
        if self.inkscape:
            group.set(skencil('maskgroup'), '1')
        # like MaskGroup.DrawShape: the fill of the mask is painted
        # below the masked objects, its outline on top of them
        if mask.is_Image:
            self.save_image(group, mask)
        elif mask.has_properties and obj.mask_fill is not None \
                 and obj.mask_fill.HasFill():
            self.save_shape(group, mask, obj.mask_fill)
        clip_id = self.clip_path(self.shape_of(mask))
        clipped = ET.SubElement(group, svg('g'))
        clipped.set('clip-path', 'url(#%s)' % clip_id)
        for child in objects[1:]:
            self.save_object(clipped, child)
        if mask.has_properties and obj.mask_line is not None:
            self.save_shape(group, mask, obj.mask_line)
        if len(group) == 1:
            # just the clipped group: no extra nesting
            group.remove(clipped)
            parent.remove(group)
            parent.append(clipped)
            if self.inkscape:
                clipped.set(skencil('maskgroup'), '1')
            return clipped
        return group

    def save_shape(self, parent, obj, props):
        if obj.is_SimpleText:
            return self.save_simple_text(parent, obj, props)
        if obj.is_PathTextText:
            return self.save_internal_path_text(parent, obj, props)
        return self.save_primitive(parent, obj, props)

    def clip_path(self, shape):
        clip = ET.SubElement(self.defs, svg('clipPath'))
        clip_id = self.new_id('clip')
        clip.set('id', clip_id)
        clip.set('clipPathUnits', 'userSpaceOnUse')
        for tag, attrs in shape.items:
            elem = ET.SubElement(clip, svg(tag), attrs)
            if shape.local is not None and 'transform' not in attrs:
                elem.set('transform', matrix(shape.local))
            elem.set('style', 'clip-rule:' + shape.fill_rule)
        return clip_id

    def shape_of(self, obj):
        """Return the Shape of OBJ for clipping."""
        if obj.is_Image:
            w, h = obj.data.Size()
            trafo = self.trafo(obj.trafo)
            points = [trafo(x, y) for x, y in ((0, 0), (w, 0), (w, h), (0, h))]
            return Shape([('path', {'d': polygon_data(points)})])
        if obj.is_SimpleText:
            return self.text_shape(obj)
        if obj.is_PathTextText:
            return self.path_text_shape(obj)
        return self.primitive_shape(obj, arrows = 0)

    #
    #   Primitives
    #

    def primitive_shape(self, obj, arrows = 1):
        """Return the Shape of the Bezier, Rectangle or Ellipse OBJ.
        Simple primitives become the corresponding SVG elements."""
        trafo = self.trafo
        if obj.is_Rectangle:
            shape = self.rect_shape(obj)
            if shape is not None:
                return shape
        elif obj.is_Ellipse:
            shape = self.ellipse_shape(obj, arrows)
            if shape is not None:
                return shape
        if obj.is_Bezier and obj.apaths:
            paths = obj.apaths
        else:
            paths = obj.Paths()
        return Shape([('path', {'d': path_data(paths, trafo)})])

    def rect_shape(self, obj):
        m11, m21, m12, m22, v1, v2 = self.trafo(obj.trafo).coeff()
        frame = orthonormal_frame((m11, m21), (m12, m22))
        if frame is None:
            return None
        u1, u2, l1, l2 = frame
        attrs = {}
        if obj.radius1 or obj.radius2:
            rx = obj.radius1 * l1; ry = obj.radius2 * l2
        else:
            rx = ry = 0
        local = None
        if is_unit(u1[1], u1[0]) and is_unit(u2[0], u2[1]):
            # axis aligned
            x0 = min(v1, v1 + m11); y0 = min(v2, v2 + m22)
            attrs.update(x = num(x0), y = num(y0),
                         width = num(l1), height = num(l2))
        elif is_unit(u1[0], u1[1]) and is_unit(u2[1], u2[0]):
            # axis aligned, the axes swapped
            x0 = min(v1, v1 + m12); y0 = min(v2, v2 + m21)
            attrs.update(x = num(x0), y = num(y0),
                         width = num(l2), height = num(l1))
            rx, ry = ry, rx
        else:
            local = Trafo(u1[0], u1[1], u2[0], u2[1], v1, v2)
            attrs.update(x = '0', y = '0', width = num(l1), height = num(l2))
            attrs['transform'] = matrix(local)
        if rx or ry:
            attrs.update(rx = num(rx), ry = num(ry))
        return Shape([('rect', attrs)], local)

    def ellipse_shape(self, obj, arrows):
        trafo = self.trafo(obj.trafo)
        m11, m21, m12, m22, cx, cy = trafo.coeff()
        frame = ellipse_frame(m11, m21, m12, m22)
        if frame is None:
            return None
        u1, u2, s1, s2, phi = frame
        start, end = obj.start_angle, obj.end_angle
        if start == end:
            # full ellipse
            attrs = {}
            local = None
            if is_unit(u1[1], u1[0]) and is_unit(u2[0], u2[1]):
                rx, ry = s1, s2
            elif is_unit(u1[0], u1[1]) and is_unit(u2[1], u2[0]):
                rx, ry = s2, s1
            else:
                local = Trafo(u1[0], u1[1], u2[0], u2[1], cx, cy)
                rx, ry = s1, s2
            if local is None:
                attrs.update(cx = num(cx), cy = num(cy))
            else:
                attrs.update(cx = '0', cy = '0', transform = matrix(local))
            if abs(rx - ry) < 1e-6:
                attrs['r'] = num(rx)
                return Shape([('circle', attrs)], local)
            attrs.update(rx = num(rx), ry = num(ry))
            return Shape([('ellipse', attrs)], local)
        if not self.inkscape or (arrows and self.has_arrows(obj)):
            return None
        # an Inkscape arc: keeps the arc editable.  In the frame of the
        # ellipse axes the parameter is the Sketch angle minus phi.
        local = Trafo(u1[0], u1[1], u2[0], u2[1], cx, cy)
        attrs = {'d': path_data(obj.Paths(), local.inverse()(self.trafo)),
                 'transform': matrix(local)}
        attrs[sodipodi('type')] = 'arc'
        attrs[sodipodi('cx')] = '0'
        attrs[sodipodi('cy')] = '0'
        attrs[sodipodi('rx')] = num(s1)
        attrs[sodipodi('ry')] = num(s2)
        attrs[sodipodi('start')] = repr((start - phi) % (2 * pi))
        attrs[sodipodi('end')] = repr((end - phi) % (2 * pi))
        arc_type = obj.arc_type
        attrs[sodipodi('arc-type')] = {const.ArcArc: 'arc',
                                       const.ArcChord: 'chord',
                                       const.ArcPieSlice: 'slice'}[arc_type]
        if arc_type != const.ArcPieSlice:
            attrs[sodipodi('open')] = 'true'
        return Shape([('path', attrs)], local)

    def has_arrows(self, obj):
        props = obj.Properties()
        return props.HasLine() and \
               (props.line_arrow1 is not None or props.line_arrow2 is not None)

    def save_primitive(self, parent, obj, props):
        rect = obj.bounding_rect
        shape = self.primitive_shape(obj)
        arrow_items = []
        markers = {}
        if props.HasLine() and props.line_width > 0 \
           and (props.line_arrow1 is not None
                or props.line_arrow2 is not None):
            arrow_items = self.arrow_positions(obj, props)
            if self.inkscape and len(shape.items) == 1 \
               and shape.items[0][0] == 'path' and len(arrow_items) <= 2 \
               and self.single_open_path(obj):
                for which, arrow, pos, dir in arrow_items:
                    markers[which] = self.marker(arrow, props, which)
                arrow_items = []
        style = self.make_style(props, rect, shape)
        for which, marker_id in markers.items():
            style.append((which, 'url(#%s)' % marker_id))
        if arrow_items:
            group = ET.SubElement(parent, svg('g'))
            self.emit_shape(group, shape, style, props, rect)
            for which, arrow, pos, dir in arrow_items:
                self.emit_arrow(group, arrow, props, pos, dir)
            return group
        return self.emit_shape(parent, shape, style, props, rect)

    def single_open_path(self, obj):
        if obj.is_Ellipse:
            return obj.arc_type == const.ArcArc
        paths = obj.Paths()
        return len(paths) == 1 and not paths[0].closed and paths[0].len > 1

    def emit_shape(self, parent, shape, style, props, rect, group = 0):
        """Create the element(s) of SHAPE painted with STYLE, in a
        group if there are several items or GROUP is true.  A conical
        gradient fill, which SVG cannot express, is drawn as wedges
        clipped to the shape.  Return the outermost element."""
        outer = None
        if props.HasFill() and props.fill_pattern.is_ConicalGradient:
            outer = ET.SubElement(parent, svg('g'))
            wedges = ET.SubElement(outer, svg('g'))
            self.emit_conical(wedges, shape, props.fill_pattern, rect)
            style = [item for item in style if item[0] != 'fill'] \
                    + [('fill', 'none')]
            if not props.HasLine():
                for key, value in shape.attrs.items():
                    outer.set(key, value)
                return outer
            parent = outer
        if len(shape.items) == 1 and not group:
            tag, attrs = shape.items[0]
            elem = ET.SubElement(parent, svg(tag), attrs)
            for key, value in shape.attrs.items():
                elem.set(key, value)
        else:
            elem = ET.SubElement(parent, svg('g'), shape.attrs)
            for tag, attrs in shape.items:
                ET.SubElement(elem, svg(tag), attrs)
        elem.set('style', style_string(style))
        return outer if outer is not None else elem

    #
    #   Paint
    #

    def make_style(self, props, rect, shape, line = 1):
        style = []
        if props.HasFill():
            pattern = props.fill_pattern
            paint = self.fill_paint(pattern, rect, shape.local)
            style.append(('fill', paint))
            style.append(('fill-rule', shape.fill_rule))
        else:
            style.append(('fill', 'none'))
        if line and props.HasLine():
            pattern = props.line_pattern
            if pattern.is_Solid:
                color = csscolor(pattern.Color())
            else:
                color = '#000000'
            style.append(('stroke', color))
            width = props.line_width
            style.append(('stroke-width', num(width or HAIRLINE_WIDTH)))
            if props.line_join != const.JoinMiter:
                style.append(('stroke-linejoin',
                              ('miter', 'round', 'bevel')[props.line_join]))
            if props.line_cap != const.CapButt:
                style.append(('stroke-linecap',
                              (None, 'butt', 'round', 'square')[props.line_cap]))
            if props.line_dashes:
                factor = max(width, 1)
                dashes = [max(factor * dash, 0.001)
                          for dash in props.line_dashes]
                style.append(('stroke-dasharray',
                              ','.join(map(num, dashes))))
        else:
            style.append(('stroke', 'none'))
        return style

    def fill_paint(self, pattern, rect, local):
        if pattern.is_Solid:
            return csscolor(pattern.Color())
        if pattern.is_AxialGradient:
            return 'url(#%s)' % self.linear_gradient(pattern, rect, local)
        if pattern.is_RadialGradient:
            return 'url(#%s)' % self.radial_gradient(pattern, rect, local)
        if pattern.is_ConicalGradient:
            # drawn separately (emit_conical)
            return 'none'
        if pattern.is_Hatching:
            return self.hatching(pattern, rect, local)
        if pattern.is_Tiled:
            return 'url(#%s)' % self.image_tile(pattern, rect, local)
        return '#000000'

    def paint_transform(self, elem, attr, trafo, local):
        """Set the transformation attribute ATTR of a paint server to
        TRAFO (from its own coordinates to the user space) for an
        element whose coordinate system is LOCAL."""
        if local is not None:
            trafo = local.inverse()(trafo)
        if trafo.coeff() != (1, 0, 0, 1, 0, 0):
            elem.set(attr, matrix(trafo))

    def gradient_stops(self, elem, colors):
        for pos, color in colors:
            stop = ET.SubElement(elem, svg('stop'))
            stop.set('offset', num(pos))
            stop.set('style', 'stop-color:' + csscolor(color))

    def linear_gradient(self, pattern, rect, local):
        # see LinearGradient.execute_axial_gradient
        vx, vy = pattern.Direction()
        angle = atan2(vy, vx) - pi / 2
        center = rect.center()
        rot = Rotation(angle, center)
        left, bottom, right, top = rot(rect)
        height = (top - bottom) * (1.0 - pattern.Border())
        trafo = rot(Translation(center))
        x1, y1 = trafo(0, height / 2)
        x2, y2 = trafo(0, -height / 2)
        elem = ET.SubElement(self.defs, svg('linearGradient'))
        grad_id = self.new_id('linearGradient')
        elem.set('id', grad_id)
        elem.set('gradientUnits', 'userSpaceOnUse')
        elem.set('x1', num(x1)); elem.set('y1', num(y1))
        elem.set('x2', num(x2)); elem.set('y2', num(y2))
        self.paint_transform(elem, 'gradientTransform', self.trafo, local)
        self.gradient_stops(elem, pattern.Gradient().Colors())
        return grad_id

    def radial_gradient(self, pattern, rect, local):
        # see RadialGradient.execute_radial
        cx, cy = pattern.Center()
        cx = cx * rect.right + (1 - cx) * rect.left
        cy = cy * rect.top   + (1 - cy) * rect.bottom
        radius = max(hypot(rect.left - cx, rect.top - cy),
                     hypot(rect.right - cx, rect.top - cy),
                     hypot(rect.right - cx, rect.bottom - cy),
                     hypot(rect.left - cx, rect.bottom - cy))
        radius = radius * (1.0 - pattern.Border())
        elem = ET.SubElement(self.defs, svg('radialGradient'))
        grad_id = self.new_id('radialGradient')
        elem.set('id', grad_id)
        elem.set('gradientUnits', 'userSpaceOnUse')
        elem.set('cx', num(cx)); elem.set('cy', num(cy))
        elem.set('fx', num(cx)); elem.set('fy', num(cy))
        elem.set('r', num(radius))
        self.paint_transform(elem, 'gradientTransform', self.trafo, local)
        # the gradient runs from the outer circle (0) to the center (1)
        colors = [(1.0 - pos, color)
                  for pos, color in pattern.Gradient().Colors()]
        colors.reverse()
        self.gradient_stops(elem, colors)
        return grad_id

    def emit_conical(self, parent, shape, pattern, rect):
        # wedges like the fallback in ConicalGradient.Execute
        clip_id = self.clip_path(shape)
        parent.set('clip-path', 'url(#%s)' % clip_id)
        if self.inkscape:
            parent.set(skencil('conical-gradient'), '1')
        steps = CONICAL_STEPS
        cx, cy = pattern.Center()
        left, bottom, right, top = rect
        cx = cx * right + (1 - cx) * left
        cy = cy * top + (1 - cy) * bottom
        vx, vy = pattern.Direction()
        angle = atan2(vy, vx)
        radius = max(hypot(left - cx, top - cy),
                     hypot(right - cx, top - cy),
                     hypot(right - cx, bottom - cy),
                     hypot(left - cx, bottom - cy)) + 10
        trafo = self.trafo(Rotation(angle, cx, cy)(Translation(cx, cy))
                           (Scale(radius)))
        colors = pattern.Gradient().Sample(steps)
        colors.reverse()
        da = pi / steps
        points = [(1, 0)]
        for i in range(steps):
            a = da * (i + 1)
            x = cos(a); y = sin(a)
            points.insert(0, (x, y))
            points.append((x, -y))
        polygons = [list(points)]
        points.insert(0, (0, 0))
        for i in range(steps - 1):
            del points[1]
            del points[-1]
            polygons.append(list(points))
        for color, polygon in zip(colors, polygons):
            elem = ET.SubElement(parent, svg('path'))
            elem.set('d', polygon_data([trafo(x, y) for x, y in polygon]))
            elem.set('style', 'fill:%s;stroke:none' % csscolor(color))

    def hatching(self, pattern, rect, local):
        spacing = pattern.Spacing()
        if spacing <= 0:
            return csscolor(pattern.Foreground())
        width = pattern.Width() or HAIRLINE_WIDTH
        if width >= spacing:
            return csscolor(pattern.Foreground())
        # see HatchingPattern.Execute: lines parallel to the direction,
        # spacing apart, one at the top of the rotated bounding box
        vx, vy = pattern.Direction()
        angle = atan2(vy, vx)
        center = rect.center()
        rot = Rotation(angle, center)
        left, bottom, right, top = rot(rect)
        height = top - bottom
        offset = height / 2 - spacing / 2
        trafo = self.trafo(rot(Translation(center)(Translation(0, offset))))
        elem = ET.SubElement(self.defs, svg('pattern'))
        pat_id = self.new_id('hatch')
        elem.set('id', pat_id)
        elem.set('patternUnits', 'userSpaceOnUse')
        elem.set('x', '0'); elem.set('y', '0')
        elem.set('width', num(spacing)); elem.set('height', num(spacing))
        self.paint_transform(elem, 'patternTransform', trafo, local)
        bg = ET.SubElement(elem, svg('rect'))
        bg.set('x', '0'); bg.set('y', '0')
        bg.set('width', num(spacing)); bg.set('height', num(spacing))
        bg.set('style', 'fill:%s;stroke:none' % csscolor(pattern.Background()))
        line = ET.SubElement(elem, svg('rect'))
        line.set('x', '0'); line.set('y', num((spacing - width) / 2))
        line.set('width', num(spacing)); line.set('height', num(width))
        line.set('style', 'fill:%s;stroke:none' % csscolor(pattern.Foreground()))
        return 'url(#%s)' % pat_id

    def image_tile(self, pattern, rect, local):
        # see ImageTilePattern.Execute and the tileimage2 PS procedure:
        # the tile pixel (col, row) is mapped to trafo(col, row)
        data = pattern.data
        w, h = data.Size()
        trafo = self.trafo(Translation(rect.left, rect.top)(pattern.trafo))
        elem = ET.SubElement(self.defs, svg('pattern'))
        pat_id = self.new_id('tile')
        elem.set('id', pat_id)
        elem.set('patternUnits', 'userSpaceOnUse')
        elem.set('x', '0'); elem.set('y', '0')
        elem.set('width', str(w)); elem.set('height', str(h))
        self.paint_transform(elem, 'patternTransform', trafo, local)
        image = ET.SubElement(elem, svg('image'))
        image.set('width', str(w)); image.set('height', str(h))
        image.set('preserveAspectRatio', 'none')
        image.set('style', 'image-rendering:optimizeSpeed')
        image.set(XLINK_HREF, self.image_data_uri(data))
        return pat_id

    #
    #   Arrows
    #

    def arrow_positions(self, obj, props):
        """Return a list of (marker property, arrow, position,
        direction) of the arrow heads of OBJ, as computed by
        CommonDevice.draw_arrows and draw_ellipse_arrows."""
        arrow1 = props.line_arrow1
        arrow2 = props.line_arrow2
        result = []
        if obj.is_Ellipse:
            if obj.arc_type == const.ArcArc \
               and obj.start_angle != obj.end_angle:
                trafo = obj.trafo
                if arrow1 is not None:
                    angle = obj.start_angle
                    result.append(('marker-start', arrow1,
                                   trafo(Point(cos(angle), sin(angle))),
                                   trafo.DTransform(Point(cos(angle - pi / 2),
                                                          sin(angle - pi / 2)))))
                if arrow2 is not None:
                    angle = obj.end_angle
                    result.append(('marker-end', arrow2,
                                   trafo(Point(cos(angle), sin(angle))),
                                   trafo.DTransform(Point(cos(angle + pi / 2),
                                                          sin(angle + pi / 2)))))
            return result
        if not obj.is_Bezier:
            return result
        from Sketch import Bezier
        for path in obj.apaths or obj.paths:
            if path.closed or path.len <= 1:
                continue
            if arrow1 is not None:
                type, controls, p3, cont = path.Segment(1)
                p = path.Node(0)
                if type == Bezier:
                    p1, p2 = controls
                    dir = p - p1
                    if not abs(dir):
                        dir = p - p2
                else:
                    dir = p - p3
                result.append(('marker-start', arrow1, p, dir))
            if arrow2 is not None:
                type, controls, p, cont = path.Segment(-1)
                p3 = path.Node(-2)
                if type == Bezier:
                    p1, p2 = controls
                    dir = p - p2
                    if not abs(dir):
                        dir = p - p1
                else:
                    dir = p - p3
                result.append(('marker-end', arrow2, p, dir))
        return result

    def arrow_style(self, arrow, props, width):
        color = csscolor(props.line_pattern.Color()) \
                if props.line_pattern.is_Solid else '#000000'
        if arrow.IsFilled():
            return 'fill:%s;fill-rule:evenodd;stroke:none' % color
        style = [('fill', 'none'), ('stroke', color),
                 ('stroke-width', num(width))]
        if props.line_join != const.JoinMiter:
            style.append(('stroke-linejoin',
                          ('miter', 'round', 'bevel')[props.line_join]))
        if props.line_cap != const.CapButt:
            style.append(('stroke-linecap',
                          (None, 'butt', 'round', 'square')[props.line_cap]))
        return style_string(style)

    def emit_arrow(self, parent, arrow, props, pos, dir):
        # see CommonDevice.draw_arrow
        width = props.line_width
        angle = dir.polar()[1]
        trafo = self.trafo(Translation(pos)(Rotation(angle)(Scale(width))))
        elem = ET.SubElement(parent, svg('path'))
        elem.set('d', path_data(arrow.Paths(), trafo))
        elem.set('style', self.arrow_style(arrow, props, width))
        return elem

    def marker(self, arrow, props, which):
        """Return the id of a marker drawing ARROW for the line
        properties PROPS at the start or the end of a path."""
        key = (which, repr(arrow.SaveRepr()),
               self.arrow_style(arrow, props, 1))
        marker_id = self.markers.get(key)
        if marker_id is not None:
            return marker_id
        marker_id = self.new_id('Arrow')
        self.markers[key] = marker_id
        elem = ET.SubElement(self.defs, svg('marker'))
        elem.set('id', marker_id)
        elem.set('orient', 'auto')
        elem.set('markerUnits', 'strokeWidth')
        elem.set('refX', '0'); elem.set('refY', '0')
        elem.set('markerWidth', '1'); elem.set('markerHeight', '1')
        elem.set('style', 'overflow:visible')
        if self.inkscape:
            elem.set(inkscape('stockid'), marker_id)
            elem.set(inkscape('isstock'), 'true')
        # The marker's x axis is the direction of the path, in the y
        # down user space.  An arrow points along its +x axis in Sketch
        # (y up), and at the start of a path it points backwards.
        if which == 'marker-start':
            trafo = Trafo(-1, 0, 0, 1, 0, 0)
        else:
            trafo = Trafo(1, 0, 0, -1, 0, 0)
        path = ET.SubElement(elem, svg('path'))
        path.set('d', path_data(arrow.Paths(), trafo))
        path.set('style', self.arrow_style(arrow, props, 1))
        return marker_id

    #
    #   Text
    #

    def text_shape(self, obj):
        """The glyph outlines of the SimpleText OBJ (see
        SimpleText.Paths)."""
        props = obj.Properties()
        font = props.font
        size = props.font_size
        text = obj.Text()
        base = self.trafo(obj.trafo(obj.atrafo))(Scale(size))
        pos = font.TypesetText(text)
        items = []
        for i in range(len(text)):
            outline = font.GetOutline(text[i])
            if outline:
                items.append(('path', {'d': path_data(
                    outline, base(Translation(pos[i])))}))
        return Shape(items, fill_rule = 'nonzero')

    def text_metadata(self, obj, shape):
        props = obj.Properties()
        attrs = shape.attrs
        attrs['aria-label'] = obj.TextAsUnicode()
        attrs[skencil('text')] = obj.TextAsUnicode()
        attrs[skencil('font')] = props.font.PostScriptName()
        attrs[skencil('size')] = num(props.font_size)
        attrs[skencil('halign')] = str(obj.halign)
        attrs[skencil('valign')] = str(obj.valign)
        attrs[skencil('trafo')] = nums(*obj.trafo.coeff())

    def save_simple_text(self, parent, obj, props = None):
        if props is None:
            props = obj.Properties()
        if not props.HasFill() or not len(obj.Text()):
            return None
        if self.inkscape and self.option('text', 0):
            elem = self.save_text_element(parent, obj, props)
            if elem is not None:
                return elem
        shape = self.text_shape(obj)
        if not shape.items:
            return None
        if self.inkscape:
            self.text_metadata(obj, shape)
        style = self.make_style(props, obj.bounding_rect, shape, line = 0)
        # a text is a group of glyphs, even for a single glyph
        return self.emit_shape(parent, shape, style, props,
                               obj.bounding_rect, group = 1)

    def save_text_element(self, parent, obj, props):
        """Save OBJ as an editable SVG text element.  The glyphs are
        positioned individually, at the positions Sketch computes.
        Return None if the text cannot be represented this way."""
        font = props.font
        text = obj.Text()
        chars = []
        for gid in text:
            char = glyphnames.glyphname_to_unicode(font.GlyphName(gid))
            if char is None or char in '\n\r':
                return None
            chars.append(char)
        if props.fill_pattern.is_ConicalGradient:
            return None
        size = props.font_size
        local = self.trafo(obj.trafo(obj.atrafo))(Trafo(1, 0, 0, -1, 0, 0))
        pos = font.TypesetText(text)
        shape = Shape([], local, 'nonzero')
        style = font_style(font, size) \
                + self.make_style(props, obj.bounding_rect, shape, line = 0)
        elem = ET.SubElement(parent, svg('text'))
        elem.set('{http://www.w3.org/XML/1998/namespace}space', 'preserve')
        elem.set('transform', matrix(local))
        elem.set('x', ' '.join([num(size * p.x) for p in pos[:len(chars)]]))
        elem.set('y', '0')
        elem.set('style', style_string(style))
        elem.text = ''.join(chars)
        elem.set(skencil('font'), font.PostScriptName())
        elem.set(skencil('halign'), str(obj.halign))
        elem.set(skencil('valign'), str(obj.valign))
        elem.set(skencil('trafo'), nums(*obj.trafo.coeff()))
        return elem

    def path_text_shape(self, obj):
        """The glyph outlines of the InternalPathText OBJ."""
        props = obj.Properties()
        font = props.font
        size = props.font_size
        text = obj.Text()
        items = []
        for idx, trafo in enumerate(obj.CharacterTransformations()):
            gid = text[idx]
            if gid in (font_module.NEWLINE_GID,
                       font_module.CARRIAGE_RETURN_GID):
                continue
            outline = font.GetOutline(gid)
            if outline:
                items.append(('path', {'d': path_data(
                    outline, self.trafo(trafo(Scale(size))))}))
        # PostScriptDevice clips procedural fills of path text with
        # eoclip
        rule = 'evenodd' if props.fill_pattern.is_procedural \
               else 'nonzero'
        return Shape(items, fill_rule = rule)

    def save_internal_path_text(self, parent, obj, props = None):
        if props is None:
            props = obj.Properties()
        if not props.HasFill():
            return None
        shape = self.path_text_shape(obj)
        if not shape.items:
            return None
        if self.inkscape:
            shape.attrs['aria-label'] = obj.TextAsUnicode()
            shape.attrs[skencil('text')] = obj.TextAsUnicode()
            shape.attrs[skencil('font')] = props.font.PostScriptName()
            shape.attrs[skencil('size')] = num(props.font_size)
        style = self.make_style(props, obj.bounding_rect, shape, line = 0)
        return self.emit_shape(parent, shape, style, props,
                               obj.bounding_rect, group = 1)

    def save_path_text(self, parent, obj):
        group = ET.SubElement(parent, svg('g'))
        if self.inkscape:
            group.set(skencil('pathtext'), '1')
        for child in obj.GetObjects():
            if child.is_PathTextText:
                self.save_internal_path_text(group, child)
            else:
                self.save_object(group, child)
        return group

    #
    #   Images and EPS
    #

    def image_data_uri(self, data):
        filename = data.Filename()
        if filename and os.path.isfile(filename):
            ext = os.path.splitext(filename)[1].lower()
            mime = {'.png': 'image/png', '.jpg': 'image/jpeg',
                    '.jpeg': 'image/jpeg'}.get(ext)
            if mime:
                with open(filename, 'rb') as f:
                    encoded = base64.b64encode(f.read()).decode('ascii')
                return 'data:%s;base64,%s' % (mime, encoded)
        buffer = io.BytesIO()
        data.Image().save(buffer, 'PNG')
        return 'data:image/png;base64,' \
               + base64.b64encode(buffer.getvalue()).decode('ascii')

    def link_or_embed(self, elem, data):
        filename = data.Filename()
        if self.inkscape and self.option('images', 0) and filename:
            absname = os.path.abspath(filename)
            try:
                href = os.path.relpath(absname,
                                       os.path.dirname(os.path.abspath(
                                           self.filename)))
            except ValueError:
                href = absname
            elem.set(XLINK_HREF, href)
            elem.set(sodipodi('absref'), absname)
        else:
            elem.set(XLINK_HREF, self.image_data_uri(data))

    def save_image(self, parent, obj):
        data = obj.data
        w, h = data.Size()
        trafo = self.trafo(obj.trafo(Trafo(1, 0, 0, -1, 0, h)))
        elem = ET.SubElement(parent, svg('image'))
        elem.set('width', str(w)); elem.set('height', str(h))
        elem.set('preserveAspectRatio', 'none')
        elem.set('transform', matrix(trafo))
        elem.set('style', 'image-rendering:optimizeSpeed')
        self.link_or_embed(elem, data)
        return elem

    def save_eps(self, parent, obj):
        data = obj.data
        filename = data.Filename()
        elem = None
        if self.option('eps', 0) == 0:
            try:
                elem = self.eps_vector(parent, obj)
            except Exception as exc:
                warn(USER, _("SVG export: cannot convert %(filename)s "
                             "to SVG: %(error)s\nUsing a raster image."),
                     filename = filename, error = str(exc))
        if elem is None:
            try:
                elem = self.eps_raster(parent, obj)
            except Exception as exc:
                warn(USER, _("SVG export: cannot render %(filename)s: "
                             "%(error)s"),
                     filename = filename, error = str(exc))
        if elem is None:
            elem = self.eps_preview(parent, obj)
        if elem is not None and self.inkscape:
            elem.set(skencil('eps-file'), filename)
        return elem

    def eps_clip(self, obj):
        w, h = obj.data.Size()
        trafo = self.trafo(obj.trafo)
        points = [trafo(x, y) for x, y in ((0, 0), (w, 0), (w, h), (0, h))]
        return self.clip_path(Shape([('path', {'d': polygon_data(points)})]))

    def eps_vector(self, parent, obj):
        data = obj.data
        filename = data.Filename()
        tempdir = tempfile.mkdtemp(prefix = 'skencil-svg-')
        try:
            out = os.path.join(tempdir, 'eps.svg')
            dvisvgm = shutil.which('dvisvgm')
            ok = False
            if dvisvgm:
                result = subprocess.run([dvisvgm, '-E', '--no-fonts',
                                         '-o', out, filename],
                                        stdout = subprocess.PIPE,
                                        stderr = subprocess.PIPE,
                                        timeout = 120)
                ok = result.returncode == 0 and os.path.exists(out)
            if not ok:
                ink = shutil.which('inkscape')
                if not ink:
                    raise SketchError(_("neither dvisvgm nor inkscape "
                                        "can convert the file"))
                subprocess.run([ink, filename, '--export-type=svg',
                                '--export-plain-svg',
                                '--export-filename=' + out],
                               stdout = subprocess.PIPE,
                               stderr = subprocess.PIPE, timeout = 300)
                if not os.path.exists(out):
                    raise SketchError(_("conversion failed"))
            tree = ET.parse(out)
        finally:
            shutil.rmtree(tempdir, ignore_errors = True)
        root = tree.getroot()
        # map the converter's view box to the EPS bounding box
        w, h = data.Size()
        box = root.get('viewBox')
        if box:
            vx, vy, vw, vh = [float(v) for v in
                              box.replace(',', ' ').split()]
        else:
            vx = vy = 0
            vw = svg_length(root.get('width'))
            vh = svg_length(root.get('height'))
        if not vw or not vh:
            raise SketchError(_("the converted file has no size"))
        sx = w / vw; sy = h / vh
        local = self.trafo(obj.trafo(Trafo(sx, 0, 0, -sy,
                                           -vx * sx, h + vy * sy)))
        outer = ET.SubElement(parent, svg('g'))
        outer.set('clip-path', 'url(#%s)' % self.eps_clip(obj))
        group = ET.SubElement(outer, svg('g'))
        group.set('transform', matrix(local))
        prefix = self.new_id('eps') + '-'
        for child in list(root):
            if child.tag in (svg('metadata'), svg('title'),
                             sodipodi('namedview')):
                continue
            group.append(child)
        prefix_ids(group, prefix)
        return outer

    def eps_raster(self, parent, obj):
        data = obj.data
        dpi = int(self.option('eps_dpi', 300))
        llx, lly = data.Start()
        w, h = data.Size()
        factor = dpi / 72.0
        pw = int(max(1, round(w * factor)))
        ph = int(max(1, round(h * factor)))
        tempdir = tempfile.mkdtemp(prefix = 'skencil-svg-')
        try:
            out = os.path.join(tempdir, 'eps.png')
            # like eps.render_preview, with transparency
            util.run_gs(['-sDEVICE=pngalpha', '-r%d' % dpi,
                         '-dNOPAUSE', '-dSAFER', '-q',
                         '-dTextAlphaBits=4', '-dGraphicsAlphaBits=4',
                         '-sOutputFile=' + out,
                         '-g%dx%d' % (pw, ph),
                         '-c', '%f' % -llx, '%f' % -lly, 'translate',
                         '/oldshowpage /showpage load def',
                         '/showpage {} def',
                         '-f', data.Filename(), '-c', 'oldshowpage quit'])
            if not os.path.exists(out):
                raise SketchError(_("ghostscript produced no output"))
            with open(out, 'rb') as f:
                png = f.read()
        finally:
            shutil.rmtree(tempdir, ignore_errors = True)
        href = 'data:image/png;base64,' + base64.b64encode(png).decode('ascii')
        return self.eps_image(parent, obj, href, pw, ph, pw / factor,
                              ph / factor)

    def eps_preview(self, parent, obj):
        image = obj.data.image
        if image is None:
            return None
        from Sketch.Graphics.image import image_to_pil
        pil = image_to_pil(image.mode, image.size, image.data)
        buffer = io.BytesIO()
        pil.save(buffer, 'PNG')
        href = 'data:image/png;base64,' \
               + base64.b64encode(buffer.getvalue()).decode('ascii')
        factor = config.preferences.eps_preview_resolution / 72.0
        pw, ph = image.size
        return self.eps_image(parent, obj, href, pw, ph, pw / factor,
                              ph / factor)

    def eps_image(self, parent, obj, href, pw, ph, width, height):
        # the image covers the rectangle (0, 0, width, height) of the
        # EPS bounding box coordinates, its first row at the top
        trafo = self.trafo(obj.trafo(Trafo(width / pw, 0, 0, -height / ph,
                                           0, height)))
        outer = ET.SubElement(parent, svg('g'))
        outer.set('clip-path', 'url(#%s)' % self.eps_clip(obj))
        elem = ET.SubElement(outer, svg('image'))
        elem.set('width', str(pw)); elem.set('height', str(ph))
        elem.set('preserveAspectRatio', 'none')
        elem.set('transform', matrix(trafo))
        elem.set(XLINK_HREF, href)
        return outer


_length_units = {'': 1.0, 'pt': 1.0, 'px': 0.75, 'mm': 72 / 25.4,
                 'cm': 72 / 2.54, 'in': 72.0, 'pc': 12.0}

def svg_length(value):
    """Return the SVG length VALUE in pt (0 if unknown)."""
    if not value:
        return 0
    match = re.match(r'\s*([-+0-9.eE]+)\s*([a-z]*)', value)
    if not match or match.group(2) not in _length_units:
        return 0
    return float(match.group(1)) * _length_units[match.group(2)]

_url_rx = re.compile(r'url\(\s*#([^)\s]+)\s*\)')

def prefix_ids(root, prefix):
    """Make the ids in the element tree ROOT unique by prefixing them
    with PREFIX, and update the references to them."""
    ids = set()
    for elem in root.iter():
        value = elem.get('id')
        if value:
            ids.add(value)
            elem.set('id', prefix + value)
    def fix_url(match):
        name = match.group(1)
        if name in ids:
            return 'url(#%s)' % (prefix + name)
        return match.group(0)
    for elem in root.iter():
        for key, value in list(elem.attrib.items()):
            if key in (XLINK_HREF, 'href') and value.startswith('#') \
               and value[1:] in ids:
                elem.set(key, '#' + prefix + value[1:])
            elif 'url(' in value:
                elem.set(key, _url_rx.sub(fix_url, value))


def save_svg(document, file, filename, options, inkscape_mode):
    saver = SVGSaver(document, file, filename, options, inkscape_mode)
    saver.Save()

def save(document, file, filename, options = {}):
    save_svg(document, file, filename, options, 1)
