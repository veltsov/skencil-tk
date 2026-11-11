# Panels: Windows and the Side Bar

Status: implemented on the `sidebar-panels` branch.  The non-modal
panels (Windows menu, plugin object panels) open either docked in a
side bar at the right of the main window (default) or as separate
windows.  Modal dialogs (`SKModal`) are not affected.

## Structure

| Piece | Where | Role |
|---|---|---|
| `SketchPanel` | `UI/sketchdlg.py` | base of all panels; builds into `self.top`, which is the *body* of a container |
| `WindowContainer` | `UI/sidebar.py` | a `Toplevel` with the body frame inside; position in `dlg_pos_<class>` |
| `DockContainer` | `UI/sidebar.py` | a frame in the side bar: app-drawn title bar, body, height grip |
| `SideBar` | `UI/sidebar.py` | scrollable column of `DockContainer`s (canvas + embedded frame, scrollbar shown only when needed) |
| panel registry | `UI/mainwindow.py` | `dialogs`, `CreateDialog`, `CreatePluginDialog`, `OpenPanel`, layout save/restore |
| `FlowFrame` | `UI/tkext.py` | wraps widgets into rows by the available width (Curve buttons, Page Layout size fields) |

The main window puts the canvas frame and the side bar into a
horizontal `tkinter.PanedWindow` (`MainWindow.panes`); the side-bar
pane is added with the first visible docked panel and removed with the
last one, so without docked panels the canvas has the full width.

`SketchPanel.__init__` calls `create_container()`, then `build_dlg()`
into `self.top` (= `container.body`), then `container.after_build()`.
Panels never touch the toplevel; the only container interface they may
rely on is that `self.top` is a frame of class `class_name` (the option
database resources `*SKPanel*...` apply to it).  Do not call
Toplevel-only methods (`resizable`, `geometry`, `title`, ...) on it.

Container interface: `body`, `after_build()`, `show_raise()`,
`withdraw()`, `save_prefs()`, `get_state()`/`set_state()`, `destroy()`.

## Panel attributes

- `dockable = 1`: `0` keeps the panel a window (Print, Reload Modules).
- `resize_policy = 'fixed'`: the docked body has its natural height.
  `'elastic'`: the layout absorbs any height (lists, text fields); the
  docked panel gets a grip at the bottom (drag: height, double click:
  natural height).  Elastic: Layers, Styles, Fill, Fonts, Guide Lines,
  Auto Shapes, plugin panels with a multi-line text parameter (LaTeX).

Width is always given by the side bar.  Layout rules for panels: grid
with `weight` on the stretching column/row, lists with scrollbars that
take the extra height, one column rather than side-by-side groups
(see the Font panel), `FlowFrame` for button groups.

## Title bars

Docked: collapse toggle (left), title, Undock, Close (right).  Colors:
those of a highlighted menu item, read from a temporary `Menu`
(`sidebar.title_colors`).  Bitmaps are ASCII art in `sidebar._bitmaps`.

A click on the title collapses/expands the panel; dragging the title
(more than `drag_threshold` pixels) moves the panel within the side bar
(`DockContainer.title_*` → `SideBar.DragMotion`/`DragEnd`/`MovePanel`).
A line in the title colors (`dropmarker`, placed over the panels) marks
the gap it goes to, the side bar scrolls when the pointer is near its top
or bottom edge, and releasing outside the side bar cancels.  Dragging
does not dock or undock (the buttons and the menu do).

An undocked panel window has no extra decoration: it goes back to the
side bar through Windows/Dock Dialog, a submenu rebuilt each time it is
opened (`MainWindow.make_dock_menu`, `UpdatedMenu` with `auto_rebuild`)
that lists the undocked panel windows by title (not those hidden by
Hide Dialogs; a shaded window, which Tk sees as iconic, is listed and
docks collapsed), plus "All" when there are
several; the cascade is disabled when there is nothing to dock
(`MenuCascade` with `sensitivecb`).  The window manager's minimize
button is not an option: panel windows are transient (dialogs, without
minimize in most window managers) and X11 has no protocol to intercept
minimizing.

## Docking, keys and preferences

Each open panel has a `layout_key`: `'<module>.<class>'` for
`CreateDialog` panels, `'plugin:<class_name>'` for plugin panels;
`MainWindow.OpenPanel(key)` opens a panel from its key.

| Preference | Meaning |
|---|---|
| `panel_docking` | docking on (default): panels docked unless in `panel_floating`; off: all panels are windows, without the Undock button, Dock Dialog disabled (`panel_floating`, `panel_layout`, `panel_states` are kept for when it is switched on again) |
| `panel_floating` | keys of panels the user undocked; they open as windows |
| `panel_layout` | keys of the docked panels open at Exit, top to bottom; reopened at startup (`MainWindow.Run`). Panel windows are not reopened, only their position is remembered, as without docking |
| `panel_states` | key → `(body height or None, collapsed)` of docked panels, updated on close and at Exit. The height is restored whenever the panel is opened; the collapsed state only at startup and when the panel moves (`reopen_panels`) — opened from the menu, a panel is expanded |
| `sidebar_width` | width of the side bar |
| `window_geometry`, `window_maximized` | main window, saved at Exit, restored at startup unless `--geometry` is given; a saved size larger than the screen opens maximized |

The container is chosen when a panel is created: `MainWindow` sets
`opening_key` around the construction and `DockNewPanel()` answers
from `panel_floating`.  Moving a panel (Undock button, Dock Dialog,
`SetPanelDocked`; the Options checkbox, `RedockPanels`) closes it and
opens it again from its key, so unapplied field values are lost.

The layout is saved by `MainWindow.Exit` only (not when the process is
killed).

## Keyboard focus

The panel widgets have `takeFocus 0` (`*SKPanel*takeFocus` in
`Resources/Misc/tkdefaults`), so Tk's standard traversal skips them.
Tab / Shift-Tab (`<<PrevWindow>>`) are bound on the toplevel instead
(`SideBar.traverse`, `WindowContainer.traverse`): they cycle through the
enabled, shown input fields (Entry, Spinbox, Text; `sidebar.focus_fields`)
of all docked panels, top to bottom, or of the panel window.  Outside
the side bar Tk's traversal applies.  A Text field keeps Tab for itself;
Ctrl-Tab leaves it.

A docked field is in the same toplevel as the canvas, so the window
manager does not give the focus back to the canvas: the canvas takes the
focus on every button press (`SketchCanvas.ButtonPressEvent`).

## Tests

`test/ui/scripts/smoke_sidebar.py`: stacking, scrollbar, collapse,
grip, Tab traversal and canvas focus, close, hide/show, plugin panel
reuse, non-dockable panels,
layout save/restore, undock/dock, switching docking, reordering by
dragging.
`smoke_links.py` resizes the side bar when the panel is docked.

## Open items

- Moving a panel does not keep unapplied field values (a
  `get_state`/`set_state` hook per panel would).
- No docking or undocking by dragging (by choice: panel windows have no
  app-drawn handle).
