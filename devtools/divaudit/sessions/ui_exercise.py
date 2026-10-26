# --run-script payload for the division-audit UI session.  Exercises
# the canvas/viewport/ruler math (zoom, scroll, redraw), the panels
# (linedlg/filldlg), the Scripts-menu functions and the plugin objects.
# Run inside the full app (under Xvfb) which itself runs under the
# audit wrapper, so all division warnings of the whole process are
# recorded:
#
#   xvfb-run -a devtools/divaudit/python2-divaudit \
#       build/scripts-2.7/skencil --run-script=<this file>
#
# Every step is guarded: a failure is reported and the session still
# quits cleanly.

import os
import sys
import traceback

import Sketch

app = Sketch.Base.main.application
win = app.main_window
doc = win.document
root = app.root


def step(name, fn):
    try:
        fn()
        print '  OK   %s' % name
    except Exception:
        print '  FAIL %s' % name
        traceback.print_exc()
    sys.stdout.flush()


def canvas_and_viewport():
    canvas = getattr(win, 'canvas', None) or getattr(win, 'viewport', None)
    vp = getattr(canvas, 'viewport', canvas)
    return canvas, vp


def selection_and_transforms():
    doc.SelectAll()
    from Sketch import Point
    doc.TranslateSelected(Point(5, 0))
    doc.RotateSelected(15)
    from Sketch import Scale
    doc.TransformSelected(Scale(1.2, 1.2))
    doc.Undo()
    doc.Redo()
    doc.SelectNone()


def zoom_and_scroll():
    canvas, vp = canvas_and_viewport()
    vp.SetScale(2.0)
    vp.SetScale(0.5)
    vp.SetCenter(doc.BoundingRect().center() if
                 hasattr(doc.BoundingRect(), 'center') else (200, 300))
    vp.set_origin(30, 30)
    vp.zoom_fit_rect(doc.BoundingRect())
    vp.update_rulers(force=1)
    vp.xview('moveto', 0.1)
    vp.yview('moveto', 0.1)
    root.update_idletasks()
    root.update()


def create_objects():
    from Sketch.Scripts.create_star import create_star_path
    from Sketch.Scripts.create_spiral import create_spiral_path
    from Sketch import PolyBezier
    win.PlaceObject(PolyBezier((create_star_path(5, 2, 100),)))
    win.PlaceObject(PolyBezier((create_spiral_path(3, '80'),)))
    from Sketch.Plugins.Objects.regpoly import RegularPolygon
    win.PlaceObject(RegularPolygon(vertices=6, radius=70))
    from Sketch.Plugins.Objects.arrow import Arrow
    win.PlaceObject(Arrow())


def open_panels():
    win.CreateDialog('linedlg', 'LinePanel')
    win.CreateDialog('filldlg', 'FillPanel')


def scripts_menu_functions():
    from Sketch.Scripts import spread
    for name in ('spread_h_casc_l', 'spread_h_casc_r', 'spread_h_center',
                 'spread_h_bbox', 'spread_v_casc_b', 'spread_v_casc_t',
                 'spread_v_center', 'spread_v_bbox'):
        fn = getattr(spread, name)
        doc.SelectAll()
        step(name, lambda f=fn: f(win))
        doc.Undo()
    doc.SelectNone()


def footprints():
    from Sketch.Scripts import footprints
    doc.SelectAll()
    footprints.foot_prints_along_path(win)
    doc.SelectNone()


# NOTE: average_points and the dialog-based scripts are skipped here:
# they open modal dialogs (AverageDialog etc.), which would block this
# scripted session.


print '== ui_exercise (pid %d)' % os.getpid()
sys.stdout.flush()
step('selection + transforms', selection_and_transforms)
step('create objects', create_objects)
step('zoom + scroll', zoom_and_scroll)
step('panels', open_panels)
step('spread scripts', scripts_menu_functions)
step('footprints', footprints)

# save the session document to exercise the savers in the live app too
def save_session():
    from Sketch.Base import plugins
    path = '/tmp/divaudit/out/session.sk'
    plugin = plugins.find_export_plugin(
        plugins.guess_export_plugin('.sk'))
    plugin(doc, path)
    print '       -> %s' % path
step('save session document', save_session)


# NOTE: terminate explicitly with os._exit(0) after Tk is destroyed
# (see test/ui/scripts/smoke_open.py for the rationale); the audit
# hook appends each warning immediately, so nothing is lost.
def _quit_app():
    print '== quitting'
    sys.stdout.flush()
    root.destroy()
    os._exit(0)

# safety net: quit even if a step hung; the normal quit is 1.5 s
# after the last step
root.after(30000, _quit_app)
root.after(1500, _quit_app)
