# Architecture

## Package bootstrap (`src/Sketch/__init__.py`)

The `Sketch` package is unusual and central to understanding the code:

- One canonical real-package tree with absolute imports everywhere;
  no implicit relative imports, no `sys.path`/`__path__` manipulation,
  no fake packages. The C extensions are built and imported under
  their real names (`Sketch.Modules.{pax,_sketch,streamfilter,
  pstokenize,skread,_type1}`).
- It sets up localization with the standard `gettext` module
  (per-domain caching shim), defines `_`.
- It imports and re-exports almost the whole graphics model so user code
  does `from Sketch import Trafo, PolyBezier, ...`.
- It initializes PIL (`from PIL import Image`; PIL is the application's
  only third-party dependency) and loads config
  (`config.init_directories`).
- `init_ui()` loads user preferences via `init_lib()` and imports the
  standard scripts.
- `init_modules_from_widget(root)` imports `pax`, initializes
  `UI.tkext` from the Tk app (`pax.create_tcl_commands(tk)`), etc.

## Layers

### `Sketch/Base/` — application framework, no Tk, no graphics
- `config.py` — global config; defaults, path setup (`init_directories`),
  user preferences handling (`preferences` object), font path, plugin
  directories, `SKETCH_FONTPATH` support.
- `configutil.py` — preferences/persistence helpers (the preferences
  file is plain utf-8 string literals, exec'd on load).
- `main.py` — `main()`, option parsing (`-d`, `-g/--geometry`,
  `--run-script`, `--version`, `-geometry` hack).
- `connector.py` — **pub/sub machinery** (Publisher, Issue, Subscribe,
  Connect/Disconnect) used everywhere for change notifications.
- `undo.py`, `undodict.py` — undo/redo framework (Undo, UndoList,
  CreateListUndo, ...); graphics objects return undo entries from
  mutation methods.
- `plugins.py` — plugin loading on `importlib` (real packages; user
  content under `$XDG_CONFIG_HOME/skencil`, default
  `~/.config/skencil`, `--configdir` override), plugin initialization.
- `load.py` — file type detection and dispatch to import filters;
  `load_drawing()`.
- `loadres.py` — resource loading (uses `Sketch.Modules.skread`).
- `warn.py` — warning/debug system (`warn`, USER/INTERNAL levels).
- `skexceptions.py`, `const.py` — exceptions and event/constants.

### `Sketch/Graphics/` — the document model and rendering (no Tk)
- `base.py` — `GraphicsObject`, `Primitive`: base classes with property
  stack, undo, publisher pattern.
- `document.py` (2477 lines) — `EditDocument`, layers/pages, commands;
  `selection.py` — selection handling; `layer.py`, `guide.py`,
  `compound.py`, `group.py`, `maskgroup.py`, `clone.py`, `blendgroup.py`.
- Shape classes: `rectangle.py`, `ellipse.py`, `bezier.py` (1444 lines,
  with `curveop.py` boolean ops), `text.py` (glyph-index text, see
  `devdocs/glyph-text.md`), `image.py` (`RasterImage`/`ImageData`, PIL
  as boundary codec), `eps.py`, `external.py` (linked images with
  automatic reloading — see `reloaddlg.py`).
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
- `skapp.py` — `SketchApplication` (Tk root, preferences, mainloop);
  checks that Tcl is threaded and sets `wantobjects(0)`.
- `mainwindow.py` (1389 lines) — main window, menus, commands.
- `canvas.py` (1955 lines) — the drawing canvas widget (uses pax-backed
  tkext widget for fast rendering), event handling, tools/modes
  (`modes.py`), `view.py`/`viewport.py` (zoom/pan; fork added middle-mouse
  scroll and wheel zoom), `ruler.py`, `miniscroll.py`.
- `tkext.py` (950 lines) — Tk widget extensions, the bridge to `pax`
  (`pax.register_object`, `InitFromTkapp`, `UpdateWhenIdle`, ...);
  `GetOpen/SaveFilename` normalize Tk file-dialog results via
  `util.as_unicode` (the single filename boundary).
- `tkutils.py` — Tk font/color helpers (`ColorScheme`, `set_ui_font`,
  color conversion).
- Dialogs: `filldlg.py`, `linedlg.py`/`styledlg.py`, `colordlg.py`,
  `fontdlg.py`, `curvedlg.py`, `guidedlg.py`, `griddlg.py`,
  `layoutdlg.py`, `layerdlg.py`, `aligndlg.py`, `blenddlg.py`,
  `gradientedit.py`, `optiondlg.py`, `export.py`, `printdlg.py`,
  `plugindlg.py`, `reloaddlg.py`.
- `skpixmaps.py` — loads pixmaps from `Resources/Pixmaps`.
- `prompt.py` — the command-line prompt window (has `exec`).
- `command.py` — command infrastructure (`RegisterCommands`).

### `Sketch/Lib/` — pure-python helper libs
- `type1.py`, `encoding.py` — Type 1 font parsing (with
  `Sketch.Modules._type1` for decryption), font metrics.
- `dscparser.py`, `psmisc.py` — PostScript/DSC parsing (EPS import).
- `glyphnames.py` — unicode ↔ Adobe glyph name mapping (AGL names,
  uniXXXX, legacy afii aliases, control-code reserved names); the
  model-side support of the glyph-index text representation.
- `units.py`, `util.py` (`as_unicode`, `format`, the `run_gs` family,
  `popen_read/write`), `skcompleter.py`.

### `Sketch/Modules/`
Contains only `__init__.py` in the source tree; the built C extension
`.so` files appear here in the build tree.

### C extensions (`src/extensions/`, built into `Sketch.Modules.*`)
- `Modules/_sketchmodule.c` — the core: `Point`, `Rect`, `Trafo`
  (2D affine), `CreatePath`/curve objects (`curveobject.c`,
  `curvefunc.c`, `curvedraw.c`, `curvelow.c`), color (`skcolor.c`),
  font metrics (`skfm.c`, gid-indexed), image scaling/gradient fills
  (`skimage.c`, `skdither.c`), plus misc helpers (`skaux.c`).
- `Modules/skreadmodule.c` — `skread.parse_sk_line2` used by the .sk
  loader to parse save-file lines safely (eval-like parsing); takes a
  sequence of function names whose string arguments are returned as
  raw bytes (the `txt`/`pt` text-content contract, see
  `devdocs/glyph-text.md`).
- `Modules/pstokenize.c` (+ `pschartab.c`) — PostScript tokenizer
  (EPS/PDF import).
- `Modules/_type1module.c` — Type 1 font decryption.
- `Filter/streamfilter.c` + filters — stream abstraction with
  Base64Decode, SubFileDecode, HexFilter, ASCII85, zlib; imported as
  `from Sketch.Modules.streamfilter import Base64Decode, SubFileDecode`.
- `Pax/paxmodule.c` — the X11/Tk rendering layer core, running on the
  stock `_tkinter`: Tcl-context callbacks are registered via
  `_tkinter`'s `createcommand` (`pax.call_py_method`) and acquire the
  GIL with `PyGILState_Ensure` — GIL-safe by design; **threaded Tcl is
  required** and checked at startup. Preserve this design when
  touching the Tk/pax boundary.
  `pax` provides off-screen X11 pixmaps, GC
  objects, windows (`tkwinobject.c`), regions, clipping, fonts, images,
  and registers Tcl commands; used by `Sketch/UI/tkext.py`,
  `canvas.py`, `ruler.py`, `miniscroll.py`, `gradientedit.py`.
- `Pax/gcmethods.c` — GC method wrappers, pulled in via
  `#include "gcmethods.c"` from `gcobject.c` (deliberately not in the
  Extension sources list; deleting it breaks the build).
- `Pax/Generate/` — the code generator (`mkgc.py`, using
  `mktools.py`/`typedefs.py`) that produces `gcmethods.c`.

### Plugins (`src/Sketch/Plugins/`)
- `Filters/` — loaders/savers registered through
  `Sketch/Base/plugins.py`:
  - Import: `skloader.py` (native `.sk` format, uses `skread`),
    `svgloader.py`, `wmfloader.py`, `xfigloader.py`, plus
    gzip/bzip-wrapping loaders.
  - Export: `sksaver.py`, `epssaver.py`, `pssaver.py`, `svgsaver.py`,
    `wmfsaver.py`, and the fork's working PDF export:
    `pdfsaver.py`, `pdfsaverbox.py`, `pdfsaverpage.py`.
- `Objects/` — plugin compound objects: `arrow.py`, `regpoly.py`,
  `lcdtext.py`, `multilinetext.py` (with `Lib/multilinetext/`),
  `autoshapeplugin.py` (with `Lib/autoshapes/`), `latextext.py`
  (renders LaTeX text; made robust in this fork).

### Scripts (`src/Sketch/Scripts/`)
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
  updated when adding or removing packages (e.g.
  `Sketch.Plugins.Objects.Lib.autoshapes` also declares icon data
  files).
