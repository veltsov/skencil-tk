# Sketch - A Python-based interactive drawing program
# Copyright (C) 1997, 1998, 1999, 2000, 2003 by Bernhard Herzog
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

#
#	Font management...
#

import os, re, string
from array import array


import streamfilter

from Sketch import _, Point, TrafoType, Scale, \
     SketchError, SketchInternalError, Subscribe, CreatePath, \
     CreateFontMetric, SKCache
from Sketch.Base import config, const
from Sketch.Lib import encoding
from Sketch.Lib import glyphnames

from Sketch.Base.warn import warn, INTERNAL, USER, pdebug
from Sketch.Lib.util import find_in_path, find_files_in_path, as_unicode

minus_tilde = string.maketrans('-', '~')

def xlfd_matrix(trafo):
    mat = '[%f %f %f %f]' % trafo.matrix()
    return mat.translate(minus_tilde)


def _str(val):
    return val.strip()

def _bb(val):
    return tuple(map(int, map(round, map(float, val.strip().split()))))

def _number(val):
    return int(round(float(val)))

converters = {
    'EncodingScheme':	_str,
    'Ascender':		_number,
    'Descender':	_number,
    'ItalicAngle':	float,
    'FontBBox':		_bb,
    'StartCharMetrics':	None,
    'EndFontMetrics':	None
}

StandardEncoding = 'AdobeStandardEncoding'


#
# The global glyph registry (see devdocs/glyph-text.md)
#
# Glyph names are mapped to small, session-local integer ids.  The
# registry grows as fonts are loaded (read_afm_file registers every
# glyph of a font).  Indices are never serialized: files store glyph
# names or font-encoding codes.

class GlyphRegistry:

    def __init__(self):
        self.names = []
        self._indices = {}

    def index(self, name):
        """Return the id of NAME, registering it if necessary."""
        idx = self._indices.get(name)
        if idx is None:
            idx = len(self.names)
            self.names.append(name)
            self._indices[name] = idx
        return idx

    def name(self, index):
        """Return the glyph name for the id INDEX."""
        return self.names[index]

    def __len__(self):
        return len(self.names)


glyph_registry = GlyphRegistry()

# reserved ids. `.notdef' must be 0; the control-code names exist
# because historical .sk files contain \n / \r bytes inside quoted
# txt()/pt() strings.
NOTDEF_GID = glyph_registry.index(encoding.notdef)		# 0
NEWLINE_GID = glyph_registry.index(glyphnames.NEWLINE)
CARRIAGE_RETURN_GID = glyph_registry.index(glyphnames.CARRIAGE_RETURN)


def read_char_metrics(afm):
    # read the individual char metrics. Assumes that each line contains
    # the keys C, W, N and B. Of these keys, only C (or CH, but that's
    # not implemented here) is really required by the AFM specification.
    charmetrics = {encoding.notdef: (0, 0,0,0,0)}
    font_encoding = [encoding.notdef] * 256
    while 1:
        line = afm.readline()
        if line == 'EndCharMetrics\n':
            break
        items = filter(None, [s.strip() for s in line.split(';')])
        if not items:
            continue
        code = name = width = bbox = None
        for item in items:
            [key, value] = item.split(None, 1)
            if key == 'C':
                code = int(value)
            elif key == 'WX':
                width = int(round(float(value)))
            elif key == 'N':
                name = value
            elif key == 'B':
                bbox = tuple(map(int,map(round,map(float,value.split()))))
        charmetrics[name] = (width,) + bbox
        font_encoding[code] = name
    return charmetrics, font_encoding

def read_afm_file(filename):
    afm = streamfilter.LineDecode(open(filename, 'r'))

    attribs = {'ItalicAngle': 0.0}
    charmetrics = None
    font_encoding = [encoding.notdef] * 256

    while 1:
        line = afm.readline()
        if not line:
            break
        try:
            [key, value] = line.split(None, 1)
        except ValueError:
            # this normally means that a line contained only a keyword
            # but no value or that the line was empty
            continue
        try:
            action = converters[key]
        except KeyError:
            continue
        if action:
            attribs[key] = action(value)
        elif key == 'StartCharMetrics':
            charmetrics, font_encoding = read_char_metrics(afm)
            break
        else:
            # EndFontMetrics
            break

    if not charmetrics:
        raise ValueError('AFM files without individual char metrics not yet supported.')

    # Register every glyph of the font in the global glyph registry and
    # build the metric entries indexed by glyph id (see
    # devdocs/glyph-text.md).  Glyphs missing their metrics keep the
    # zero metrics of the sparse array.
    gid_entries = []
    for name, metric_tuple in charmetrics.items():
        gid_entries.append((glyph_registry.index(name),) + metric_tuple)

    if attribs.get('EncodingScheme', StandardEncoding) == StandardEncoding:
        enc = encoding.iso_latin_1
    else:
        enc = font_encoding

    # report glyphs of the encoding that the font does not define
    for name in enc:
        if name not in charmetrics:
            # missing character...
            warn(INTERNAL, '%s: missing character %s', filename, name)

    # some fonts don't define ascender and descender (psyr.afm for
    # instance). use the values from the font bounding box instead. This
    # is not really a good idea, but how do we solve this?
    #
    # If psyr.afm is the only afm-file where these values are missing
    # (?) we could use the values from the file s050000l.afm shipped
    # with ghostscript (or replace psyr.afm with that file).
    #
    # This is a more general problem since many of the values Sketch
    # reads from afm files are only optional (including ascender and
    # descender).
    if 'Ascender' not in attribs:
        attribs['Ascender'] = attribs['FontBBox'][3]
    if 'Descender' not in attribs:
        attribs['Descender'] = attribs['FontBBox'][1]

    return (CreateFontMetric(attribs['Ascender'], attribs['Descender'],
                             attribs['FontBBox'], attribs['ItalicAngle'],
                             gid_entries),
            enc)


_warned_about_afm = {}
def read_metric(ps_name):
    for afm in ps_to_filename[ps_name]:
        afm = afm + '.afm'
        filename = find_in_path(config.font_path, afm)
        if filename:
            if __debug__:
                import time
                start = time.clock()
            metric = read_afm_file(filename)
            if __debug__:
                pdebug('timing', 'time to read afm %s: %g', afm,
                       time.clock() - start)
            return metric
    else:
        if not _warned_about_afm.get(afm):
            warn(USER,
                 _("I cannot find the metrics for the font %(ps_name)s.\n"
                   "The file %(afm)s is not in the font_path.\n"
                   "I'll use the metrics for %(fallback)s instead."),
                 ps_name = ps_name, afm = afm,
                 fallback = config.preferences.fallback_font)
            _warned_about_afm[afm] = 1
        if ps_name != config.preferences.fallback_font:
            return read_metric(config.preferences.fallback_font)
        else:
            raise SketchError("Can't load metrics for fallback font %s",
                              config.preferences.fallback_font)


def font_file_name(ps_name):
    names = []
    for basename in ps_to_filename[ps_name]:
        names.append(basename + '.pfb')
        names.append(basename + '.pfa')
    filename = find_files_in_path(config.font_path, names)
    return filename


_warned_about_outlines = {}
def read_outlines(ps_name):
    filename = font_file_name(ps_name)
    if filename:
        if __debug__:
            pdebug('font', 'read_outlines: %s', filename)

        import Sketch.Lib.type1
        return Sketch.Lib.type1.read_outlines(filename)
    else:
        if not _warned_about_outlines.get(ps_name):
            warn(USER,
                 _("I cannot find the outlines for the font %(ps_name)s.\n"
                   "The file with basename(s) %(filename)s is not found in the font_path.\n"
                   "I'll use the outlines for %(fallback)s instead."),
                 ps_name = ps_name, filename = ps_to_filename[ps_name],
                 fallback = config.preferences.fallback_font)
            _warned_about_outlines[ps_name] = 1
        if ps_name != config.preferences.fallback_font:
            return read_outlines(config.preferences.fallback_font)
        else:
            raise SketchInternalError('Cannot find file for font %s' % ps_name)

def convert_outline(outline):
    paths = []
    trafo = Scale(0.001)
    for closed, sub in outline:
        if closed:
            sub.append(sub[0])
        path = CreatePath()
        paths.append(path)
        for item in sub:
            if len(item) == 2:
                path.AppendLine(*item)
            else:
                path.AppendBezier(*item)
        if closed:
            path.load_close()
    for path in paths:
        path.Transform(trafo)
    return tuple(paths)




fontlist = []
fontmap = {}
ps_to_filename = {}

def _add_ps_filename(ps_name, filename):
    filename = (filename,)
    if ps_name in ps_to_filename:
        filename = ps_to_filename[ps_name] + filename
    ps_to_filename[ps_name] = filename

def read_font_dirs():
    #print 'read_font_dirs'
    if __debug__:
        import time
        start = time.clock()

    rx_sfd = re.compile(r'^.*\.sfd$')
    for directory in config.font_path:
        #print directory
        try:
            # unicode dir -> unicode file names
            # (devdocs/string-handling.md)
            filenames = os.listdir(as_unicode(directory))
        except os.error as exc:
            warn(USER, _("Cannot list directory %s:%s\n"
                         "ignoring it in font_path"),
                 directory, str(exc))
            continue
        dirfiles = filter(rx_sfd.match, filenames)
        for filename in dirfiles:
            filename = os.path.join(directory, filename)
            #print filename
            try:
                file = open(filename, 'r')
                line_nr = 0
                for line in file.readlines():
                    line_nr = line_nr + 1
                    line = line.strip()
                    if not line or line[0] == '#':
                        continue
                    info = map(intern, line.split(','))
                    if len(info) == 6:
                        psname = info[0]
                        fontlist.append(tuple(info[:-1]))
                        _add_ps_filename(psname, info[-1])
                        fontmap[psname] = tuple(info[1:-1])
                    elif len(info) == 2:
                        psname, basename = info
                        _add_ps_filename(psname, basename)
                    else:
                        warn(INTERNAL,'%s:%d: line must have exactly 6 fields',
                             filename, line_nr)
                file.close()
            except IOError as value:
                warn(USER, _("Cannot load sfd file %(filename)s:%(message)s;"
                             "ignoring it"),
                     filename = filename, message = value.strerror)
    if __debug__:
        pdebug('timing', 'time to read font dirs: %g', time.clock() - start)

def make_family_to_fonts():
    families = {}
    for item in fontlist:
        family = item[1]
        fontname = item[0]
        if family in families:
            families[family] = families[family] + (fontname,)
        else:
            families[family] = (fontname,)
    return families



xlfd_template = "%s--%s-*-*-*-*-*-%s"

font_cache = SKCache()

class Font:

    def __init__(self, name):
        self.name = name
        info = fontmap[name]
        family, font_attrs, xlfd_start, encoding_name = info
        self.family = family
        self.font_attrs = font_attrs
        if xlfd_start:
            xlfd_start = xlfd_start.lower()
        self.xlfd_start = xlfd_start
        self.encoding_name = encoding_name
        self.metric, self.encoding = read_metric(self.PostScriptName())
        # map between the font's 256-code encoding (as used by .sk
        # files and PostScript) and glyph ids (see devdocs/glyph-text.md)
        self.code_to_gid = [glyph_registry.index(name)
                            for name in self.encoding]
        # control codes that occur in historical .sk files map to the
        # reserved control glyphs (see devdocs/glyph-text.md)
        self.code_to_gid[0x0A] = NEWLINE_GID
        self.code_to_gid[0x0D] = CARRIAGE_RETURN_GID
        self.gid_to_code = dict(
            [(self.code_to_gid[code], code)
             for code in range(256)
             if self.encoding[code] != encoding.notdef])
        # control-code glyphs round-trip through their byte codes
        self.gid_to_code[NEWLINE_GID] = 0x0A
        self.gid_to_code[CARRIAGE_RETURN_GID] = 0x0D
        self.outlines = None

        self.ref_count = 0
        font_cache[self.name] = self

    def __del__(self):
        if font_cache is not None and self.name in font_cache:
            del font_cache[self.name]

    def __repr__(self):
        return "<Font %s>" % self.name

    def GetXLFD(self, size_trafo):
        if not self.xlfd_start:
            return 'fixed'
        if type(size_trafo) == TrafoType:
            if size_trafo.m11 == size_trafo.m22 > 0\
               and size_trafo.m12 == size_trafo.m21 == 0:
                # a uniform scaling. Special case for better X11R5
                # compatibility
                return xlfd_template % (self.xlfd_start,
                                        int(round(size_trafo.m11)),
                                        self.encoding_name)
            return xlfd_template % (self.xlfd_start, xlfd_matrix(size_trafo),
                                    self.encoding_name)
        return xlfd_template % (self.xlfd_start, int(round(size_trafo)),
                                self.encoding_name)

    def ClearXLFD(self):
        self.xlfd_start = None
        family, font_attrs, xlfd_start, encoding_name = fontmap[self.name]
        xlfd_start = None
        fontmap[self.name] = (family, font_attrs, xlfd_start, encoding_name)
    
    def PostScriptName(self):
        return self.name

    def TextGids(self, text):
        """Convert TEXT to a gid array.  Accepted forms: array('I') of
        glyph ids (returned unchanged), unicode (characters mapped to
        glyph names), byte string (codes in this font's encoding -- the
        legacy form used by .sk files and import filters).  See
        devdocs/glyph-text.md."""
        if isinstance(text, array):
            if text.typecode == 'I':
                return text
            return array('I', text)
        if isinstance(text, unicode):
            gids = []
            for char in text:
                name = glyphnames.unicode_to_glyphname(char)
                if name is None:
                    gids.append(NOTDEF_GID)
                else:
                    gids.append(glyph_registry.index(name))
            return array('I', gids)
        # byte string: font-encoding codes
        code_to_gid = self.code_to_gid
        return array('I', [code_to_gid[ord(char)] for char in text])

    def _as_gids(self, text):
        if isinstance(text, array) and text.typecode == 'I':
            return text
        return self.TextGids(text)

    def GlyphName(self, gid):
        """Return the glyph name for the glyph id GID."""
        return glyph_registry.name(gid)

    def IsPrintableGlyph(self, gid):
        """Return true if the glyph GID is printable, i.e. has a code
        in the font's encoding."""
        return gid in self.gid_to_code

    def GidForChar(self, char):
        """Return the glyph id for the single byte character CHAR (a
        code in this font's encoding)."""
        return self.code_to_gid[ord(char)]

    def SpaceGid(self):
        """Return the glyph id of the space character."""
        return self.code_to_gid[32]

    def GlyphCodes(self, gids):
        """Return a list of the byte codes of GIDS in this font's
        encoding.  Glyphs that are not in the encoding become code 0
        (notdef)."""
        gid_to_code = self.gid_to_code
        result = []
        for gid in gids:
            code = gid_to_code.get(gid)
            if code is None:
                code = 0
            result.append(code)
        return result

    def EncodedText(self, gids):
        """Return the glyphs GIDS as a byte string in this font's
        encoding (the serialization form of .sk files and PostScript).
        Glyphs that are not in the encoding become notdef."""
        return ''.join(map(chr, self.GlyphCodes(gids)))

    def TextBoundingBox(self, text, size):
        # Return the bounding rectangle of TEXT (gids, bytes or
        # unicode) when set in this font with a size of SIZE. The
        # coordinates of the rectangle are relative to the origin of
        # the first character.
        llx, lly, urx, ury = self.metric.string_bbox(self._as_gids(text))
        size = size / 1000.0
        return (llx * size, lly * size, urx * size, ury * size)

    def TextCoordBox(self, text, size):
        # Return the coord rectangle of TEXT when set in this font with
        # a size of SIZE. The coordinates of the rectangle are relative
        # to the origin of the first character.
        metric = self.metric
        width = metric.string_width(self._as_gids(text))
        size = size / 1000.0
        return (0,		metric.descender * size,
                width * size,	metric.ascender * size)

    def TextCaretData(self, text, pos, size):
        from math import tan, pi
        size = size / 1000.0
        x = self.metric.string_width(self._as_gids(text), pos) * size
        lly = self.metric.lly * size
        ury = self.metric.ury * size
        t = tan(self.metric.italic_angle * pi / 180.0);
        up = ury - lly
        return Point(x - t * lly, lly), Point(-t * up, up)

    def TypesetText(self, text):
        return self.metric.typeset_string(self._as_gids(text))

    def GetOutline(self, gid):
        """Return the outline paths of the glyph with id GID."""
        if self.outlines is None:
            self.char_strings, self.cs_interp \
                = read_outlines(self.PostScriptName())
            self.outlines = {}
        char_name = glyph_registry.name(gid)
        outline = self.outlines.get(char_name)
        if outline is None:
            self.cs_interp.execute(self.char_strings[char_name])
            outline = convert_outline(self.cs_interp.paths)
            self.outlines[char_name] = outline
            self.cs_interp.reset()
        copy = []
        for path in outline:
            path = path.Duplicate()
            copy.append(path)
        return tuple(copy)

    def FontFileName(self):
        return font_file_name(self.PostScriptName())



_warned_about_font = {}
def GetFont(fontname):
    if fontname in font_cache:
        return font_cache[fontname]
    if fontname not in fontmap:
        if not _warned_about_font.get(fontname):
            warn(USER, _("I can't find font %(fontname)s. "
                         "I'll use %(fallback)s instead"),
                 fontname = fontname,
                 fallback = config.preferences.fallback_font)
            _warned_about_font[fontname] = 1
        if fontname != config.preferences.fallback_font:
            return GetFont(config.preferences.fallback_font)
        raise ValueError('Cannot find font %s.' % fontname)
    return Font(fontname)


#
#	Initialisation on import
#

Subscribe(const.INITIALIZE, read_font_dirs)
