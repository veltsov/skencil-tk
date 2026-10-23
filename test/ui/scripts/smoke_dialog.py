# --run-script payload: open the Layers dialog (this is the dialog that
# exposed the pax/GIL NULL-tstate crash), then quit.

import os

import Sketch

app = Sketch.Base.main.application
win = app.main_window

win.CreateDialog('layerdlg', 'LayerPanel')

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
