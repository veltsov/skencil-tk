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
# SVG import (see devdocs/svg-import.md).
#
# The import filter Plugins/Filters/svgloader.py uses SVGLoader; other
# code (e.g. plugins converting the output of external tools) can use
# import_svg() and import_svg_group().

import io
import os
import sys

from Sketch import _, SketchLoadError, SketchError
from Sketch.Base.load import GenericLoader
from Sketch.Base.warn import warn_tb, INTERNAL

from . import tree
from .builder import Builder

__all__ = ['SVGLoader', 'import_svg', 'import_svg_group']


def page_layout(width, height):
    """A page layout of WIDTH x HEIGHT points: a standard paper format if
    the size is one."""
    from Sketch.Graphics.pagelayout import PageLayout
    from Sketch.Graphics.papersize import PapersizesList
    from Sketch.Graphics.pagelayout import Portrait, Landscape
    # no rounding noise of the unit conversion (pt -> px -> pt)
    width = round(width, 6)
    height = round(height, 6)
    for name, w, h in PapersizesList:
        if abs(w - width) < 1 and abs(h - height) < 1:
            return PageLayout(name, orientation = Portrait)
        if abs(h - width) < 1 and abs(w - height) < 1:
            return PageLayout(name, orientation = Landscape)
    return PageLayout(width = width, height = height, orientation = Portrait)


class SVGLoader(GenericLoader):

    format_name = 'SVG'

    def __init__(self, file, filename, match, options = None):
        GenericLoader.__init__(self, file, filename, match)
        self.options = options or {}

    def Load(self):
        file = self.file
        try:
            file.seek(0)
            data = file.read()
        except (AttributeError, OSError, io.UnsupportedOperation):
            data = self.match.string.encode('latin-1') + file.read()
        base_dir = self.options.get('base_dir')
        if base_dir is None:
            base_dir = os.path.dirname(self.filename or '')
        return self.load_data(data, base_dir)

    def load_data(self, data, base_dir):
        if isinstance(data, str):
            data = data.encode('utf-8')
        if data[:2] == b'\x1f\x8b':
            import gzip
            data = gzip.decompress(data)
        try:
            root = tree.parse(data)
        except Exception as exc:
            raise SketchLoadError(_("Invalid SVG file: %s") % exc)
        if root.tag != 'svg':
            raise SketchLoadError(_("Not an SVG file"))
        try:
            builder = Builder(root, base_dir, self.add_message,
                              self.options)
            page, layers = builder.build()
        except SketchError:
            raise
        except Exception as exc:
            warn_tb(INTERNAL, 'SVG import')
            raise SketchLoadError(_("Error importing SVG: %s") % exc
                                  ).with_traceback(sys.exc_info()[2])
        self.document()
        if not layers:
            layers = [(None, 1, 0, {}, [])]
        count = 0
        for name, visible, locked, attrs, objects in layers:
            count += 1
            if not name:
                name = _("Layer %d") % count
            self.layer(name, visible, attrs.get('printable', 1), locked,
                       attrs.get('outlined', 0))
            for obj in objects:
                self.append_object(obj)
        if builder.guides:
            from Sketch import GuideLayer, GuideLine, Point
            self.begin_layer_class(GuideLayer, (_("Guide Lines"),))
            for pos, horizontal in builder.guides:
                point = Point(0, pos) if horizontal else Point(pos, 0)
                self.append_object(GuideLine(point, horizontal))
        self.end_all()
        doc = self.object
        if page is not None and self.options.get('page', 1):
            doc.load_SetLayout(page_layout(*page))
        doc.load_Completed()
        return doc


def _read(source):
    if isinstance(source, (bytes, bytearray)):
        return bytes(source), ''
    if isinstance(source, str):
        with open(source, 'rb') as f:
            return f.read(), source
    return source.read(), ''


def import_svg(source, filename = '', base_dir = None, **options):
    """Import the SVG SOURCE (bytes, a file name or a file object) into a
    new document.  Relative image references are resolved against
    BASE_DIR (default: the directory of the file).  OPTIONS: page (set
    the page size, default 1), merge_glyphs (default 0).  The messages
    are in the document's meta.load_messages."""
    data, name = _read(source)
    filename = filename or name
    if base_dir is not None:
        options['base_dir'] = base_dir
    loader = SVGLoader(None, filename, None, options)
    if base_dir is None:
        base_dir = os.path.dirname(filename)
    doc = loader.load_data(data, base_dir)
    messages = loader.Messages()
    if messages:
        doc.meta.load_messages = messages
    return doc


def import_svg_group(source, **kw):
    """Import SOURCE as a single group (None if it is empty).  Returns
    (group, messages)."""
    doc = import_svg(source, **kw)
    messages = doc.meta.load_messages
    group = doc.as_group()
    if group is not None and len(group.GetObjects()) == 1 \
       and group.GetObjects()[0].is_Group:
        # a single layer
        group = group.GetObjects()[0]
        group.parent = None
    return group, messages
