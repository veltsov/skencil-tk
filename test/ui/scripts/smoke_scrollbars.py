# --run-script payload: exercise the scrollbar -command path. Tk's
# scrollbar bindings (tk::ScrollByUnits etc.) invoke the pax canvas
# widget command directly from the Tcl event dispatch -- unlike
# tk.call, without the GIL -- which used to abort the app with
# "Fatal Python error: PyEval_RestoreThread: NULL tstate" on the first
# wheel event over a scrollbar. Regression guard for the fix that
# marshals xview/yview through call_py_method (see
# devdocs/modernize-paxtkinter.md).

import os
import traceback

import Sketch

app = Sketch.Base.main.application
win = app.main_window
root = app.root
canvas = win.canvas


def update():
    root.update_idletasks()
    root.update()


try:
    update()

    vy0 = canvas.virtual_y
    vx0 = canvas.virtual_x

    # wheel up on the vertical scrollbar: virtual_y must decrease
    canvas.vbar.event_generate('<Button-4>', when='tail')
    update()
    vy1 = canvas.virtual_y
    assert vy1 < vy0, 'vbar <Button-4> did not scroll up: %s -> %s' % (vy0, vy1)

    # wheel down on the vertical scrollbar
    canvas.vbar.event_generate('<Button-5>', when='tail')
    update()
    vy2 = canvas.virtual_y
    assert vy2 > vy1, 'vbar <Button-5> did not scroll down: %s -> %s' % (vy1, vy2)

    # wheel on the horizontal scrollbar (Skencil-side binding added in
    # mainwindow.py; stock Tk 8.6 hardcodes vertical wheel scrolling)
    canvas.hbar.event_generate('<Button-4>', when='tail')
    update()
    vx1 = canvas.virtual_x
    assert vx1 < vx0, 'hbar <Button-4> did not scroll left: %s -> %s' % (vx0, vx1)

    # slider drag: B1 press on the slider, drag down to 80% of the bar,
    # release. Each motion issues `yview moveto <fraction>` directly
    # from the event dispatch (tk::ScrollDrag -> tk::ScrollToPos).
    first, last = canvas.vbar.get()
    height = int(canvas.vbar.winfo_height())
    if height < 50:
        height = 600  # geometry not settled; use a plausible bar height
    y0 = int((first + last) / 2.0 * height)
    y1 = int(0.8 * height)
    vy3 = canvas.virtual_y
    canvas.vbar.event_generate('<1>', x=5, y=y0, when='tail')
    canvas.vbar.event_generate('<B1-Motion>', x=5, y=y1, when='tail')
    canvas.vbar.event_generate('<ButtonRelease-1>', x=5, y=y1, when='tail')
    update()
    assert canvas.virtual_y > vy3, \
        'vbar slider drag down did not scroll down: %s -> %s' % (vy3, canvas.virtual_y)

    # MOVETO via the scrollbar command path (tk.call context); the
    # fraction must arrive as a float through call_py_method
    vh = float(canvas.virtual_height)
    max_frac = 1.0 - canvas.tkwin.height / vh
    expected = min(0.5, max_frac) * vh
    root.tk.call(canvas._w, 'yview', 'moveto', 0.5)
    update()
    # set_origin snaps the scroll offset to whole pixels, so the origin
    # may be up to 1 px off the exact fraction
    assert abs(canvas.virtual_y - expected) <= 1.0, \
        'yview moveto 0.5 -> %r, expected %r' % (canvas.virtual_y, expected)
except Exception:
    traceback.print_exc()
    os._exit(1)

print('smoke_scrollbars OK')
root.destroy()
os._exit(0)