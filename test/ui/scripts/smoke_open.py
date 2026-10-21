# --run-script payload: sanity operations on the opened document, then
# a clean quit.  Executed by mainwindow.py before the mainloop starts;
# Sketch.main.application is the running SketchApplication.

import os

import Sketch

app = Sketch.main.application
win = app.main_window
doc = win.document
assert doc is not None, 'no document open'

# a few harmless operations exercising the document and the canvas
doc.SelectAll()
from Sketch import Point
doc.TranslateSelected(Point(5, 0))
doc.Undo()

root = app.root


# NOTE: the process is terminated explicitly with os._exit(0) after the
# Tk is destroyed.  Without this, interpreter shutdown segfaults on the
# master branch (a pax object finalizer runs after Tcl teardown; fixed
# on `modernize' by the GIL-safe pax callbacks) and the exit status
# would be 139 even though the app itself ran fine.

def _quit_app():
    root.destroy()
    os._exit(0)


root.after(1000, _quit_app)
