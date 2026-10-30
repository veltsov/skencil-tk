# --run-script payload: trigger the LtxObj recompute (edit flow, the
# PluginPanel.set_parameter transaction) and the create flow (the
# PluginPanel.do_apply constructor call) with the LaTeX tools MISSING
# from PATH (see test_latex_missing.py).
#
# The failed recompute must be a rejected update: the plugin reports
# the error once and re-raises, the transaction is aborted (no undo
# entry, no EDITED message), and the object stays exactly as it was.
# (The pre-fix code looped forever here, because the exception raised
# in the plugin's error report escaped recompute() and was caught and
# re-applied by the undo machinery.)

import os
import sys

import Sketch

app = Sketch.Base.main.application
doc = app.main_window.document
root = app.root


def find_ltxobj(container):
    for obj in container.objects:
        if obj.__class__.__name__ == 'LtxObj':
            return obj
    return None


def _quit():
    root.destroy()
    os._exit(0)


def _dump_exc():
    # write the traceback to the real stderr (fd 2) -- sys.stderr is
    # redirected inside the app -- and fail loudly
    import traceback
    os.write(2, traceback.format_exc().encode())
    os._exit(1)


def _watchdog():
    os.write(2, b'latex_missing: watchdog fired (30s)\n')
    os._exit(42)


def body():
    try:
        _body()
    except BaseException:
        _dump_exc()


def _body():
    obj = None
    for layer in doc.layers:
        obj = find_ltxobj(layer)
        if obj is not None:
            break
    assert obj is not None, 'no LtxObj in document'

    from Sketch import SketchError
    from Sketch.Graphics.document import AbortTransactionError

    orig_text = obj.Text()
    orig_group = obj.group
    orig_nobjects = len(obj.objects)
    n_undo = len(doc.undo.undoinfo)

    # edit flow: the PluginPanel.set_parameter transaction -- the
    # recompute fails, the plugin reports the error, and the change is
    # rejected (the transaction is aborted)
    doc.BeginTransaction('Set Parameters')
    try:
        try:
            try:
                doc.AddUndo(obj.SetParameters({'text': orig_text + ' x',
                                               'size': obj.size}))
                rejected = 0
            except SketchError:
                # reported by the plugin; reject like the dialog does
                # (AbortTransaction raises AbortTransactionError)
                rejected = 1
                doc.AbortTransaction(warn = 0)
        except AbortTransactionError:
            pass
        finally:
            doc.EndTransaction()
    except BaseException:
        _dump_exc()

    # the object must be untouched: same group and children, the text
    # parameter unchanged, and no undo entry added
    intact = (obj.group is orig_group
              and obj.text == orig_text
              and len(obj.objects) == orig_nobjects
              and orig_nobjects > 0)
    undo_unchanged = len(doc.undo.undoinfo) == n_undo

    # create flow: the PluginPanel.do_apply constructor call -- also
    # rejected, no object is created
    from Sketch.Base import plugins
    info = plugins.object_plugins['LtxObj']
    try:
        info.Constructor()(text = '\\sf missing tools', size = 25.0)
        create_rejected = 0
    except SketchError:
        create_rejected = 1

    sys.stdout.write('LTXMISSING: rejected=%s intact=%s nobjects=%d '
                     'undo-unchanged=%s create-rejected=%s\n'
                     % (rejected, intact, len(obj.objects),
                        undo_unchanged, create_rejected))
    sys.stdout.flush()
    root.after(200, _quit)


root.after(500, body)
root.after(30000, _watchdog)
