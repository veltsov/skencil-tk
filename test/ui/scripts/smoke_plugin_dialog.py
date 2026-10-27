# --run-script payload: open the Autoshapes plugin dialog (a custom
# plugin dialog whose toolbar buttons are built from quantized PIL
# icons; regression guard for the py3 putpalette bytes fix), then
# place a star and exercise the +/- keys in edit mode through real Tk
# key events (regression guard for the late-registered plugin class
# keymaps: AutoshapeEditor.AnyKey -> KeyHandler), and quit.
import os
import traceback

import Sketch

app = Sketch.Base.main.application
win = app.main_window
canvas = win.canvas
doc = win.document


# NOTE: the process is terminated explicitly with os._exit() after the
# Tk is destroyed.  Without this, interpreter shutdown segfaults on the
# master branch (a pax object finalizer runs after Tcl teardown; fixed
# on `modernize' by the GIL-safe pax callbacks) and the exit status
# would be 139 even though the app itself ran fine.

def _quit(status):
    app.root.destroy()
    os._exit(status)


def test():
    try:
        from Sketch.Plugins.Objects.Lib.autoshapes.autoshapelib import (
            Autoshape)

        # open the plugin dialog
        info = Sketch.Base.plugins.object_plugins['Autoshape']
        assert info.HasCustomDialog(), 'Autoshape must have a custom dialog'
        win.CreatePluginDialog(info)

        # place a star and enter edit mode
        obj = Autoshape('star')
        obj.SetData((20, 20, 5))
        doc.Insert(obj)
        doc.SelectAll()
        doc.SetMode(Sketch.EditMode)
        assert doc.IsEditMode(), 'edit mode not entered'
        n0 = obj.GetN()

        # real key events through the canvas' <KeyPress> binding; the
        # canvas must have registered the plugin editor's keymap by now
        canvas.focus_force()
        canvas.update()
        canvas.event_generate('<KeyPress-plus>')
        canvas.update()
        assert obj.GetN() == n0 + 1, \
            '+ key: ray count %d -> %d' % (n0, obj.GetN())
        canvas.event_generate('<KeyPress-minus>')
        canvas.update()
        assert obj.GetN() == n0, \
            '- key: ray count %d' % obj.GetN()
        print('AUTOSHAPE DIALOG AND KEYS OK')
    except:
        traceback.print_exc()
        _quit(1)
    _quit(0)


# run the test from the mainloop once the window is mapped (key events
# need a realized, focused widget)
app.root.after(2000, test)
