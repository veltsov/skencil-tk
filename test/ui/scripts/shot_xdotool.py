# --run-script payload: synthetic keyboard input via xdotool.  The
# selection is moved with three Right arrow key presses (canvas key
# bindings: MoveSelected), then a screenshot is captured and the app
# quits.

import os
import sys

import Sketch

app = Sketch.main.application
win = app.main_window
doc = win.document
assert doc is not None, 'no document open'

doc.SelectAll()

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


def send_keys_and_capture():
    root.update_idletasks()
    root.update()
    rc = os.system(
        'xdotool search --class sketch windowactivate --sync >/dev/null 2>&1; '
        'xdotool key Right; xdotool key Right; xdotool key Right; '
        'sleep 0.5; '
        'import -window root "%s"' % shot)
    if rc != 0:
        sys.stderr.write('xdotool/screenshot failed (rc=%d)\n' % rc)
    root.after(200, _quit_app)


root.after(2500, send_keys_and_capture)
