#  curvetext.py - Sketch script to create bezier objects from font files
#
#  Copyright (c) 2001 Intevation GmbH <url:http://intevation.net>
#  Copyright (c) 2001 Bernhard Herzog <bh@intevation.de>
#  Copyright (c) 2000 Tamito KAJIYAMA <kajiyama@grad.sccs.chukyo-u.ac.jp>
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License as
#  published by the Free Software Foundation; either version 2 of the
#  License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful, but
#  WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
#  General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software
#  Foundation Inc., 675 Mass Ave, Cambridge, MA 02139, USA.


"""
Sketch module to create text from a given Type1 or TrueType font file
as a group of bezier-objects.

Place this script into ~/.sketch or some other directory on Python's
path as curvetext.py, and put the line

import curvetext

into ~/.sketch/userhooks.py. This will create a menu entry "Create Curve
Text" in the "Scripts" menu.

To use it, put the font files into ~/.sketch/fonts/. For a Type1 font,
you need the font file itself (i.e. the pfa or pfb file) and the .afm
file. For TrueType fonts you only need the ttf file, however, you need
the FreeType library and the freetype python bindings from Tamito
KAJIYAMA's JapaneseText
(http://pseudo.grad.sccs.chukyo-u.ac.jp/~kajiyama/sketch/). The fonts
will be listed in the dialog box.

Configuration:

curvetext.py has two global variables that you can modify:

   curvetext.font_directory

        The directory where the font files are

   curvetext.list_standard_fonts

        Set this to true (e.g. 1) to include the font's Sketch's text
        objects know about to the list.

To set these variables assign a new value after the "import curvetext"
in userhooks.py

"""

__version__ = "1.0"

# The code quality is not as good as it could be, but it does the job :)
#
# Ideas for improvements:
#
# - Use a plugin object. That way the text would stay editable as text
#
# - Take the metrics directly from the PFB file instead of relying on
#   the presence of the AFM file. Sketch currently doesn't use any
#   information from the AFM file that isn't available in the PFB's too.
#
# - Perhaps use the default text properties for the bezier objects
#

import os.path
from string import replace

from Tkinter import Button, Label, Entry, Frame, Scrollbar, \
     DoubleVar, StringVar, E, W, N, S, END, LEFT, RIGHT, Y
import Tkinter

import Sketch, Sketch.UI
from Sketch import ContAngle, ContSmooth, CreatePath, Point
from Sketch.UI.sketchdlg import SKModal
from Sketch.Graphics.font import read_afm_file, read_outlines, convert_outline
from Sketch.Lib.type1 import read_outlines
from Sketch.Graphics.properties import DefaultTextProperties

class FontError(Exception):
    """Exceptions specific to this module"""
    pass

class Type1FontFile:

    """Represent one Type 1 font file in a way similar to a normal
    Sketch font object."""

    def __init__(self, filename):
        """Initialize instance from the type 1 files described by
        filename, which does not contain the .pfb or .afm extensions"""
        self.filename = filename
        if os.path.exists(filename + '.pfb'):
            self.font_file = filename + '.pfb'
        else:
            self.font_file = filename + '.pfa'
        afm = filename + '.afm'
        if os.path.exists(afm):
            self.metric, self.encoding = read_afm_file(afm)
        else:
            msg = ("Missing AFM file %s.\n"
                   "You can use ghostscript's pf2afm to generate it"
                   " if necessary.") % afm
            raise FontError(msg)
	self.outlines = None

    def __repr__(self):
        return "<Type1File %s>" % self.filename

    def TypesetText(self, text):
	return self.metric.typeset_string(text)

    def GetOutline(self, char):
	if self.outlines is None:
	    self.char_strings, self.cs_interp \
			       = read_outlines(self.font_file)
	    self.outlines = {}
	char_name = self.encoding[ord(char)]
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


def curves_type1(text, font):
    objects = []
    pos = font.TypesetText(text)
    for i in range(len(text)):
        paths = font.GetOutline(text[i])
        if paths:
            obj = Sketch.PolyBezier(paths = paths, properties = DefaultTextProperties())
            trafo = Sketch.Translation(pos[i])
            obj.Transform(trafo)
            objects.append(obj)
    return Sketch.Group(objects)


def get_charmap(face):
    # Taken verbatim from KAJIYAMA's JapaneseText which is GPL.
    for i in range(face.num_charmaps):
        pid, eid = face.get_charmap_id(i)
        if pid == 3 and eid == 1:  # Windows Unicode
            return face.get_charmap(i)
    else:
        raise RuntimeError, "no Windows Unicode charmap"


def create_ttf_group(text, face):
    # This function is taken almost verbatim from KAJIYAMA's
    # JapaneseText which is GPL.
    # prepare fonts
    font = face.new_instance()
    font.set_resolutions(72, 72)
    font.set_charsize(1024.0)
    font_charmap = get_charmap(face)
    # convert glyph data into bezier polygons
    offset = 0
    objects = []
    for i in range(len(text)):
        code = ord(text[i])
        glyph = font.new_glyph(font_charmap.index(code))
        paths = []
        for contour in glyph.outline:
            path = CreatePath()
            j = 0
            npoints = len(contour)
            while j <= npoints:
                if j == npoints:
                    x, y, onpoint = contour[0]
                else:
                    x, y, onpoint = contour[j]
                point = Point(x, y)
                j = j + 1
                if onpoint:
                    path.AppendLine(point)
                    last_point = point
                else:
                    c1 = last_point + (point - last_point) * 2.0 / 3.0
                    if j == npoints:
                        x, y, onpoint = contour[0]
                    else:
                        x, y, onpoint = contour[j]
                    if onpoint:
                        j = j + 1
                        cont = ContAngle
                    else:
                        x = point.x + (x - point.x) * 0.5
                        y = point.y + (y - point.y) * 0.5
                        cont = ContSmooth
                    last_point = Point(x, y)
                    c2 = last_point + (point - last_point) * 2.0 / 3.0
                    path.AppendBezier(c1, c2, last_point, cont)
            path.ClosePath()
            paths.append(path)
        obj = Sketch.PolyBezier(paths = tuple(paths))
        trafo = Sketch.Scale(1/1024.0)(Sketch.Translation(offset, 0))
        obj.Transform(trafo)
        objects.append(obj)
        offset = offset + glyph.advance
    return Sketch.Group(objects)


def curves_truetype(text, filename):
    import freetype
    engine = freetype.FreeType()
    return create_ttf_group(text, engine.open_face(filename))


def text_as_curves(text, font_format, font_name, size):
    """Return the string text as a group of bezier objects.

    The outlines are taken from the font described by font_format (a
    string, one of "TT" or "T1" or "T1-file") and the font name
    """
    if font_format == "T1":
        object = curves_type1(text, Sketch.GetFont(font_name))
    if font_format == "T1-file":
        object = curves_type1(text, font = Type1FontFile(font_name))
    elif font_format == "TT":
        object = curves_truetype(text, font_name)
    scale = Sketch.Scale(size)
    object.Transform(scale)
    return object

    
class SmartListbox(Tkinter.Listbox):

    """Smarter Listbox widget that can hold list of objects other than
    strings and return the selected object"""

    def __init__(self, master, command = None, args = (), **kw):
	apply(Tkinter.Listbox.__init__, (self, master), kw)
        self.list = []

    def SetList(self, list):
        self.list = list
	self.delete(0, END)
	for text, object in list:
	    self.insert(END, text)

    def SelectNone(self):
	self.select_clear(0, END)

    def Select(self, idx, view = 0):
	self.select_clear(0, END)
	self.select_set(idx)
        if view:
            self.yview(idx)

    def SelectedObject(self, default = None):
        sel = self.curselection()
        if sel:
            return self.list[int(sel[0])][-1]
        else:
            return default


class CurveTextDialog(SKModal):

    title = "Create Curve Text"

    def __init__(self, master, font_directory, list_standard_fonts):
        self.font_directory = font_directory
        self.list_standard_fonts = list_standard_fonts
        SKModal.__init__(self, master)

    def build_dlg(self):
        row = 0
	self.var_size = DoubleVar(self.top)
        self.var_size.set(16.0)
        label = Label(self.top, text = "Text Size")
        label.grid(column = 0, row = row, sticky = E)
	entry = Entry(self.top, width = 15, textvariable = self.var_size)
	entry.grid(column = 1, row = row)

        row = row + 1
        label = Label(self.top, text = "Font")
        label.grid(column = 0, row = row, sticky = E)
        row = row + 1
        frame = Frame(self.top)
	frame.grid(column = 0, row = row, columnspan = 2)
        list = self.list = SmartListbox(frame)
        list.SetList(self.build_font_list())
	list.pack(side = LEFT, expand = 1)
        scrollbar = Scrollbar(frame, command = list.yview)
        scrollbar.pack(side = RIGHT, fill = Y)
        list.config(yscrollcommand = scrollbar.set)
        
        row = row + 1
        self.var_text = StringVar(self.top)
        self.var_text.set("Test")
        label = Label(self.top, text = "Text")
        label.grid(column = 0, row = row, sticky = E)
	entry = Entry(self.top, width = 15, textvariable = self.var_text)
	entry.grid(column = 1, row = row)

        row = row + 1
	button = Button(self.top, text = "OK", command = self.ok)
	button.grid(column = 0, row = row, sticky = W)
	button = Button(self.top, text = "Cancel", command = self.cancel)
	button.grid(column = 1, row = row, sticky = E)

    def ok(self):
        font = self.list.SelectedObject()
        if font is not None:
            self.close_dlg((self.var_text.get(), font, self.var_size.get()))

    def build_font_list(self):
        # take the type 1 fonts from the known fonts
        items = []

        # the standard fonts
        if self.list_standard_fonts:
            fontnames = Sketch.Graphics.font.fontmap.keys()
            fontnames.sort()
            for name in fontnames:
                items.append(("T1: " + name, ("T1", name)))

        # scan the font directory
        font_files = os.listdir(self.font_directory)
        font_files.sort()
        used_basenames = {}
        type1 = []
        ttf = []
        for name in font_files:
            basename, ext = os.path.splitext(name)
            if ext in ('.pfa', '.pfb'):
                if not used_basenames.has_key(basename):
                    type1.append(("T1: " + basename,
                                  ("T1-file", os.path.join(self.font_directory,
                                                           basename))))
                    used_basenames[basename] = 1
            elif ext == '.ttf':
                ttf.append(("TT: " + basename,
                            ("TT", os.path.join(self.font_directory, name))))
        type1.sort()
        ttf.sort()
        return items + type1 + ttf


font_directory = '~/.sketch/fonts'
list_standard_fonts = 1

convdict = {"\xd0\xb0" : "\301",
"\xd0\xb1" : "\302",
"\xd0\xb2" : "\327",
"\xd0\xb3" : "\307",
"\xd0\xb4" : "\304",
"\xd0\xb5" : "\305",
"\xd0\xb6" : "\326",
"\xd0\xb7" : "\332",
"\xd0\xb8" : "\311",
"\xd0\xb9" : "\312",
"\xd0\xba" : "\313",
"\xd0\xbb" : "\314",
"\xd0\xbc" : "\315",
"\xd0\xbd" : "\316",
"\xd0\xbe" : "\317",
"\xd0\xbf" : "\320",
"\xd1\x80" : "\322",
"\xd1\x81" : "\323",
"\xd1\x82" : "\324",
"\xd1\x83" : "\325",
"\xd1\x84" : "\306",
"\xd1\x85" : "\310",
"\xd1\x86" : "\303",
"\xd1\x87" : "\336",
"\xd1\x88" : "\333",
"\xd1\x89" : "\335",
"\xd1\x8a" : "\337",
"\xd1\x8b" : "\331",
"\xd1\x8c" : "\330",
"\xd1\x8d" : "\334",
"\xd1\x8e" : "\300",
"\xd1\x8f" : "\321",
"\xd0\x90" : "\341",
"\xd0\x91" : "\342",
"\xd0\x92" : "\367",
"\xd0\x93" : "\347",
"\xd0\x94" : "\344",
"\xd0\x95" : "\345",
"\xd0\x96" : "\366",
"\xd0\x97" : "\372",
"\xd0\x98" : "\351",
"\xd0\x99" : "\352",
"\xd0\x9a" : "\353",
"\xd0\x9b" : "\354",
"\xd0\x9c" : "\355",
"\xd0\x9d" : "\356",
"\xd0\x9e" : "\357",
"\xd0\x9f" : "\360",
"\xd0\xa0" : "\362",
"\xd0\xa1" : "\363",
"\xd0\xa2" : "\364",
"\xd0\xa3" : "\365",
"\xd0\xa4" : "\346",
"\xd0\xa5" : "\350",
"\xd0\xa6" : "\343",
"\xd0\xa7" : "\376",
"\xd0\xa8" : "\373",
"\xd0\xa9" : "\375",
"\xd0\xaa" : "\377",
"\xd0\xab" : "\371",
"\xd0\xac" : "\370",
"\xd0\xad" : "\374",
"\xd0\xae" : "\340",
"\xd0\xaf" : "\361"}

                
def create_curve_text(context):
    dialog = CurveTextDialog(context.application.root,
                             os.path.expanduser(font_directory),
                             list_standard_fonts)
    result = dialog.RunDialog()
    if result is not None:
        text, (font_type, font_name), size = result
        if text.find("\xd0") >= 0 or text.find("\xd1") >= 0:
            for c in convdict.keys():
                text = replace(text,c,convdict[c])
        if text.find("\\") >= 0:
            text = eval('"""'+text+'"""',{"__builtins__":None},{})
        try:
            group = text_as_curves(text, font_type, font_name, size)
            context.main_window.canvas.PlaceObject(group, "Create CurveText")
        except FontError, exception:
            context.application.MessageBox("Curve Text Error",
                                           str(exception))
                                           



import Sketch.Scripting        
Sketch.Scripting.AddFunction('create_curve_text',
                             'Create Curve Text',
                             create_curve_text,
                             script_type = Sketch.Scripting.AdvancedScript)

