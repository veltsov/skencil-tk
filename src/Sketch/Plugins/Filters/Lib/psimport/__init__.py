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

"""Import of EPS, PostScript and PDF (devdocs/ps-import.md).

An intermediate implementation: PostScript and EPS are converted to PDF
by ghostscript (pdfwrite), each selected PDF page to SVG by poppler's
pdftocairo, and the SVG is imported by svgimport.  It is to be replaced
by a reader of ghostscript-normalized PDF behind the same API.

    doc = import_ps(filename, pages = '1')
    group, messages = import_ps_group(filename, pages = '1')

PAGES selects the pages: `1', `2-4', `1,3,5-', `all'.  Several pages
become layers `Page N' on top of each other (top left corners aligned);
a file of one page ignores PAGES.
"""

import os, re, shutil, struct, subprocess, tempfile, io, weakref

from Sketch import _, SketchLoadError, Translation
from Sketch.Base.load import GenericLoader
from Sketch.Graphics.layer import Layer
from Sketch.Lib import dscparser, util
from Sketch.Plugins.Filters.Lib import svgimport

TIMEOUT = 120

EPS, PS, PDF = 'eps', 'ps', 'pdf'

# the header of an EPS file with a TIFF or WMF preview ("DOS EPS")
DOS_EPS_MAGIC = b'\xc5\xd0\xd3\xc6'


def tool(name, package):
    path = shutil.which(name)
    if path is None:
        raise SketchLoadError(_("%(tool)s not found: importing PostScript "
                                "and PDF needs %(package)s")
                              % {'tool': name, 'package': package})
    return path


def run(command, what):
    """Run COMMAND (a list); raise SketchLoadError with the tail of its
    error output if it fails.  Return its standard output."""
    try:
        result = subprocess.run(command, stdout = subprocess.PIPE,
                                stderr = subprocess.PIPE, timeout = TIMEOUT)
    except subprocess.TimeoutExpired:
        raise SketchLoadError(_("%s did not finish in time") % what)
    except OSError as exc:
        raise SketchLoadError("%s: %s" % (what, exc.strerror))
    if result.returncode != 0:
        output = (result.stderr or result.stdout).decode('utf-8', 'replace')
        output = '\n'.join(output.strip().splitlines()[-6:])
        raise SketchLoadError(_("%(what)s failed:\n%(output)s")
                              % {'what': what, 'output': output})
    return result.stdout.decode('utf-8', 'replace')


def parse_pages(text, count):
    """The sorted page numbers of the page selection TEXT (`1', `2-4',
    `1,3,5-', `all' or empty: all) of a document of COUNT pages.  Raise
    SketchLoadError if it is invalid."""
    text = (text or '').strip().lower()
    if text in ('', 'all', '*'):
        return list(range(1, count + 1))
    pages = set()
    for item in text.replace(' ', ',').split(','):
        if not item:
            continue
        match = re.match(r'^(\d*)\s*(-?)\s*(\d*)$', item)
        if not match or not (match.group(1) or match.group(3)):
            raise SketchLoadError(_("invalid page selection `%s'") % text)
        first = int(match.group(1) or 1)
        if match.group(2):
            last = int(match.group(3) or count)
        else:
            last = first
        if not 1 <= first <= last <= count:
            raise SketchLoadError(_("page selection `%(pages)s' outside "
                                    "the pages 1-%(count)d")
                                  % {'pages': text, 'count': count})
        pages.update(range(first, last + 1))
    if not pages:
        raise SketchLoadError(_("invalid page selection `%s'") % text)
    return sorted(pages)


class Source:

    """A PostScript, EPS or PDF file prepared for the conversion: the
    PDF to convert and its page sizes.  The temporary files are in
    self.dir; call cleanup() when done."""

    def __init__(self, filename = '', data = None):
        self.dir = tempfile.mkdtemp(prefix = 'skencil-ps-')
        # removed also if the import is abandoned (e.g. the options
        # dialog cancelled)
        self.cleanup = weakref.finalize(self, shutil.rmtree, self.dir,
                                        True)
        self.pdf = None
        self.sizes = []
        try:
            if data is not None or not filename \
               or not os.path.isfile(filename):
                # e.g. read from a pipe (gziploader)
                name = os.path.join(self.dir, 'input')
                with open(name, 'wb') as f:
                    f.write(data or b'')
                filename = name
            self.filename = filename
            self.prepare()
        except:
            self.cleanup()
            raise

    def prepare(self):
        with open(self.filename, 'rb') as f:
            head = f.read(64)
        if head.startswith(b'%PDF-'):
            self.kind = PDF
            self.pdf = self.filename
        elif head.startswith(DOS_EPS_MAGIC):
            self.kind = EPS
            self.eps_to_pdf(self.extract_dos_eps())
        elif head.startswith(b'%!'):
            if dscparser.IsEpsFileStart(head.split(b'\n')[0]
                                        .split(b'\r')[0]
                                        .decode('latin-1')):
                self.kind = EPS
                self.eps_to_pdf(self.filename)
            else:
                self.kind = PS
                self.ps_to_pdf(self.filename)
        else:
            raise SketchLoadError(_("not a PostScript or PDF file"))
        self.sizes = self.page_sizes()
        if not self.sizes:
            raise SketchLoadError(_("the file has no pages"))

    def extract_dos_eps(self):
        # the PostScript section of an EPS file with a binary header:
        # magic, offset and length of the PostScript (little endian)
        with open(self.filename, 'rb') as f:
            data = f.read()
        offset, length = struct.unpack('<II', data[4:12])
        name = os.path.join(self.dir, 'section.eps')
        with open(name, 'wb') as f:
            f.write(data[offset:offset + length])
        return name

    def gs(self, args, what):
        gs = util.ghostscript_command()
        if not shutil.which(gs):
            raise SketchLoadError(_("%(tool)s not found: importing "
                                    "PostScript needs ghostscript")
                                  % {'tool': gs})
        self.pdf = os.path.join(self.dir, 'converted.pdf')
        run([gs, '-q', '-dSAFER', '-dBATCH', '-dNOPAUSE',
             '-sDEVICE=pdfwrite', '-sOutputFile=' + self.pdf] + args, what)

    def eps_to_pdf(self, filename):
        # the page is the bounding box (also a trailing one, which
        # -dEPSCrop ignores)
        try:
            info = dscparser.parse_eps_file(filename)
        except (dscparser.DSCError, OSError) as exc:
            raise SketchLoadError(str(exc))
        if not info.BoundingBox:
            raise SketchLoadError(_("the EPS file has no bounding box"))
        llx, lly, urx, ury = info.BoundingBox
        if urx <= llx or ury <= lly:
            raise SketchLoadError(_("the EPS file has an empty bounding "
                                    "box"))
        self.gs(['-dDEVICEWIDTHPOINTS=%g' % (urx - llx),
                 '-dDEVICEHEIGHTPOINTS=%g' % (ury - lly), '-dFIXEDMEDIA',
                 '-c', '<</Install {%g %g translate}>> setpagedevice'
                 % (-llx, -lly),
                 '-f', filename, '-c', 'showpage'], 'ghostscript')

    def ps_to_pdf(self, filename):
        self.gs([filename], 'ghostscript')

    def page_sizes(self):
        output = run([tool('pdfinfo', 'poppler-utils'), '-f', '1',
                      '-l', '100000', self.pdf], 'pdfinfo')
        sizes = []
        for line in output.splitlines():
            match = re.match(r'^Page\s+\d+\s+size:\s+([\d.]+)\s+x\s+([\d.]+)',
                             line)
            if match:
                sizes.append((float(match.group(1)),
                              float(match.group(2))))
        if self.kind == EPS:
            # the extra showpage of eps_to_pdf may add an empty page
            sizes = sizes[:1]
        return sizes

    def description(self):
        count = len(self.sizes)
        width, height = self.sizes[0]
        text = _("%(count)d pages, %(width)g x %(height)g pt") \
               % {'count': count, 'width': width, 'height': height}
        if len(set(self.sizes)) > 1:
            text = text + '\n' + _("(the pages differ in size)")
        text = text + '\n' + _("Pages, e.g.: 2  1-3  1,4-  all\n"
                               "(several pages become layers)")
        return text

    def page_svg(self, page):
        out = os.path.join(self.dir, 'page%d.svg' % page)
        run([tool('pdftocairo', 'poppler-utils'), '-svg',
             '-f', str(page), '-l', str(page), self.pdf, out], 'pdftocairo')
        with open(out, 'rb') as f:
            return f.read()

    def import_pages(self, pages):
        """Import the pages PAGES (a selection text) into a document."""
        count = len(self.sizes)
        numbers = parse_pages(pages, count) if count > 1 else [1]
        doc = None
        messages = []
        top = 0
        for number in numbers:
            page = svgimport.import_svg(self.page_svg(number),
                                        filename = self.filename,
                                        base_dir = self.dir)
            for line in (page.meta.load_messages or '').splitlines():
                if len(numbers) > 1:
                    line = _("Page %(page)d: %(message)s") \
                           % {'page': number, 'message': line}
                messages.append(line)
            if doc is None:
                doc = page
                top = doc.PageSize()[1]
                if len(numbers) > 1:
                    layers = content_layers(doc)
                    objects = take_objects(layers)
                    for layer in layers[1:]:
                        doc.layers.remove(layer)
                    layers[0].SetName(_("Page %d") % number)
                    for obj in objects:
                        layers[0].load_AppendObject(obj)
                    doc.active_layer = layers[0]
                continue
            # the top left corners coincide
            offset = Translation(0, top - page.PageSize()[1])
            objects = take_objects(content_layers(page))
            layer = Layer(_("Page %d") % number)
            for obj in objects:
                obj.Transform(offset)
                layer.load_AppendObject(obj)
            others = content_layers(doc)
            doc.layers.insert(doc.layers.index(others[-1]) + 1, layer)
            layer.SetDocument(doc)
        if len(set(self.sizes[n - 1] for n in numbers)) > 1:
            messages.append(_("The pages differ in size; their top left "
                              "corners are aligned"))
        doc.meta.load_messages = '\n'.join(messages)
        return doc


def content_layers(doc):
    layers = [layer for layer in doc.layers if not layer.is_SpecialLayer]
    if not layers:
        layer = Layer(_("Layer 1"))
        doc.layers.insert(0, layer)
        layer.SetDocument(doc)
        layers = [layer]
    return layers


def take_objects(layers):
    objects = []
    for layer in layers:
        objects.extend(layer.GetObjects())
        layer.objects = []
    for obj in objects:
        obj.parent = None
    return objects


def import_ps(source, pages = '1'):
    """Import SOURCE (a file name, bytes or a file object), the pages
    PAGES of it, into a new document.  The messages are in the
    document's meta.load_messages."""
    if isinstance(source, str):
        src = Source(source)
    elif isinstance(source, (bytes, bytearray)):
        src = Source(data = bytes(source))
    else:
        src = Source(data = source.read())
    try:
        return src.import_pages(pages)
    finally:
        src.cleanup()


def import_ps_group(source, pages = '1'):
    """Import SOURCE as a single group (None if it is empty): a group
    per page if several are selected.  Returns (group, messages)."""
    doc = import_ps(source, pages)
    messages = doc.meta.load_messages
    group = doc.as_group()
    if group is not None and len(group.GetObjects()) == 1 \
       and group.GetObjects()[0].is_Group:
        group = group.GetObjects()[0]
        group.parent = None
    return group, messages


class PSLoader(GenericLoader):

    format_name = 'PostScript/PDF'

    def __init__(self, file, filename, match, options = None):
        GenericLoader.__init__(self, file, filename, match, options)
        self.source = None

    def get_source(self):
        if self.source is None:
            data = None
            if not self.filename or not os.path.isfile(self.filename):
                file = self.file
                try:
                    file.seek(0)
                    data = file.read()
                except (AttributeError, OSError, io.UnsupportedOperation):
                    data = self.match.string.encode('latin-1') + file.read()
            self.source = Source(self.filename, data)
        return self.source

    def OptionInfo(self):
        source = self.get_source()
        if len(source.sizes) < 2:
            return None
        return source.description()

    def Load(self):
        try:
            doc = self.get_source().import_pages(self.options.get('pages',
                                                                  '1'))
        finally:
            if self.source is not None:
                self.source.cleanup()
                self.source = None
        self.messages = {}
        for line in (doc.meta.load_messages or '').splitlines():
            self.add_message(line)
        return doc
