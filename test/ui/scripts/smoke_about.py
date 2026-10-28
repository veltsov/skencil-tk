# --run-script payload: invoke File->About (the AboutBox command builds
# a version string that raised AttributeError on the py3 branch: tkinter
# has no __version__ there), then quit.

import os

import Sketch

app = Sketch.Base.main.application
win = app.main_window

# The exception must propagate and kill the process (nonzero exit):
win.AboutBox()

root = app.root


# NOTE: the process is terminated explicitly with os._exit(0) after the
# Tk is destroyed.  Without this, interpreter shutdown segfaults on the
# master branch (a pax object finalizer runs after Tcl teardown; fixed
# on `modernize' by the GIL-safe pax callbacks) and the exit status
# would be 139 even though the app itself ran fine.

def _quit_app():
    root.destroy()
    os._exit(0)


root.after(2000, _quit_app)