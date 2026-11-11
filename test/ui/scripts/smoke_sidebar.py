# --run-script payload: with docked panels, open several panels in the
# side bar (also a plugin panel twice), check the scrollbar, collapse,
# resize and close them, check that a non-dockable panel opens as a
# window, save and restore the layout, switch between windows and
# docked panels and check that the side bar disappears with the last
# panel, then quit.

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

    # Tab cycles through the fields of the docked panels; a click on the
    # canvas takes the focus back
    from Sketch.UI.sidebar import focus_fields
    fields = []
    for dock in sidebar.docks:
        fields.extend(focus_fields(dock.body))
    line_fields = focus_fields(win.dialogs['LinePanel'].top)
    poly_fields = focus_fields(win.dialogs['RegularPolygon'].top)
    assert line_fields and poly_fields
    assert fields.index(line_fields[0]) < fields.index(poly_fields[0])
    root.focus_force()
    fields[0].focus_set()
    root.update()
    def focus():
        return str(root.focus_get())
    assert focus() == str(fields[0]), focus()
    fields[0].event_generate('<Tab>')
    root.update()
    assert focus() == str(fields[1]), focus()
    fields[1].event_generate('<<PrevWindow>>')
    fields[0].event_generate('<<PrevWindow>>')
    root.update()
    assert focus() == str(fields[-1]), focus()
    fields[-1].event_generate('<Tab>')
    root.update()
    assert focus() == str(fields[0]), focus()
    win.canvas.event_generate('<ButtonPress-1>', x = 5, y = 5)
    win.canvas.event_generate('<ButtonRelease-1>', x = 5, y = 5)
    root.update()
    assert focus() == str(win.canvas), focus()

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

    # the layout is saved and restored: order, heights, collapsed
    keys = [dialog.layout_key for dialog in sidebar.Panels()]
    assert keys == ['Sketch.UI.aligndlg.AlignPanel',
                    'Sketch.UI.linedlg.LinePanel',
                    'Sketch.UI.styledlg.StylePanel',
                    'plugin:RegularPolygon'], keys
    win.dialogs['StylePanel'].container.set_height(150)
    win.dialogs['LinePanel'].container.set_collapsed(1)
    win.save_panel_layout()
    assert config.preferences.panel_layout == keys
    from Sketch.Base.configutil import save_repr
    for name in ('panel_layout', 'panel_states'):
        value = getattr(config.preferences, name)
        assert eval(save_repr(value)) == value, value
    for dialog in list(win.dialogs.values()):
        if dialog.dockable:
            dialog.close_dlg()
    root.update()
    assert not sidebar.docks
    win.restore_panel_layout()
    root.update()
    assert [dialog.layout_key for dialog in sidebar.Panels()] == keys
    assert win.dialogs['StylePanel'].container.body.winfo_height() == 150
    assert win.dialogs['LinePanel'].container.collapsed
    assert not win.dialogs['AlignPanel'].container.collapsed

    # opened from the menu, a panel is expanded: an open one and one
    # that was collapsed when it was closed
    win.CreateDialog('Sketch.UI.linedlg', 'LinePanel')
    assert not win.dialogs['LinePanel'].container.collapsed
    win.dialogs['LinePanel'].container.set_collapsed(1)
    win.dialogs['RegularPolygon'].container.set_collapsed(1)
    win.dialogs['RegularPolygon'].close_dlg()
    assert config.preferences.panel_states['plugin:RegularPolygon'][1]
    win.CreatePluginDialog(info)
    root.update()
    assert not win.dialogs['RegularPolygon'].container.collapsed
    assert [dialog.layout_key for dialog in sidebar.Panels()] == keys

    # undock a panel with the button in its title bar and dock it again
    # with Windows/Dock Dialog; the choice is saved
    dock = win.dialogs['StylePanel'].container
    dock.frame.nametowidget('titlebar.undock').event_generate(
        '<ButtonRelease-1>')
    root.update()
    panel = win.dialogs['StylePanel']
    assert panel.top.winfo_toplevel() != root
    assert config.preferences.panel_floating == [
        'Sketch.UI.styledlg.StylePanel']
    assert [dialog.layout_key for dialog in sidebar.Panels()] == \
           [keys[0], keys[1], keys[3]]
    # the panel windows are not opened again at startup
    win.save_panel_layout()
    assert config.preferences.panel_layout == [keys[0], keys[1], keys[3]]
    panel.close_dlg()
    win.OpenPanel(keys[2])
    root.update()
    panel = win.dialogs['StylePanel']
    top = panel.top.winfo_toplevel()
    assert top != root and 'titlebar' not in top.children
    assert win.undocked_panels() == [panel]
    entries = win.make_dock_menu()
    assert [entry.rest['label'] for entry in entries] == ['Styles'], entries
    entries[0]._call_cmd()
    root.update()
    assert not win.undocked_panels()
    panel = win.dialogs['StylePanel']
    assert panel.top.winfo_toplevel() == root
    assert config.preferences.panel_floating == []
    # docked again at the end
    assert [dialog.layout_key for dialog in sidebar.Panels()] == \
           [keys[0], keys[1], keys[3], keys[2]]
    assert panel.container.body.winfo_height() == 150
    keys = [keys[0], keys[1], keys[3], keys[2]]

    # switch to windows and back: the panels move, in their order; with
    # docking off, Dock Dialog has nothing to dock; switched on again,
    # the panel the user undocked stays a window
    win.SetPanelDocked(win.dialogs['AlignPanel'], 0)
    root.update()
    floating = ['Sketch.UI.aligndlg.AlignPanel']
    assert config.preferences.panel_floating == floating
    docked = keys[1:]
    config.preferences.panel_docking = 0
    win.RedockPanels()
    root.update()
    assert not sidebar.docks
    assert len(win.dialogs) == 5
    for dialog in win.dialogs.values():
        top = dialog.top.winfo_toplevel()
        assert top != root
    assert not win.undocked_panels()
    assert config.preferences.panel_floating == floating
    config.preferences.panel_docking = 1
    win.RedockPanels()
    root.update()
    assert [dialog.layout_key for dialog in sidebar.Panels()] == docked
    assert win.dialogs['LinePanel'].container.collapsed
    assert win.undocked_panels() == [win.dialogs['AlignPanel']]
    # several undocked panels: Dock Dialog has an entry for all of them
    win.SetPanelDocked(win.dialogs['LinePanel'], 0)
    root.update()
    assert len(win.undocked_panels()) == 2
    # hidden panel windows are not offered
    win.HideDialogs()
    root.update()
    assert not win.undocked_panels()
    win.ShowDialogs()
    root.update()
    assert len(win.undocked_panels()) == 2
    # a shaded window (iconic for Tk) is offered and docks collapsed
    line = win.dialogs['LinePanel']
    # (under Xvfb there is no WM to shade it)
    line.top.winfo_toplevel().state = lambda: 'iconic'
    root.update()
    assert line in win.undocked_panels()
    entries = win.make_dock_menu()
    assert entries[-1].rest['label'] == 'All', entries
    entries[-1]._call_cmd()
    root.update()
    assert not win.undocked_panels()
    assert config.preferences.panel_floating == []
    assert [dialog.layout_key for dialog in sidebar.Panels()][-2:] == \
           ['Sketch.UI.aligndlg.AlignPanel', 'Sketch.UI.linedlg.LinePanel'] \
           or [dialog.layout_key for dialog in sidebar.Panels()][-2:] == \
           ['Sketch.UI.linedlg.LinePanel', 'Sketch.UI.aligndlg.AlignPanel']
    assert win.dialogs['LinePanel'].container.collapsed
    assert not win.dialogs['AlignPanel'].container.collapsed

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
