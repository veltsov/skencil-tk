# AGENTS.md — Knowledge Base for Working on skencil-tk

Skencil is an interactive vector drawing program for X11, written in
Python with performance-critical parts in C extension modules.
This repository is a continuation of the Skencil project
(http://www.skencil.org), based on skencil-1.0alpha by Igor E. Novikov,
which in turn is based on Bernhard Herzog's "Sketch" (1996–2005).
The current maintainer's fork (Vladimir Eltsov, 2018+) added many features (see `README.md`) and made port to Python 3.

**Read this file first. Detailed notes are in `devdocs/`:**

| File                               | Contents                                                                                                                                                                             |
| ---------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `devdocs/build-and-environment.md` | How to build, run, package; devtools scripts; required packages; AppImage (bundled ghostscript/pstoedit/fonts)                                                                       |
| `devdocs/architecture.md`          | Source layout, package structure, C extension modules, plugin system, file formats, key classes and data flow                                                                        |
| `devdocs/testing.md`               | The automatic test suite in `test/`: layers (model/formats/Xvfb app/screenshot), baseline recording from `master`, fixture management                                                |
| `devdocs/string-handling.md`       | The string-kind taxonomy (origins → types → conversions) and the conventions that replace scattered type checks                                                                      |
| `devdocs/glyph-text.md`            | The glyph-index text representation of `SimpleText` (global glyph registry, gid arrays, conversions at all sinks)                                                                    |
| `devdocs/text-input.md`            | The unicode keyboard input path; open follow-up items (multilinetext latin-1 input, full-charset insertion)                                                                          |
| `devdocs/image-transparency.md`    | Image alpha transparency: current state and the plan (display blending, PS flatten, PDF via ghostscript SMask recipe) — **planned, not implemented**                                 |
| `devdocs/svg-export.md`            | SVG export: the Inkscape and Plain flavours, object/paint mapping onto the PostScript semantics, text modes, TexText, EPS, limitations                                              |
| `devdocs/svg-import.md`            | SVG import (`Plugins/Filters/Lib/svgimport`): geometry, paint and opacity, fill rule, gradients, clips/masks, markers, text as curves (SVG fonts, Inkscape), round trip of the export, API |
| `devdocs/ps-import.md`             | EPS/PS/PDF import (`Plugins/Filters/Lib/psimport`): the intermediate gs → pdftocairo → svgimport pipeline, page selection as import options, the approaches compared, the planned native PDF reader |
| `devdocs/display-backends.md`      | Modern display backends (pixman, XRender, cairo, GPU/Tk-native) evaluated against Skencil's device architecture; antialiasing and font-model modernization goals — **analysis only** |

## Quick facts

- **Language:** Python 3 (3.10 on the dev systems) + C extension
  modules. ~200 `.py` files under `src/`, ~57k lines of Python, plus
  ~10k lines of C in `src/extensions/`.
- **UI toolkit:** Tk via the stock `_tkinter`, plus the custom C
  extension `pax` (X11/pixmap rendering for Tk widgets). The runtime
  *requires threaded Tcl* (checked at startup); `wantobjects(0)` is set
  so `tk.call` results come back as strings. pax's Tcl-context
  callbacks are marshaled through `_tkinter`'s `createcommand`
  (`pax.call_py_method`, GIL-safe) — preserve this design.
- **Localization:** user-visible strings go through `_()` from `Sketch`
  (standard `gettext` module; per-domain caching shim in
  `Sketch/__init__.py`).
- **Build:** `python3 setup.py build` (distutils). Result goes to
  `build/lib.linux-x86_64-3.10/` and the launcher to
  `build/scripts-3.10/skencil`. The app is run *directly from the build
  directory*, no install needed (see `README.md`). Because of this,
  **every source change (including plain `.py` files) must be followed
  by a rebuild** — `src/` is not on the runtime `sys.path`; the app
  only reads from `build/lib.linux-x86_64-3.10/`.
- **Version:** `1.2` (`src/Sketch/VERSION`, also `setup.py` and
  `PKG-INFO`; shown by `--version` and in the PostScript Creator
  comment).
- **License:** LGPL (most), GPL for some parts; see `README`, `COPYING`.

## Repository layout

- `src/` — the application source
  - `Sketch/` — main Python package (`Base`, `Graphics`, `UI`, `Lib`,
    `Modules`, `Scripting`, `Scripts`, `Plugins/{Filters,Objects}`)
  - `extensions/` — C sources of the extension modules
    (`Modules/` geometry+font+image, `Pax/` Tk/X11 integration, `Filter/`
    stream filters)
  - `Resources/` — pixmaps, font metrics, misc resources, translations
  - `skencil`, `sk2ps`, `skconvert` — launcher / CLI scripts
    installed into `build/scripts-3.10` (and dispatched by AppRun);
    `sk2ppm.py`, `skshow.py` — CLI scripts that are not installed
- `po/` — gettext translations (built to `src/Resources/Messages` by setup.py)
- `devtools/` — build/dev-environment scripts (see build doc)
- `AppDir/` — assembled AppImage directory (gitignored parts)
- `test/` — the automatic regression test suite (`test/run_tests.sh`)
- `tests/` — hand-run scratch scripts (gitignored)
- `old/` — archived old plugins (gitignored)
- `setup.py`, `MANIFEST.in`, `setup.cfg`, `PKG-INFO` — distutils build
- Files like `*.sav`, `*.sav2`, `*.sav3` are manual backups of files before
  modifications; `*.patch` files are leftover patches (likely already
  applied). Do **not** delete or "clean up" them without asking.

## Working rules

- When analysing code (greps, searches, reading), **skip the `AppDir/`**
  directory — it is a bundled AppImage payload containing a full copy of
  the python3 stdlib and third-party modules that pollutes every search.
  Concentrate on `src/` (plus `test/` and `devdocs/` as appropriate).
- Do not touch anything outside the task scope; when only asked to
  document, do not modify source files.
- New code is Python 3 (3.10 baseline). Do not reformat or
  whitespace-fix old files wholesale; edits should be minimal and
  localized.
- After **any** source change — C extensions, `setup.py`, *and plain
  Python files* — rebuild with `python3 setup.py build` and test from
  the build tree. The app imports from
  `build/lib.linux-x86_64-3.10/`, not from `src/`, so editing a `.py`
  file in `src/` has no effect on the running application until the
  build copies it over. Incremental builds are cheap (timestamp-based
  re-copy + `compileall`).
- **The test suite is the gate for every change:** `test/run_tests.sh`
  (headless model + formats + Xvfb app/screenshot layers; see
  `devdocs/testing.md`). Run it after every non-trivial change.
- One build tree serves one interpreter version (per-version
  subdirectories); do not build branches that target a different
  interpreter version in this checkout — distutils `build_py` copies
  *all* `.py` sources before `build_ext` runs, so a failed cross-version
  build leaves a corrupted build tree. Build such branches from their
  own git worktree.

## Entry points (runtime flow)

1. `src/skencil` (launcher) puts `../lib.linux-x86_64-3.10` on
   `sys.path` and calls `Sketch.main.main()`.
2. `Sketch/Base/main.py:main()` parses options, calls `Sketch.init_ui()`,
   creates `SketchApplication`
   (`Sketch/UI/skapp.py`; `init_tk` checks that Tcl is threaded and sets
   `wantobjects(0)`) and runs the Tk mainloop.
3. `Sketch/__init__.py` is the package bootstrap: sets up gettext,
   imports and re-exports geometry primitives from the `_sketch` C
   module (`Sketch.Modules._sketch`), initializes PIL, loads config
   (`config.init_directories`), and imports/re-exports the whole
   graphics model from `Sketch/Graphics/*`. The C extension modules
   import under their real names (`Sketch.Modules.{pax,_sketch,
   streamfilter,pstokenize,skread,_type1}`); no `__path__`/`sys.path`
   manipulation exists anywhere.

## Test suite

- `test/run_tests.sh` — runs everything under pytest (python3),
  comparing against the golden artifacts in `test/baselines/`
  (`BASELINE-REV` records the master revision they were recorded from;
  the runner warns when master has moved past it).
- `test/run_tests.sh --record` — (re)generates the baselines: builds a
  git worktree of `master` at the recorded revision and runs the whole
  suite against it with `SKENCIL_TEST_RECORD=1`.
- Layers: headless document-model tests (`test/model/`), format
  round-trips incl. ghostscript raster comparison (`test/formats/`),
  app smoke + screenshot tests under Xvfb (`test/ui/`). See
  `devdocs/testing.md`.
- `test/add-fixture <file.sk>` installs a new fixture and regenerates
  its baselines; `test/data/fixtures.txt` is the manifest.
