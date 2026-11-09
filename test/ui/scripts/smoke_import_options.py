# --run-script payload: the import options dialog
# (plugindlg.ImportOptionsDlg) of File -> Open and Insert Document for
# the multi-page PostScript file $SKENCIL_TEST_PS: the description and
# the `pages' entry, OK (pages 1,3 as two layers; Insert: a group of
# page groups), Cancel (nothing happens, no message box).  The dialog
# is built without RunDialog (which would wait for the user).

import os

import Sketch
from Sketch.UI.plugindlg import ImportOptionsDlg

app = Sketch.Base.main.application
win = app.main_window
root = app.root
filename = os.environ['SKENCIL_TEST_PS']


def _dump_exc():
    # write the traceback to the real stderr (fd 2) -- sys.stderr is
    # redirected inside the app -- and fail loudly
    import traceback
    os.write(2, traceback.format_exc().encode())
    os._exit(1)


def answering(pages):
    # an ask_import_options that fills in PAGES and presses OK, or
    # Cancel if PAGES is None
    seen = []
    def ask(info, description, options):
        dialog = ImportOptionsDlg(root, info, options,
                                  description = description)
        assert [var.name for var in dialog.vars] == ['pages']
        assert dialog.vars[0]() == options['pages']
        seen.append(description)
        if pages is None:
            dialog.cancel()
        else:
            dialog.vars[0](pages)
            dialog.ok()
        return dialog.result
    return ask, seen


def layer_names(doc):
    return [layer.Name() for layer in doc.layers
            if not layer.is_SpecialLayer]


def _body():
    boxes = []
    app.MessageBox = lambda *args, **kw: boxes.append(kw)
    ask, seen = answering('1,3')
    win.ask_import_options = ask
    win.LoadFromFile(filename)
    assert seen and seen[0].startswith('3 pages'), seen
    assert layer_names(win.document) == ['Page 1', 'Page 3'], \
        layer_names(win.document)
    # the different page sizes are reported
    assert len(boxes) == 1 and 'differ in size' in boxes[0]['message'], \
        boxes
    doc = win.document

    boxes[:] = []
    ask, seen = answering(None)
    win.ask_import_options = ask
    win.LoadFromFile(filename)
    assert seen and win.document is doc and not boxes, boxes

    ask, seen = answering('all')
    win.ask_import_options = ask
    # Insert hands the group to the canvas for interactive placement
    placed = []
    win.canvas.PlaceObject = placed.append
    win.InsertFile(filename)
    assert len(placed) == 1 and len(placed[0].GetObjects()) == 3, placed


def body():
    try:
        _body()
    except BaseException:
        _dump_exc()
    root.destroy()
    os._exit(0)


root.after(500, body)
