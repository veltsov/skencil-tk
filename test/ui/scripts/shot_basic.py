# --run-script payload: capture the root window of the freshly opened
# document without changing anything (baseline screenshot), then quit.
# The capture target is given by the SKENCIL_SHOT_FILE environment
# variable.

import os
import sys

import Sketch

app = Sketch.main.application
shot = os.environ.get('SKENCIL_SHOT_FILE')
root = app.root


# NOTE: the process is terminated explicitly with os._exit(0) after the
# Tk is destroyed.  Without this, interpreter shutdown segfaults on the
# master branch (a pax object finalizer runs after Tcl teardown; fixed
# on `modernize' by the GIL-safe pax callbacks) and the exit status
# would be 139 even though the app itself ran fine.

def _quit_app():
    root.destroy()
    os._exit(0)


def capture_and_quit():
    root.update_idletasks()
    root.update()
    if shot:
        rc = os.system('import -window root "%s"' % shot)
        if rc != 0:
            sys.stderr.write('screenshot capture failed (rc=%d)\n' % rc)
    root.after(200, _quit_app)


root.after(2500, capture_and_quit)
