# Sketch - A Python-based interactive drawing program
# Copyright (C) 1997, 1998 by Bernhard Herzog
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


from Sketch.UI.sketchdlg import SketchPanel
from tkinter import X, BOTH, LEFT, TOP
from tkinter import Frame, Label
from Sketch.UI.tkext import UpdatedButton, MyEntry, UpdatedCheckbutton, \
     MyOptionMenu2

from Sketch.UI.view import SketchView

bitmap_types = [('Portable Pixmap (PPM)', 'ppmraw'),
                ('Portable Graymap (PGM)', 'pgmraw'),
                ('Portable Bitmap (PBM)', 'pbmraw')]



class ExportPanel(SketchPanel):

    title = 'Export'

    def __init__(self, master, main_window, doc):
        SketchPanel.__init__(self, master, main_window, doc, name = 'export')

    def build_dlg(self):
        top = self.top

        self.view = SketchView(top, self.document, width = 200, height = 200,
                               background = 'white')
        self.view.pack(side = LEFT, fill = BOTH, expand = 1)

        self.opt_format = MyOptionMenu2(top, bitmap_types)
        self.opt_format.pack(side = TOP)

        frame = Frame(top)
        frame.pack(side = TOP, expand = 1, fill = X)
        label = Label(frame, text = 'Resolution')
        label.pack(side = LEFT)
        entry = MyEntry(frame, width = 4)
        entry.pack(side = LEFT)
        label = Label(frame, text = 'dpi')
        label.pack(side = LEFT)

        frame = Frame(top)
        frame.pack(side = TOP, expand = 1, fill = X)
        label = Label(frame, text = 'Size')
        label.pack(side = LEFT)
        entry = MyEntry(frame, width = 4)
        entry.pack(side = LEFT)
        label = Label(frame, text = 'x')
        label.pack(side = LEFT)
        entry = MyEntry(frame, width = 4)
        entry.pack(side = LEFT)
        label = Label(frame, text = 'pixel')
        label.pack(side = LEFT)

        check = UpdatedCheckbutton(top, text = 'antialiasing')
        check.pack(side = TOP)

        frame = Frame(top)
        frame.pack(side =TOP)
        button = UpdatedButton(frame, text = 'Export')
        button.pack(side = LEFT)
        button = UpdatedButton(frame, text = 'Close', command = self.close_dlg)
        button.pack(side = LEFT)


    def init_from_doc(self):
        self.view.SetDocument(self.document)




import os

from Sketch.Lib import util


def export_bitmap(document):
    from psdevice import PostScriptDevice
    width, height = document.PageSize()
    width = round(width)
    height = round(height)
    res = 72
    outfile = '/tmp/export.ppm'
    args = ['-dSAFER', '-dNOPAUSE', '-g%dx%d' % (width, height),
            '-r%d' % res, '-sDEVICE=ppmraw',
            '-sOutputFile=' + outfile, '-q', '-']
    if __debug__:
        print(args)
    file = util.run_gs_pipe(args)
    try:
        device = PostScriptDevice(file, as_eps = 0)
        document.Draw(device)
        device.Close()
        file.write('quit\n')
    finally:
        file.close()



