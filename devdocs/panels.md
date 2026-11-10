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

Docked: collapse toggle (left), title, Undock, Close (right).  An
undocked window (docking on) gets a strip with a Dock button above the
body.  Colors: those of a highlighted menu item, read from a temporary
`Menu` (`sidebar.title_colors`).  Bitmaps are ASCII art in
`sidebar._bitmaps`.

## Docking, keys and preferences

Each open panel has a `layout_key`: `'<module>.<class>'` for
`CreateDialog` panels, `'plugin:<class_name>'` for plugin panels;
`MainWindow.OpenPanel(key)` opens a panel from its key.

| Preference | Meaning |
|---|---|
| `panel_docking` | docking on (default) / all panels as windows |
| `panel_floating` | keys of panels the user undocked; they open as windows |
| `panel_layout` | keys of the panels open at Exit, docked ones top to bottom first; reopened at startup (`MainWindow.Run`) |
| `panel_states` | key → `(body height or None, collapsed)` of docked panels, updated on close and at Exit |
| `sidebar_width` | width of the side bar |
| `window_geometry`, `window_maximized` | main window, saved at Exit, restored at startup unless `--geometry` is given; a saved size larger than the screen opens maximized |

The container is chosen when a panel is created: `MainWindow` sets
`opening_key` around the construction and `DockNewPanel()` answers
from `panel_floating`.  Moving a panel (Undock/Dock buttons,
`SetPanelDocked`; the Options checkbox, `RedockPanels`) closes it and
opens it again from its key, so unapplied field values are lost.

The layout is saved by `MainWindow.Exit` only (not when the process is
killed).

## Tests

`test/ui/scripts/smoke_sidebar.py`: stacking, scrollbar, collapse,
grip, close, hide/show, plugin panel reuse, non-dockable panels,
layout save/restore, undock/dock, switching docking.
`smoke_links.py` resizes the side bar when the panel is docked.

## Open items

- Keyboard traversal (Tab) in docked panels is counterintuitive.
- Moving a panel does not keep unapplied field values (a
  `get_state`/`set_state` hook per panel would).
- No drag-and-drop docking or reordering; order follows opening order.
