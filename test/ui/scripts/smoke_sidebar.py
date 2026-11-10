# --run-script payload: with docked panels, open several panels in the
# side bar (also a plugin panel twice), check the scrollbar, collapse,
# resize and close them, check that a non-dockable panel opens as a
# window and that the side bar disappears with the last panel, then
# quit.

import os
import sys

import Sketch
from Sketch.Base import config, plugins

app = Sketch.Base.main.application
win = app.main_window
root = app.root


def check():
    config.preferences.panel_docking = 1
    sidebar = win.sidebar
    assert str(sidebar) not in [str(w) for w in win.panes.panes()]

    for module, name in (('layerdlg', 'LayerPanel'),
                         ('aligndlg', 'AlignPanel'),
                         ('griddlg', 'GridPanel'),
                         ('linedlg', 'LinePanel'),
                         ('styledlg', 'StylePanel')):
        win.CreateDialog('Sketch.UI.' + module, name)
    info = plugins.object_plugins['RegularPolygon']
    win.CreatePluginDialog(info)
    win.CreatePluginDialog(info)
    root.update()
    assert str(sidebar) in [str(w) for w in win.panes.panes()]
    assert len(sidebar.docks) == 6, sidebar.docks
    for dialog in win.dialogs.values():
        assert dialog.top.winfo_toplevel() == root
    # 6 panels do not fit in 650 pixels: the scrollbar is shown
    assert sidebar.vbar.winfo_ismapped()
    # the side bar was scrolled to the last panel shown
    first, last = sidebar.canvas.yview()
    assert last == 1.0, (first, last)

    # collapse: only the title bar is left
    dock = win.dialogs['LayerPanel'].container
    height = dock.frame.winfo_height()
    dock.toggle_collapsed()
    root.update()
    assert not dock.body.winfo_ismapped()
    assert dock.frame.winfo_height() < height
    win.dialogs['LayerPanel'].deiconify_and_raise()
    root.update()
    assert not dock.collapsed and dock.body.winfo_ismapped()

    # resize the body of a panel
    dock.set_height(200)
    root.update()
    assert dock.body.winfo_height() == 200, dock.body.winfo_height()
    dock.set_height(None)
    root.update()
    assert dock.body.winfo_height() == dock.body.winfo_reqheight()

    # drag the grip of an elastic panel
    win.CreateDialog('Sketch.UI.guidedlg', 'GuidePanel')
    root.update()
    dock = win.dialogs['GuidePanel'].container
    assert dock.grip.winfo_ismapped()
    height = dock.body.winfo_height()
    dock.grip.event_generate('<ButtonPress-1>', x = 2, y = 2)
    dock.grip.event_generate('<Motion>', x = 2, y = 52, state = 0x100)
    dock.grip.event_generate('<ButtonRelease-1>', x = 2, y = 52)
    root.update()
    assert dock.body.winfo_height() == height + 50, \
           (height, dock.body.winfo_height())
    assert not win.dialogs['AlignPanel'].container.grip.winfo_ismapped()
    win.dialogs['GuidePanel'].close_dlg()

    # hide and show all
    win.HideDialogs()
    root.update()
    assert str(sidebar) not in [str(w) for w in win.panes.panes()]
    win.ShowDialogs()
    root.update()
    assert str(sidebar) in [str(w) for w in win.panes.panes()]

    # close through the title bar and through the panel
    dock = win.dialogs['LayerPanel'].container
    dock.frame.nametowidget('titlebar.close').event_generate(
        '<ButtonRelease-1>')
    win.dialogs['GridPanel'].close_dlg()
    root.update()
    assert 'LayerPanel' not in win.dialogs
    assert len(sidebar.docks) == 4

    # the print panel is not dockable
    win.CreateDialog('Sketch.UI.printdlg', 'PrintPanel')
    assert win.dialogs['PrintPanel'].top.winfo_toplevel() != root
    assert len(sidebar.docks) == 4

    for dialog in list(win.dialogs.values()):
        dialog.close_dlg()
    root.update()
    assert not sidebar.docks
    assert str(sidebar) not in [str(w) for w in win.panes.panes()]
    sys.stdout.write('SIDEBAR-OK\n')
    sys.stdout.flush()


def _run():
    try:
        check()
    except Exception:
        import traceback
        traceback.print_exc()
    root.destroy()
    os._exit(0)


root.after(1000, _run)
