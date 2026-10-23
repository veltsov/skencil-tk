# --run-script payload: recompile the LtxObj with a non-ASCII unicode
# text parameter (as the plugin dialog passes it), exercising utf-8
# through the external LaTeX toolchain (pdflatex/latex + pstoedit),
# then save the document.
#
# Environment:
#   SKENCIL_LTX_TEXT  utf-8 encoded text for the plugin parameter
#   SKENCIL_LTX_OUT   path of the saved .sk document
#
# The recompute runs inside the mainloop (like a real Apply click; a
# synchronous body before the mainloop can deadlock in the Tk/pax
# layer) and the process is terminated explicitly with os._exit(0)
# (see smoke_quit.py).
#
# Status is reported as LTXGROUP:ok|empty|error on stdout:
#   ok     the recompute produced a rendered group
#   empty  the toolchain ran, but pstoedit's Sketch driver returned an
#          empty document (pstoedit 3.78 regression; the unicode
#          handling itself is still exercised and the parameter is
#          saved)
#   error  the recompute raised (also exits with status 1)

import os
import sys

import Sketch

app = Sketch.Base.main.application
win = app.main_window
doc = win.document
assert doc is not None, 'no document open'

LTX_TEXT = os.environ['SKENCIL_LTX_TEXT'].decode('utf-8')
OUT = os.environ['SKENCIL_LTX_OUT']


def find_ltxobj(container):
    for obj in container.objects:
        if obj.__class__.__name__ == 'LtxObj':
            return obj
    return None


def patch_write_error(obj):
    # route LaTeX/dvips/pstoedit errors to stdout (sys.stderr is
    # redirected inside the app) and make them raise, so a broken
    # toolchain fails the test quickly instead of opening a modal
    # message box (which hangs an unattended Xvfb run)
    mod = sys.modules[obj.__class__.__module__]
    def write_error(btitle, bmessage):
        sys.stdout.write('LaTeX error (%s):\n%s\n' % (btitle, bmessage))
        sys.stdout.flush()
        raise mod.cm_exc(btitle, bmessage)
    mod.write_error = write_error


def body():
    obj = None
    for layer in doc.layers:
        obj = find_ltxobj(layer)
        if obj is not None:
            break
    assert obj is not None, 'no LtxObj in document'
    patch_write_error(obj)

    status = 'ok'
    # same transaction structure as PluginPanel.do_apply, but print the
    # traceback (AbortTransaction's warn_tb is suppressed by default)
    doc.BeginTransaction(u'Set Parameters')
    try:
        try:
            doc.AddUndo(obj.SetParameters({'text': LTX_TEXT,
                                           'size': obj.size}))
        except:
            import traceback
            traceback.print_exc()
            status = 'error'
            doc.AbortTransaction()
    finally:
        doc.EndTransaction()

    if status == 'ok':
        if obj.group is None:
            status = 'empty'
        sys.stdout.write('LTXGROUP:%s\n' % status)
        sys.stdout.flush()
        from Sketch.Base import plugins
        saver = plugins.find_export_plugin(
            plugins.guess_export_plugin('.sk'))
        saver(doc, OUT)
        sys.stdout.write('latex_recompile: saved %s\n' % OUT)
        sys.stdout.flush()
    else:
        sys.stdout.write('LTXGROUP:error\n')
        sys.stdout.flush()

    root.after(200, _quit_app if status != 'error' else _exit_failed)


def _quit_app():
    root.destroy()
    os._exit(0)


def _exit_failed():
    sys.stdout.flush()
    os._exit(1)


root = app.root
root.after(500, body)
