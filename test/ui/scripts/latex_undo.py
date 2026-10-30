# --run-script payload: exact-state undo/redo of LtxObj parameter
# changes with a working LaTeX toolchain.  Two successful recomputes
# (each runs the toolchain), then Undo/Redo must restore the exact
# previous rendering -- byte-identical saved documents -- without
# running the toolchain again (an exec_command wrapper counts the
# runs).  See test_latex.py::test_latex_undo_exact_state.

import os
import sys

import Sketch

app = Sketch.Base.main.application
doc = app.main_window.document
root = app.root

OUT = os.environ['SKENCIL_LTX_OUT']

import Sketch.Plugins.Objects.latextext as mod

calls = {'n': 0}
_real_exec_command = mod.exec_command
def _counting_exec_command(command):
    calls['n'] = calls['n'] + 1
    return _real_exec_command(command)
mod.exec_command = _counting_exec_command


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
    os.write(2, b'latex_undo: watchdog fired (180s)\n')
    os._exit(42)


def apply_params(obj, kw):
    # the PluginPanel.set_parameter transaction
    doc.BeginTransaction('Set Parameters')
    try:
        doc.AddUndo(obj.SetParameters(kw))
    finally:
        doc.EndTransaction()


def _save(path):
    from Sketch.Base import plugins
    saver = plugins.find_export_plugin(plugins.guess_export_plugin('.sk'))
    saver(doc, path)


def _body():
    obj = None
    for layer in doc.layers:
        obj = find_ltxobj(layer)
        if obj is not None:
            break
    assert obj is not None, 'no LtxObj in document'

    t0 = obj.Text()
    n0 = calls['n']

    # two successful recomputes, saving the state after each
    apply_params(obj, {'text': t0 + ' A', 'size': obj.size})
    _save(OUT + '.A')
    n_a = calls['n']
    apply_params(obj, {'text': t0 + ' B', 'size': obj.size})
    _save(OUT + '.B')
    n_b = calls['n']
    assert n_b > n_a, 'the second apply did not run the toolchain'

    # Undo: the exact state after the first apply, no toolchain run
    doc.Undo()
    _save(OUT + '.A-undo')
    n_undo = calls['n']

    # Redo: the exact state after the second apply, no toolchain run
    doc.Redo()
    _save(OUT + '.B-redo')
    n_redo = calls['n']

    sys.stdout.write('LTXUNDO: runs=%d undo-runs=%d redo-runs=%d\n'
                     % (n_b - n0, n_undo - n_b, n_redo - n_undo))
    sys.stdout.flush()
    root.after(200, _quit)


def body():
    try:
        _body()
    except BaseException:
        _dump_exc()


root.after(500, body)
root.after(180000, _watchdog)
