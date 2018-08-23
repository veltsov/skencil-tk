#!/usr/bin/python

# Sketch - A Python-based interactive drawing program
# Copyright (C) 2000, 2001 by Bernhard Herzog
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

'''\
skshow [options] file1 [file2 ...]

A slideshow for sketch files. Use space/backspace or left and right
mouse button for navigation.

Options:
 -h, --help     Print this help message
 --keep         Keep files in memory after loading them
 --preload      Load the next file in advance while the old one is shown
 --fit          Fit drawing in window
 --display=DISP The X display to use
 --geometry=GEO The size and/or position of the window in the form WxH+X+Y

'''


import sys, getopt

class Options:
    display = None
    geometry = '640x480'
    keep = 0
    preload = 0
    fit = 0
    files = []

def parse_options():
    try:
        opts, args = getopt.getopt(sys.argv[1:], "h",
                                   ["display=", "geometry=", "keep", "preload", "fit" ,
                                    "help"])
    except getopt.error:
        sys.stderr.write(__doc__)
        sys.exit(0)

    for opt, value in opts:
        if opt == "--display":
            Options.display = value
        elif opt == "--geometry":
            Options.geometry = value
        elif opt == "--keep":
            Options.keep = 1
        elif opt == "--preload":
            Options.preload = 1
        elif opt == "--fit":
            Options.fit = 1
        elif opt in ("-h", "--help"):
            sys.stderr.write(__doc__)
            sys.exit(0)

    Options.files = args

parse_options()

import Sketch
Sketch.init_ui()

import Sketch.UI.skapp, Sketch.UI.view, Sketch.load

from Tkinter import BOTH


class ShowView(Sketch.UI.view.SketchView):

    def __init__(self, master=None, toplevel = None, double_buffer = 1,
                 show_page_outline = 0, **kw):
	apply(Sketch.UI.view.SketchView.__init__, (self, master), kw)
        self.double_buffer = double_buffer
        self.show_page_outline = show_page_outline

    def do_clear(self, region):
        if not self.double_buffer:
            Sketch.UI.view.SketchView.do_clear(self, region)

    def RedrawMethod(self, region = None):
        if self.double_buffer:
            self.gc.StartDblBuffer()
        Sketch.UI.view.SketchView.RedrawMethod(self, region)
        if self.double_buffer:
            self.gc.EndDblBuffer()
        self.tkwin.Sync()


class MainWindow:

    def __init__(self, app, files, keep = 0, preload = 0):
        self.application = app
        self.files = files
        self.keep = keep
        self.preload = preload
        self.docs = [None] * len(self.files)
        self.current = 0
        self.autofill = 1
        self.build_window()
        self.bind_events()

    def build_window(self):
        root = self.application.root
        self.view = ShowView(root, toplevel = root)
        self.view.pack(fill = BOTH, expand = 1)
	self.view.focus()

    def bind_events(self):
        self.view.bind("<Configure>", self.view_resized)
        self.view.bind("<Map>", self.view_resized)
        self.view.bind("<q>", self.Exit)
        for event in ("<1>", "<n>", "<space>"):
            self.view.bind(event, self.next_file)
        for event in ("<3>", "<p>", "<BackSpace>"):
            self.view.bind(event, self.previous_file)

    def adjust_view(self):
        if self.autofill:
            if Options.fit:
                self.view.FitToWindow()
            else:
                self.view.FitPageToWindow()
            #self.view.SetScale(1.0)
            #self.view.SetCenter((512, 384), move_contents = 0)

    def view_resized(self, event):
        self.adjust_view()

    def next_file(self, *args):
        which = self.current + 1
        if which < len(self.files):
            self.current = which
            self.load_file(which)

    def previous_file(self, event):
        which = self.current - 1
        if which >= 0:
            self.current = which
            self.load_file(which)
            
    def load_file(self, which):
        if self.docs[which] is None:
            filename = self.files[which]
            doc = Sketch.load.load_drawing(filename)
            self.docs[which] = doc
        else:
            doc = self.docs[which]
        
        self.view.SetDocument(doc)
        self.adjust_view()

        if not self.keep and which > 0 and self.docs[which - 1] is not None:
            self.docs[which - 1].Destroy()
            self.docs[which - 1] = None
        
        if self.preload:
            self.view.after_idle(self.preload_files)

    def preload_files(self, *args):
        next = self.current + 1
        if next < len(self.docs) and not self.docs[next]:
            filename = self.files[next]
            doc = Sketch.load.load_drawing(filename)
            self.docs[next] = doc


    def Exit(self, *args):
        self.application.Exit()

    def Run(self):
        self.load_file(0)
	self.application.Mainloop()

    


class SketchShowApplication(Sketch.UI.skapp.TkApplication):

    tk_basename = 'sketchshow'
    tk_class_name = 'SketchShow'

    def __init__(self, files, screen_name = None, geometry = None, keep = 0,
                 preload = 0):
	Sketch.UI.skapp.TkApplication.__init__(self, screen_name = screen_name,
                                               geometry = geometry)
	self.files = files
	self.build_window(keep, preload)

    def init_tk(self, screen_name = None, geometry = None):
	Sketch.UI.skapp.TkApplication.init_tk(self, screen_name = screen_name,
                                              geometry = geometry)
        Sketch.init_modules_from_widget(self.root)

    def build_window(self, keep, preload):
        #self.root.wm_maxsize(1024, 768)
        self.main_window = MainWindow(self, self.files, keep = keep,
                                      preload = preload)

    def Run(self):
	self.main_window.Run()

    def Exit(self):
	self.root.destroy()


app = SketchShowApplication(Options.files, screen_name = Options.display,
                            geometry = Options.geometry, keep = Options.keep,
                            preload = Options.preload)
app.Run()


