# --run-script payload: the export options dialog
# (plugindlg.ExportOptionsDlg) for every export plugin with parameters:
# one widget set per parameter, initial values from the given options,
# OK returns the chosen options, an invalid number keeps the dialog
# open, Cancel returns None.  The dialog is built without RunDialog
# (which would wait for the user).

import os

import Sketch
from Sketch.Base import plugins
from Sketch.UI.plugindlg import ExportOptionsDlg

app = Sketch.Base.main.application
win = app.main_window
doc = win.document
root = app.root


def _dump_exc():
    # write the traceback to the real stderr (fd 2) -- sys.stderr is
    # redirected inside the app -- and fail loudly
    import traceback
    os.write(2, traceback.format_exc().encode())
    os._exit(1)


def check(info):
    options = info.GetOptions(doc)
    names = [param[0] for param in info.parameters]
    # start from a non-default choice
    options['box'] = 1
    dialog = ExportOptionsDlg(root, info, options)
    assert [var.name for var in dialog.vars] == names, dialog.vars
    for var in dialog.vars:
        assert var() == options[var.name], (info.format_name, var.name)
    vars = dict((var.name, var) for var in dialog.vars)
    vars['box'](0)
    dialog.ok()
    expected = dict(options, box = 0)
    assert dialog.result == expected, (dialog.result, expected)

    dialog = ExportOptionsDlg(root, info, options)
    if 'eps_dpi' in names:
        vars = dict((var.name, var) for var in dialog.vars)
        vars['eps_dpi'](5)
        dialog.ok()
        # still open: the warning is printed in headless mode
        assert dialog.top.winfo_exists(), info.format_name
        assert dialog.result is None
        vars['eps_dpi'](600)
        dialog.ok()
        assert dialog.result['eps_dpi'] == 600, dialog.result
    else:
        dialog.cancel()
        assert dialog.result is None
        assert not dialog.top.winfo_exists()


def _body():
    assert doc is not None, 'no document open'
    checked = []
    for info in plugins.export_plugins:
        if info.parameters:
            check(info)
            checked.append(info.format_name)
    assert sorted(checked) == ['PDF', 'SVG'], checked


def body():
    try:
        _body()
    except BaseException:
        _dump_exc()
    root.destroy()
    os._exit(0)


root.after(500, body)
