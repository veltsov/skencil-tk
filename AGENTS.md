# AGENTS.md — Knowledge Base for Working on skencil-tk

Skencil is an interactive vector drawing program for X11, written almost
entirely in Python 2 with performance-critical parts in C extension modules.
This repository is a continuation of the Skencil project
(http://www.skencil.org), based on skencil-1.0alpha by Igor E. Novikov,
which in turn is based on Bernhard Herzog's "Sketch" (1996–2005).
The current maintainer's fork (Vladimir Eltsov, 2018+) converted the UI
from GTK to **Tk** and added many features (see `README.md`).

**Read this file first. Detailed notes are in `devdocs/`:**

| File | Contents |
|------|----------|
| `devdocs/build-and-environment.md` | How to build, run, package; devtools scripts; required packages; Python 2.7 build environment (containerless bwrap root, podman container, AppImage) |
| `devdocs/architecture.md` | Source layout, package structure, C extension modules, plugin system, file formats, key classes and data flow |
| `devdocs/python3-porting.md` | All findings relevant to the goal of porting the application to Python 3: inventory of Python-2-only constructs (per-file), C extension issues, strategy recommendations |
| `devdocs/paxtkinter-analysis.md` | Deep analysis of the `paxtkinter` module: why it exists (GIL/TclLock), full dependency surface, and the plan to drop it in favor of stock `_tkinter` (branch `modernize`) |
| `devdocs/modernize-paxtkinter.md` | Pre-flight experiment record (2026-10-20): running the app on stock `_tkinter` segfaults at the first pax→Python call (gdb backtrace); corrected conclusions and the simplified fix |
| `devdocs/modernize-roadmap.md` | Roadmap of pre-py3 modernization batches (dead code, 2to3-based mechanical cleanups, deeper items) with status |
| `devdocs/testing.md` | The automatic test suite in `test/`: layers (model/formats/Xvfb app/screenshot), baseline recording from `master`, fixture management, known findings |
| `devdocs/unicode-runtime-audit.md` | The unicode-at-runtime bug class (gettext shim returns unicode on py2): fixed instances, the `.sk` utf-8/\x-escape format decision, and the planned proactive audit tooling (not yet executed) |
| `devdocs/string-handling.md` | The string-kind taxonomy (origins → types → conversions) and the conventions that replace scattered type checks; feeds the py3 port |
| `devdocs/glyph-text.md` | The glyph-index text representation of `SimpleText` (global glyph registry, gid arrays, conversions at all sinks); supersedes the byte-per-character K3 form |
| `devdocs/text-input.md` | Findings and design for the planned text input rework: unicode keyboard input (Cyrillic etc.), keymap dispatch, afii/uniXXXX glyph-name candidates — **planned, not implemented** |
| `devdocs/import-restructure.md` | The import machinery findings (implicit relative imports, fake plugin packages, `module.so` suffix trick) and the executed restructuring into a canonical real-package layout with absolute imports |

## Quick facts

- **Language:** Python 2 (2.7) + C extension modules. ~200 `.py` files under
  `src/`, ~57k lines of Python, plus ~10k lines of C in `src/extensions/`.
- **UI toolkit:** Tk (via `Tkinter`), plus the custom C extension `pax`
  (X11/pixmap rendering for Tk widgets). Since the `modernize` branch,
  the stock `_tkinter` is used directly — the former `paxtkinter`
  `_tkinter`-replacement module was dropped (see
  `devdocs/modernize-paxtkinter.md`); the runtime now *requires
  threaded Tcl* (checked at startup). No GTK anymore (despite the
  legacy name `Sketch/Base/gtkutils.py`, which now contains only Tk
  font/color helpers).
- **Build:** `python2 setup.py build` (distutils). Result goes to
  `build/lib.linux-x86_64-2.7/` and the launcher to
  `build/scripts-2.7/skencil`. The app is run *directly from the build
  directory*, no install needed (see `README.md`). Because of this,
  **every source change (including plain `.py` files) must be followed
  by a rebuild** — `src/` is not on the runtime `sys.path`; the app only
  reads from `build/lib.linux-x86_64-2.7/`.
- **Version:** `1.1` (`src/Sketch/VERSION`, also `setup.py` and
  `PKG-INFO`; shown by `--version` and in the PostScript Creator
  comment).
- **License:** LGPL (most), GPL for some parts; see `README`, `COPYING`.
- **Current environment used for development:** Ubuntu 20.04 (focal) with
  `python2, python2-dev, python-tk, python-pil, python-pil.imagetk,
  tcl-dev, tk-dev` (see `README.md` and `devtools/devcont/install-dev-packages`).
- **No test suite.** `tests/` contains only scratch/demo scripts run by hand
  under python2 (and `tests/` is gitignored, as are `old/`, `AppDir/` build
  artifacts, `build/`, `*.sav*` backups).

## Repository layout

- `src/` — the application source
  - `Sketch/` — main Python package (`Base`, `Graphics`, `UI`, `Lib`,
    `Modules`, `Scripting`)
  - `extensions/` — C sources of the extension modules
    (`Modules/` geometry+font+image, `Pax/` Tk/X11 integration, `Filter/`
    stream filters)
  - `Plugins/` — import/export filters (`Filters/`) and plugin objects
    (`Objects/`)
  - `Script/` — user scripts (run via `--run-script` or Scripts menu)
  - `Resources/` — pixmaps, font metrics, misc resources, translations
  - `skencil`, `skencil.py`, `sk2ps`, `skconvert.py`, `skshow.py` —
    launcher / CLI scripts
- `po/` — gettext translations (built to `src/Resources/Messages` by setup.py)
- `devtools/` — build/dev-environment scripts (see build doc)
- `AppDir/` — assembled AppImage directory (gitignored parts)
- `tests/` — hand-run scratch scripts (gitignored)
- `old/` — archived old plugins (gitignored)
- `setup.py`, `MANIFEST.in`, `setup.cfg`, `PKG-INFO` — distutils build
- Files like `*.sav`, `*.sav2`, `*.sav3` are manual backups of files before
  modifications; `*.patch` files are leftover patches (likely already
  applied). Do **not** delete or "clean up" them without asking.

## Working rules

- When analysing code (greps, searches, reading), **skip the `AppDir/`**
  directory — it is a bundled AppImage payload containing a full copy of
  the python2 stdlib and third-party modules that pollutes every search.
  Concentrate on `src/` (plus `test/` and `devdocs/` as appropriate).
- Do not touch anything outside the task scope; when only asked to
  document, do not modify source files.
- The code is Python 2: keep new code Python 2 compatible unless the task
  explicitly says otherwise. Do not "modernize" code opportunistically —
  the codebase is intentionally kept buildable with python2.7 until the
  Python 3 port is done (see `devdocs/python3-porting.md` for the port plan).
- Never reformat or whitespace-fix old files wholesale; edits should be
  minimal and localized.
- After **any** source change — C extensions, `setup.py`, *and plain
  Python files* — rebuild with `python2 setup.py build` and test from
  the build tree. The app imports from `build/lib.linux-x86_64-2.7/`,
  not from `src/`, so editing a `.py` file in `src/` has no effect on
  the running application until the build copies it over.
- Localization: user-visible strings should go through `_()` from `Sketch`
  (standard `gettext` module; per-domain caching shim in
  `Sketch/__init__.py` — the former `intl` C extension was dropped).

## Entry points (runtime flow)

1. `src/skencil` (launcher) puts `../lib.linux-x86_64-2.7` on `sys.path`
   and calls `Sketch.main.main()`.
2. `Sketch/Base/main.py:main()` parses options, calls `Sketch.init_ui()`,
   creates `SketchApplication`
   (`Sketch/UI/skapp.py`; `init_tk` checks that Tcl is threaded and sets
   `wantobjects(0)`) and runs the Tk mainloop.
3. `Sketch/__init__.py` is the package bootstrap: extends `__path__` with
   `Modules/` and `Base/`, sets up gettext, imports and re-exports
   geometry primitives from `_sketch` C module, initializes PIL, loads
   config (`config.init_directories`), and imports/re-exports the whole
   graphics model from `Sketch/Graphics/*`.
