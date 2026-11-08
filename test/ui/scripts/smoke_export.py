# --run-script payload: export the opened document through the main
# window's SaveToFile (the path of File->Export) with every export
# plugin, then through File->Export itself and Export Again, and save
# it gzip-compressed (py3 regression guard: the PDF filters and the
# compressed save piped str into binary pipes, WMF packed str and
# floats, ExportAgain passed an unknown keyword, and File->Export did
# not enable Export Again).  The files go to $SKENCIL_EXPORT_DIR; the
# test checks them.

import os

import Sketch
from Sketch.Base import plugins

app = Sketch.Base.main.application
win = app.main_window
doc = win.document
root = app.root
outdir = os.environ['SKENCIL_EXPORT_DIR']


def _dump_exc():
    # write the traceback to the real stderr (fd 2) -- sys.stderr is
    # redirected inside the app -- and fail loudly
    import traceback
    os.write(2, traceback.format_exc().encode())
    os._exit(1)


def _body():
    assert doc is not None, 'no document open'
    for info in plugins.export_plugins:
        filename = os.path.join(outdir, 'export.' + info.format_name)
        win.SaveToFile(filename, info.format_name)
    # File->Export with the file dialog answered, then Export Again,
    # which the export must have enabled
    filename = os.path.join(outdir, 'interactive.pdf')
    app.GetSaveFilename = lambda **kw: filename
    win.exporttype.set(plugins.find_export_plugin('PDF').tk_file_type[0])
    assert not win.commands.ExportAgain.sensitive
    win.SaveToFileInteractive(2)
    command = win.commands.ExportAgain
    assert command.sensitive, 'Export Again is not enabled'
    assert command.menu_name.endswith('interactive.pdf'), command.menu_name
    os.remove(filename)
    command.Invoke()
    # compressed native save
    filename = os.path.join(outdir, 'compressed.sk')
    win.SaveToFile(filename, plugins.NativeFormat, 'gzip', filename + '.gz')


def body():
    try:
        _body()
    except BaseException:
        _dump_exc()
    root.destroy()
    os._exit(0)


root.after(500, body)
