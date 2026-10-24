# Python 3 Port — Current State and Plan

Date: 2026-10-24.  This document describes the current port-relevant
state of the codebase and the porting plan.  Historical findings live
in the git history and in the sibling documents
(`import-restructure.md`, `string-handling.md`,
`unicode-runtime-audit.md`, `modernize-roadmap.md`,
`modernize-paxtkinter.md`, `paxtkinter-analysis.md`); everything marked
resolved there is done.

## Environment

- Development system: Ubuntu 20.04 (focal); python2.7.18 at
  `/usr/bin/python2` (the interpreter the app still runs on),
  python3.10.12 available as `python3`, Tcl/Tk 8.6, Xvfb for the UI
  tests.
- The py3 package set for the port: `python3-dev python3-tk
  python3-pil python3-pil.imagetk tcl-dev tk-dev`.
- The app is run directly from the build tree; `setup.py`, the
  launchers and `devtools/` still carry python2-specific paths (stage
  E below).

## What is already py3-ready (kept brief; see the sibling docs)

- **Package layout and imports**: one real package tree with canonical
  absolute imports; no implicit relative imports, no `sys.path`/
  `__path__` manipulation, no fake packages, no `imp`; the C extensions
  are built and imported under their real names
  (`Sketch.Modules.{pax,_sketch,streamfilter,pstokenize,skread,_type1}`)
  — the legacy `module.so` suffix dependence is gone.  A py3 `compile()`
  sweep reports only 12 files with syntax errors (below).
- **String handling**: the K1–K6 taxonomy of `string-handling.md` is
  implemented and enforced (`undo.check_info`, `ScriptRegistry.Add`);
  the model is already the py3 shape — user names and file names are
  unicode, text content is glyph-index arrays, `.sk` files are
  byte-compatible utf-8 `\x`-escaped literals, the preferences file is
  plain utf-8.  No `basestring`, no `unicode()` calls remain.
- **Tk layer**: runs on stock `_tkinter` with threaded Tcl (checked at
  startup); pax's callbacks are marshaled through `_tkinter`'s
  `createcommand` (`pax.call_py_method`) — GIL-safe by design, and this
  design must be preserved by the port.  `wantobjects(0)` is set so
  `tk.call` results come back as strings; py3 tkinter still supports it.
- **Plugins/scripts**: `importlib`-based loader, real packages, user
  content under the XDG configuration directory
  (`$XDG_CONFIG_HOME/skencil`, default `~/.config/skencil`,
  `--configdir` override).
- **Validation**: `test/run_tests.sh` — 95 tests (headless model,
  format round-trips against master baselines including a ghostscript
  raster comparison, Xvfb app smoke, LaTeX recompile).  The suite is
  the gate for every porting step; `--record` regenerates baselines
  from master.

## Remaining Python-side work (verified 2026-10-24)

### Syntax errors under py3 (12 files, all small)

| Kind | Files |
|---|---|
| inconsistent tab/space indentation (py3 is stricter) | `Sketch/__init__.py`, `Lib/psmisc.py`, `UI/palette.py`, `UI/plugindlg.py`, `Scripts/TeX.py`, `Scripts/curvetext.py`, `Plugins/Objects/latextext.py`, `skshow.py` |
| py2-only integer literals (`10L`, leading-zero octal) | `Plugins/Filters/Lib/drawfile.py:105`, `Lib/util.py:176` |
| old syntax statements | `UI/viewport.py:65`, `Plugins/Filters/svgsaver.py:158` |

All mechanical; a restricted `2to3` pass (the safe fixers listed in
`modernize-roadmap.md` section B) plus hand-edits suffice.

### py2-only constructs still in use

| Construct | Sites | Port action |
|---|---|---|
| `import Tkinter`/`from Tkinter import`/`Tkconstants` | 39 files | mechanical rename to `tkinter`/`tkinter.constants`; the uppercase constants (`END`, `BOTH`, ...) exist in py3 tkinter — verify per use anyway |
| `tkFileDialog`/`tkMessageBox`/`tkSimpleDialog` | `Plugins/Objects/Lib/multilinetext/TextEditor.py` | rename to `tkinter.filedialog` etc. |
| `execfile` | `Base/configutil.py:221` (preferences), `UI/mainwindow.py:610` (--run-script) | `exec(compile(open(..., 'rb').read(), filename, 'exec'), ...)`; for preferences the coding cookie is honored by compile and the `_LoadedPreferences` unicode conversion disappears in py3 (documented in the file) |
| `string.maketrans` | `Graphics/font.py:38`, `Lib/dscparser.py:45`, `Plugins/Filters/svgloader.py:259` | *not* drop-in (`str.maketrans` returns a dict; py2 `str.translate` needs the 256-char table) — build the tables with a small helper or switch to `str.replace`/regex |
| `long(...)` | `Plugins/Filters/Lib/drawfile.py` (3 sites, 64-bit fraction math) | `int()` — py2 ints are 64-bit on the target platforms |
| `__nonzero__` | `Graphics/selection.py:398` (`__nonzero__ = __len__`) | add `__bool__ = __len__` alongside (py2+py3 compatible) |
| `reduce` builtin | `Graphics/{compound,document,selection,text}.py` (7 sites) | `functools.reduce` — py2-compatible, do now |
| `"__cmp__"` dict key | `Scripting/wrapper.py:59` | attr-name table for the scripting wrapper; review and drop |
| `cStringIO` / `StringIO` | `Lib/type1.py:24`, `Plugins/Objects/Lib/multilinetext/chunker.py:18` | `io.StringIO`/`io.BytesIO` behind a try-import, or straight rewrite |
| `import UserDict` | `Scripts/pathutils/base.py` | py3 still ships `UserDict`; small usage review |
| `xml.sax.saxlib` | `Plugins/Filters/svgloader.py` | broken on py2 already; rewrite to `xml.sax.handler` (roadmap item C1) — do it as port prep, it un-breaks SVG import under py2 too |
| `from lib.blocktext import` | `Plugins/Objects/Lib/autoshapes/simpleblocktext.py` | pre-existing broken plugin (the module does not exist anywhere); delete with maintainer approval |


### Semantics to audit (no reliable grep; suite + targeted review)

- **Integer division `/`**: geometry/trafo/pattern/dither math.  The
  controlled way: add `from __future__ import division` per file and
  fix the fallout under py2 (suite-validated) — this converts the
  riskiest un-greppable change into verified fixes before the switch.
- `dict.keys()` indexing and mutation during iteration; `sort(cmp=...)`
  callbacks (none found in Graphics; audit the Plugins).
- Old-style classes: everything currently derives from nothing (py2
  classic classes); under py3 they become new-style automatically.
  `type(obj).__name__` is `'instance'` on py2 (the suite's
  `testsupport.class_name` already handles both).  Watch for
  `__getattr__` tricks in `Graphics/base.py`/`clone.py`.

## C extensions (the bulk of the port)

Sources: `src/extensions/{Modules,Pax,Filter}` (~21k built lines).
`Pax/paxtkinter.c` and `Pax/intl.c` are dead leftovers (not built) and
should be deleted before porting; `Pax/gcmethods.c` is not in the build
either.

| Module (built name) | ~Lines | Port notes |
|---|---|---|
| `Sketch.Modules._sketch` (`_sketchmodule.c` + `curve*`/`sk*`/`skfm`) | 9400 | geometry types; mostly arg parsing + math.  `PyString_*` (5), `PyInt_*` (~25), `PyCObject` → `PyCapsule` (curveobject undo segments) |
| `Sketch.Modules.pax` (`Pax/*`) | 4700 | Tk C API via `interpaddr`/`Tk_Window`, X11 pixmaps/GC/regions, `call_py_method` marshaling.  `PyString_*` (~15 built), `PyInt_*` (~40).  The GIL design from `modernize-paxtkinter.md` must be preserved |
| `Sketch.Modules.streamfilter` (`Filter/*`) | 2900 | `PyString_*` (~40), `PyInt_*` (6); the `Filter_Functions` C-struct bridge to pstokenize via `PyCObject` → `PyCapsule` |
| `Sketch.Modules.pstokenize` | 850 | `PyString_*` (36); imports `Sketch.Modules.streamfilter` at init (already canonical) |
| `Sketch.Modules.skread` (`skreadmodule.c`) | 660 | `parse_sk_line2` (restricted eval of `.sk` lines); decide whether py3 returns `str` directly (then the `decode_sk_string` call sites vanish) or keeps bytes + explicit decode |
| `Sketch.Modules._type1` | 160 | tiny |

Common C-API work for all: `Py_InitModule` → `PyModuleDef` +
`PyInit_<shortname>` (`init_sketch` → `PyInit__sketch`, `initskread` →
`PyInit_skread`, `init_type1` → `PyInit__type1`; pax/streamfilter/
pstokenize keep their names), `PyString_*` → `PyUnicode_*` for text and
`PyBytes_*` for binary (split per the string-kind taxonomy), `PyInt_*`
→ `long`/`PyLong`, `PyCObject` → `PyCapsule`, `tp_compare`/slot review.
Single-phase init is sufficient (no per-subinterpreter state needed).

### The one real design problem: skimage vs. the PIL C API

`skimage.c` (1719 lines) implements the X11 display scaling and the
gradient/pattern fill math in C.  It reaches into PIL's *private* C
internals: `#include "Imaging.h"`, a local re-declaration of the
`ImagingObject` struct from `_imagingmodule.c`, and Python passing
`PIL.Image.Image.im` (the internal core handle) into
`_sketch.copy_image_to_ximage`, `fill_{axial,radial,conical}_gradient`,
`fill_transformed_tile`, `write_ps_hex` and `fill_hsv_*` (call sites in
`graphics.py`, `psdevice.py`, `colordlg.py`, `gradientedit.py`).
Modern Pillow neither installs usable third-party headers nor
guarantees that struct layout — this cannot simply be recompiled.

Options (decision required before porting skimage):

1. **Buffer-protocol shim (recommended)**: pass raw pixel bytes
   (`PIL.Image.tobytes()` / `frombytes`) plus mode and size into the C
   functions instead of `ImagingObject*`.  Keeps all the C math;
   changes ~15 call sites in skimage.c plus the Python callers; adds
   one copy per operation (acceptable for display-sized images).
2. Reimplement the fill/scale math in Python (numpy or plain) — no C
   build issue, but the canvas redraw path gets slower.
3. Vendor a minimal Imaging subset inside skimage (own struct, convert
   from PIL at the boundary) — most work, keeps zero-copy.

`setup.py`'s `/usr/include/python2.7/Imaging` include-dir handling goes
away with whichever option is chosen.

## Porting plan

Stages are ordered so that everything that *can* be validated under
python2 happens first (stage A), the C port happens on a branch (stage
B), and the final switch is small (stages C–D).  The test suite is the
gate throughout; baselines are compared against master's
(`test/run_tests.sh --record` refreshes them when master moves).

- **Stage A — py2-compatible modernization (do now, on the main
  branch):** the 12 syntax-error files; `reduce` → `functools.reduce`;
  `__bool__` aliases; drop the `wrapper.py` `__cmp__` entry;
  `execfile` → `exec(compile(...))` (works on py2); the svgloader
  rewrite to `xml.sax`; delete the dead C sources (`paxtkinter.c`,
  `intl.c`, `gcmethods.c`) and the stale `*.patch`/`*.sav` clutter with
  maintainer approval; the `from __future__ import division` rollout
  with suite-validated fixes; version-parameterize `setup.py` (build
  dir names via `sys.version_info`), `src/skencil` (lib dir) and
  `devtools/`.  Gate: build + 95 tests + Xvfb smoke after each batch.
- **Stage B — C extensions on a port branch (python3):** in the order
  `_sketch` (geometry) → `streamfilter`/`_type1`/`skread`/
  `pstokenize` → `pax` → `skimage` last (design decision above first).
  Per module: `PyModuleDef` + `PyInit_`, the bytes/unicode split per
  the taxonomy, `PyCapsule` bridges, warning-free compile.  Gate per
  module: import + the headless model tests under py3
  (`test/testsupport.py` needs `Sketch.init_lib`, which requires
  `_sketch` and `streamfilter` first — order the work accordingly);
  formats/Xvfb once the Tk layer works.
- **Stage C — Python switch (same branch):** `Tkinter` → `tkinter`
  renames (39 files), the `TextEditor.py` dialog modules, removal of
  the stage-A shims, dict-view cleanups the suite surfaces.  Gate:
  full suite under py3 (model + formats + Xvfb smoke + LaTeX).
- **Stage D — environment and packaging:** devtools
  (`install-dev-packages`, `build-skencil`, `build-devroot`,
  `collect-app-dir` → python3 payload), `README.md`, `.vscode`
  settings, AppImage rebuild.  Gate: the app runs from the build tree
  and from the AppDir.

## Known risks

- **skimage/PIL** — the only genuinely open design question (above).
- **pax under py3 tkinter** — the GIL/`tcl_tstate` analysis
  (`modernize-paxtkinter.md`) was done on py2; the py3 `_tkinter` C
  source differs (multi-phase init, capsule-based internals), so the
  pax port needs its own pre-flight experiment under Xvfb, like the
  paxtkinter drop had.
- **Threaded Tcl** remains a hard runtime requirement (checked at
  startup).
- **Old-style → new-style classes** — behavior differences are
  possible where code relies on classic-class lookup order; the suite
  should catch them.
- **Baselines** were recorded from py2 master; EPS bytes may differ
  under py3 (e.g. float formatting) — the raster comparison with a
  pixel tolerance is the fallback, as in the existing format tests.

