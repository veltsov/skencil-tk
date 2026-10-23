# --run-script payload: just quit (used for the bare-launch smoke test,
# no document is open).

import os

import Sketch

app = Sketch.Base.main.application
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
