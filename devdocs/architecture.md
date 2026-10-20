# Architecture

## Package bootstrap (`src/Sketch/__init__.py`)

The `Sketch` package is unusual and central to understanding the code:

- It inserts `Modules/` and `Base/` into its own `__path__`, so modules
  like `config`, `undo`, `connector`, `warn`, `skexceptions`, `plugins`,
  `loadres` (in `Sketch/Base/`) are importable as top-level names
  (`import config`, not `import Sketch.Base.config`).
- It inserts `Modules/` into `sys.path[1:]`, so the C extensions
  (`_sketch`, `pax`, `paxtkinter`, `streamfilter`, `pstokenize`,
  `skreadmodule`, `_type1module`, `intl`) are importable top-level too.
- It sets up gettext through the custom `intl` extension (fallback:
  identity functions), defines `_`.
- It imports and re-exports almost the whole graphics model so user code
  does `from Sketch import Trafo, PolyBezier, ...`.
- `_import_PIL()` imports PIL (package or old top-level `Image`) and
  patches `sys.modules` so `PIL.Image` always works.
- `init_ui()` imports `paxtkinter` and replaces `sys.modules['_tkinter']`
  with it **before** Tk is imported, then `init_lib()` (loads user
  preferences, `Issue(INITIALIZE)`) and imports the standard scripts from
  `config.preferences.standard_scripts`.
- `init_modules_from_widget(root)` imports `pax`, initializes
  `UI.tkext` from the Tk app (`pax.create_tcl_commands(tk)`), etc.

## Layers

### `Sketch/Base/` — application framework, no Tk, no graphics
- `config.py` — global config; defaults, path setup (`init_directories`),
  user preferences handling (`preferences` object), font path, plugin
  directories, `SKETCH_FONTPATH` support.
- `configutil.py` — preferences/persistence helpers.
- `main.py` — `main()`, option parsing (`-d`, `-g/--geometry`,
  `--run-script`, `--version`, `-geometry` hack).
- `connector.py` — **pub/sub machinery** (Publisher, Issue, Subscribe,
  Connect/Disconnect) used everywhere for change notifications.
- `undo.py`, `undodict.py` — undo/redo framework (Undo, UndoList,
  CreateListUndo, ...); graphics objects return undo entries from
  mutation methods.
- `plugins.py` — plugin loading (`__import__` + `exec` based), plugin
  initialization, `create_packages`.
- `load.py` — file type detection and dispatch to import filters;
  `load_drawing()`.
- `loadres.py` — resource loading (uses `skreadmodule`).
- `warn.py` — warning/debug system (`warn`, USER/INTERNAL levels).
- `gtkutils.py` — **name is legacy**: contains Tk font/color helpers
  (`ColorScheme`, `set_ui_font`, color conversion). The `gtk3utils` git
  branch was an experiment (partially reverting to gtk for fonts/colors)
  that was abandoned; commit "Remove attempts to set fonts and colors via
  gtk. Modern tk is good enough..." is the state on master.
- `skexceptions.py`, `const.py` — exceptions and event/constants.

### `Sketch/Graphics/` — the document model and rendering (no Tk)
- `base.py` — `GraphicsObject`, `Primitive`: base classes with property
  stack, undo, publisher pattern.
- `document.py` (2477 lines) — `EditDocument`, layers/pages, commands;
  `selection.py` — selection handling; `layer.py`, `guide.py`,
  `compound.py`, `group.py`, `maskgroup.py`, `clone.py`, `blendgroup.py`.
- Shape classes: `rectangle.py`, `ellipse.py`, `bezier.py` (1444 lines,
  with `curveop.py` boolean ops), `text.py`, `image.py`, `eps.py`,
  `external.py` (linked images; the fork added automatic reloading — see
  `reloaddlg.py`).
- Properties: `properties.py` (`Style`, `FillStyle`, `LineStyle`,
  `PropertyStack`), `color.py`, `pattern.py` (solid, hatching, gradients,
  image tiles), `dashes.py`, `arrow.py`, `font.py`, `gradient.py`,
  `pagelayout.py`, `papersize.py`.
- Rendering: `psdevice.py` — `PostScriptDevice`; `graphics.py` (1687
  lines) — `GraphicsDevice`, `SimpleGC`, `InvertingDevice`,
  `HitTestDevice`. Drawing is device-based: the same drawing code renders
  to screen (Tk via pax/GC) and to PostScript/PDF.
- `plugobj.py` — `PluginCompound`/`TrafoPlugin` base classes for plugin
  objects.

### `Sketch/UI/` — Tk interface
- `skapp.py` — `SketchApplication` (Tk root, preferences, mainloop).
- `mainwindow.py` (1389 lines) — main window, menus, commands.
- `canvas.py` (1955 lines) — the drawing canvas widget (uses pax-backed
  tkext widget for fast rendering), event handling, tools/modes
  (`modes.py`), `view.py`/`viewport.py` (zoom/pan; fork added middle-mouse
  scroll and wheel zoom), `ruler.py`, `miniscroll.py`.
- `tkext.py` (950 lines) — Tk widget extensions, the bridge to `pax`
  (`pax.register_object`, `InitFromTkapp`, `UpdateWhenIdle`, ...).
- Dialogs: `filldlg.py`, `linedlg.py`/`styledlg.py`, `colordlg.py`,
  `fontdlg.py`, `curvedlg.py`, `guidedlg.py`, `griddlg.py`,
  `layoutdlg.py`, `layerdlg.py`, `aligndlg.py`, `blenddlg.py`,
  `gradientedit.py`, `optiondlg.py`, `export.py`, `printdlg.py`,
  `plugindlg.py`, `reloaddlg.py`.
- `skpixmaps.py` — loads pixmaps from `Resources/Pixmaps`.
- `prompt.py` — the command-line prompt window (has `exec`).
- `command.py` — command infrastructure (`RegisterCommands`).

### `Sketch/Lib/` — pure-python helper libs
- `type1.py`, `encoding.py` — Type 1 font parsing (with `_type1module`
  for decryption), font metrics.
- `dscparser.py`, `psmisc.py` — PostScript/DSC parsing (EPS import).
- `units.py`, `util.py`, `skcompleter.py`.

### `Sketch/Modules/`
Only `X.py` (X11 constants) is Python here; the C extension `.so` files
appear here only after `build&copy`.

### C extensions (`src/extensions/`, built into `Sketch.Modules.*`)
- `Modules/_sketchmodule.c` — the core: `Point`, `Rect`, `Trafo`
  (2D affine), `CreatePath`/curve objects (`curveobject.c`,
  `curvefunc.c`, `curvedraw.c`, `curvelow.c`), color (`skcolor.c`),
  font metrics (`skfm.c`), image dithering (`skimage.c`), plus misc
  helpers (`skaux.c`, `skreadmodule`-style fast parsing).
- `Modules/skreadmodule.c` — `skread.parse_sk_line2` used by the .sk
  loader to parse save-file lines safely (eval-like parsing).
- `Modules/pstokenize.c` (+ `pschartab.c`) — PostScript tokenizer
  (EPS/PDF import).
- `Modules/_type1module.c` — Type 1 font decryption.
- `Filter/streamfilter.c` + filters — stream abstraction with
  Base64Decode, SubFileDecode, HexFilter, ASCII85, zlib; imported
  top-level, e.g. `from streamfilter import Base64Decode, SubFileDecode`.
- `Pax/paxmodule.c` + `paxtkinter.c` — the X11/Tk rendering layer:
  `paxtkinter` wraps/replaces `_tkinter` (patching the Tk event loop and
  object registration); `pax` provides off-screen X11 pixmaps, GC
  objects, windows (`tkwinobject.c`), regions, clipping, fonts, images,
  and registers Tcl commands; used by `Sketch/UI/tkext.py`,
  `canvas.py`, `ruler.py`, `miniscroll.py`, `gradientedit.py`.
  See `devdocs/paxtkinter-analysis.md` for why `paxtkinter` exists
  (GIL/TclLock design) and the plan to drop it in favor of stock
  `_tkinter` (branch `modernize`).
- `Pax/intl.c` — gettext bindings (`Sketch.Modules.intl`).
- `Pax/Generate/` — code generator script (`mkgc.py`) for GC methods.
- Small patches exist: `skcolor.c.patch`, `skpoint.c.patch`,
  `skrect.c.patch` (leftovers; check whether applied before using).

### Plugins (`src/Plugins/`)
- `Filters/` — loaders/savers registered through
  `Sketch/Base/plugins.py`:
  - Import: `skloader.py` (native `.sk` format, uses `skread`),
    `svgloader.py`, `ailoader.py` (Adobe Illustrator), `wmfloader.py`,
    `cmxloader.py`, `xfigloader.py`, `cgmloader.py`,
    `drawinput.py`, plus gzip/bzip-wrapping loaders.
  - Export: `sksaver.py`, `epssaver.py`, `pssaver.py`, `svgsaver.py`,
    `aisaver.py`, `wmfsaver.py`, and the fork's working PDF export:
    `pdfsaver.py`, `pdfsaverbox.py`, `pdfsaverpage.py`.
  - `Lib/` — helper libs for formats (e.g. `drawfile.py`).
- `Objects/` — plugin compound objects: `arrow.py`, `regpoly.py`,
  `lcdtext.py`, `multilinetext.py` (with `Lib/multilinetext/`),
  `autoshapeplugin.py` (with `Lib/autoshapes/`), `latextext.py`
  (renders LaTeX text; made robust in this fork).

### Scripts (`src/Script/`)
Python modules that are also user-callable scripts (Scripts menu /
`--run-script`): e.g. `create_star.py`, `transform.py`, `TeX.py`,
`reload_image.py`, `export_raster.py`, `pathutils/` package. Enabled via
`config.preferences.standard_scripts`.

## Data flow / rendering

- Document objects are `GraphicsObject`s with a `PropertyStack`. They
  draw themselves onto a device (`GraphicsDevice` subclass): on screen a
  device backed by Tk/pax GC; for export a `PostScriptDevice`.
- Changes go through undo-returning methods; notifications are
  distributed by `connector.Issue` with constants from `Sketch/const.py`
  (e.g. `CHANGED`).
- Files are loaded via `Sketch/Base/load.py` → plugin loader → document;
  saved via the corresponding saver plugin.

## Distribution / packaging

- `setup.py` (distutils): `build`, `install`, `sdist`, `bdist_rpm`,
  `build_locales`, plus the custom `build&copy` and Debian (`DEBIAN=1`)
  packaging logic (see `DEBIAN/`, `AppDir/`).
- The package list and `package_dir` mapping in `setup.py` must be
  updated when adding packages (e.g. `Plugins.Objects.Lib.autoshapes`
  also declares icon data files).

