# Python 3 Port — Current State and Plan

Date: 2026-10-26.  This document describes the current port-relevant
state of the codebase and the porting plan.  Historical findings live
in the git history and in the sibling documents
(`import-restructure.md`, `string-handling.md`,
`unicode-runtime-audit.md`, `modernize-roadmap.md`,
`modernize-paxtkinter.md`, `paxtkinter-analysis.md`); everything marked
resolved there is done.

## Environment

- Development system: Ubuntu 20.04 (focal); python2.7.18 at
  `/usr/bin/python2` (the interpreter the app still runs on).
- **Python 3 environment (audited 2026-10-26, by import probes — dpkg
  metadata is unreliable in the bwrap dev root, files owned by
  `nobody`):** python3.10.12 at `/usr/bin/python3`.  Already present
  and importable under py3, i.e. **no installation needed**:
  `tkinter` (Tk 8.6), `PIL` 9.0.1 including `PIL.ImageTk` (used by the
  autoshape toolbar icons), `numpy` 1.21.5, `setuptools` 59.6.0, the
  python3.10 C headers (`/usr/include/python3.10`), the Tcl/Tk 8.6 dev
  headers (`/usr/include/tcl8.6`), gcc/make for the stage-B extension
  builds, the stdlib `lib2to3` (deprecated since 3.10 but present —
  fine for the restricted mechanical pass), and the system tools the
  test suite drives: `Xvfb`, `ghostscript`, LaTeX.
- **Missing for the port / test suite (re-checked 2026-10-26):**
  nothing essential.  `python3-pytest` is now installed (pytest 6.2.5,
  `python3 -m pytest` works); `python3-pip`/`python3-venv` are not
  installed and are **not wanted** — port policy is to use only the
  system python3 and system dist-packages (Pillow, numpy are already
  there).
- The py2-era set (`python2 python2-dev python-tk python-pil
  python-pil.imagetk tcl-dev tk-dev`) is still what the running app
  builds against.
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
- **Validation**: `test/run_tests.sh` — 111 tests (headless model
  including the image-representation suite `test/model/test_image.py`,
  format round-trips against master baselines including a ghostscript
  raster comparison, Xvfb app smoke, LaTeX recompile).  The suite is
  the gate for every porting step; `--record` regenerates baselines
  from master.

## Remaining Python-side work (re-verified 2026-10-26)

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
| `import Tkinter`/`from Tkinter import`/`Tkconstants` | 43 files (73 import lines; recount 2026-10-26; includes the plugin Lib helpers `autoshapelib.py`, `multilinetext/{iterator,styletext,TextEditor}.py` and `autoshapeplugin.py`) | mechanical rename to `tkinter`/`tkinter.constants`; the uppercase constants (`END`, `BOTH`, ...) exist in py3 tkinter — verify per use anyway |
| `tkFileDialog`/`tkMessageBox`/`tkSimpleDialog` | `Plugins/Objects/Lib/multilinetext/TextEditor.py` | rename to `tkinter.filedialog` etc. |
| ~~`execfile`~~ | ~~`Base/configutil.py`, `UI/mainwindow.py`~~ | **done 2026-10-26**: `exec(compile(open(..., 'rb').read(), filename, 'exec'), ...)`; for preferences the coding cookie is honored by compile and the `_LoadedPreferences` unicode conversion disappears in py3 (documented in the file) |
| `string.maketrans` | `Graphics/font.py:38`, `Lib/dscparser.py:45`, `Plugins/Filters/svgloader.py:259` | *not* drop-in (`str.maketrans` returns a dict; py2 `str.translate` needs the 256-char table) — build the tables with a small helper or switch to `str.replace`/regex |
| ~~`long(...)`~~ | ~~`Plugins/Filters/Lib/drawfile.py`~~ | **done 2026-10-26**: `int()` (py2 ints are 64-bit on the target platforms) |
| `__nonzero__` | `Graphics/selection.py:398` (`__nonzero__ = __len__`) | add `__bool__ = __len__` alongside (py2+py3 compatible) |
| `reduce` builtin | `Graphics/{compound,document,selection,text}.py` (7 sites) | `functools.reduce` — py2-compatible, do now |
| `"__cmp__"` dict key | `Scripting/wrapper.py:59` | attr-name table for the scripting wrapper; review and drop |
| `cStringIO` / `StringIO` | `Lib/type1.py:24`, `Plugins/Objects/Lib/multilinetext/chunker.py:18` (direct); try-import pairs in `Base/warn.py:83`, `Plugins/Filters/Lib/drawfile.py:43–46`, `Plugins/Filters/drawinput.py:55–58`; py2-only `from StringIO import StringIO` in the tests `test/model/test_unicode.py:327`, `test/model/test_image.py:258` | `io.StringIO`/`io.BytesIO` behind a try-import, or straight rewrite; the two test sites switch to `io.StringIO` when the suite runs under py3 |
| `import UserDict` | `Scripts/pathutils/base.py` | py3 still ships `UserDict`; small usage review |
| ~~`xml.sax.saxlib`~~ | ~~`Plugins/Filters/svgloader.py`~~ | **done 2026-10-26**: rewritten to `xml.sax.handler.ContentHandler` + `make_parser().parse()` (and the plugin's broken `skread` import fixed; verified with a smoke SVG load under py2) |
| `from lib.blocktext import` | ~~`Plugins/Objects/Lib/autoshapes/simpleblocktext.py`~~ | pre-existing broken plugin (the module does not exist anywhere) — **deleted 2026-10-26** as dead code |


### Semantics to audit (no reliable grep; suite + targeted review)

- **Integer division `/`**: geometry/trafo/pattern/dither math.  The
  controlled way: add `from __future__ import division` per file and
  fix the fallout under py2 (suite-validated) — this converts the
  riskiest un-greppable change into verified fixes before the switch.
  **Done 2026-10-26** (see `divaudit-findings.md`): 46 runtime-verified
  sites fixed, 257 unverified sites flagged `# divaudit: unverified`,
  rollout in 86 files (draw-input pair excluded until reviewed);
  `skpoint.c` gained `nb_true_divide` (keep it in stage B).
- `dict.keys()` indexing and mutation during iteration; `sort(cmp=...)`
  callbacks (none found in Graphics; audit the Plugins).
- Old-style classes: everything currently derives from nothing (py2
  classic classes); under py3 they become new-style automatically.
  `type(obj).__name__` is `'instance'` on py2 (the suite's
  `testsupport.class_name` already handles both).  Watch for
  `__getattr__` tricks in `Graphics/base.py`/`clone.py`.

## C extensions (the bulk of the port)

Sources: `src/extensions/{Modules,Pax,Filter}` (~21k built lines).
`Pax/paxtkinter.c` and `Pax/intl.c` (dead leftovers, not built and not
`#include`d anywhere) were deleted 2026-10-26; the broken
`simpleblocktext.py` plugin went with them.  **Correction
(2026-10-26):** `Pax/gcmethods.c` is *not* dead — it is unconditionally
`#include`d by `gcobject.c:342` (which is why it is absent from the
Extension sources list); deleting it broke a fresh build (the earlier
"not in the build" claim was wrong; an incremental rebuild masked the
breakage by reusing the stale `gcobject.o`).  `gcmethods.c` stays, as
does the `Pax/Generate/` generator that produces it.  Note for
archaeology: the `devtools/divaudit/ctypes_catalog.py` skip-filters for
the deleted file names are now inert (kept — harmless).

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
Note (verified 2026-10-26, see `divaudit-findings.md`): all live
`PyInt_AsLong` sites are preceded by `PyInt_Check` guards that reject
floats loudly -- preserve those guards in the port (as
`PyLong_Check`/`PyIndex_Check`); no silent-conversion hardening is
needed on the py2 side.

### The former one real design problem: skimage vs. the PIL C API — solved

This section documents the (now implemented) rework of the image
handling.  On 2026-10-24 option 4 below was implemented on the main
branch (suite-gated): `skimage.c` no longer contains any PIL symbol —
`Imaging.h`, the `ImagingObject` re-declaration, the untyped `"O"`
casts and `setup.py`'s `/usr/include/python2.7/Imaging` handling are
gone — and its py3 port is now mechanical (standard
`PyModuleDef`/`PyUnicode`/`PyBytes` work).

Original problem: `skimage.c` (1719 lines) implements the X11 display
scaling and the gradient/pattern fill math in C.  It reached into PIL's
*private* C internals: `#include "Imaging.h"`, a local re-declaration of
the `ImagingObject` struct from `_imagingmodule.c`, and Python passing
`PIL.Image.Image.im` (the internal core handle) into
`_sketch.copy_image_to_ximage`, `fill_{axial,radial,conical}_gradient`,
`fill_transformed_tile`, `write_ps_hex` and `fill_hsv_*`.  Modern
Pillow neither installs usable third-party headers nor guarantees that
struct layout — this could not simply be recompiled.

#### What PIL is actually used for (inventory, verified 2026-10-24)

Surprisingly little.  All per-pixel work in the interactive path
(scaling, affine transform, gradient/tile fills, dithering, hex export)
is Skencil's own C (`skimage.c`/`skdither.c`); PIL's algorithms never
run there.  In the rendering path PIL provides only *allocation*
(`PIL.Image.new` scratch buffers in `graphics.py:546`, `colordlg.py:145`,
`gradientedit.py:48`), *metadata* (`mode`, `size`) and *raw memory*
(`.im`, poked directly by skimage).  On the model/IO level the complete
list of PIL API use is:

| Use | Where |
|---|---|
| format decode on import (`Image.open`); `.sk` embedded images (base64/subfile stream → `load_image`); EPS preview (ghostscript temp file); cmxloader `fromstring` for embedded bitmaps | `Graphics/image.py:86`, `Plugins/Filters/skloader.py:355–361`, `Graphics/eps.py:61`, `cmxloader.py:797,844,851`, `ailoader.py`, `drawinput.py` |
| force lazy decode (`load()`) | `image.py:46`, `eps.py:62` |
| mode normalization at load + Grayscale command (`convert`) | `image.py:44,69` |
| Invert command (`ImageChops.invert`) | `image.py:74` |
| `.sk` embedded-image encoding (`save(file, 'PNG')`) | `Plugins/Filters/sksaver.py:522` |
| PS-export tile scaling (`im.resize`; again via `.im` internals) | `Graphics/psdevice.py:674` |
| export script only (`invert`, `convert`, `putalpha`, `save`) | `Scripts/export_raster.py:198–202` |

So the PIL object is the model's image container for historical
convenience — free universal codec, free pixel buffer with a
C-accessible layout, free one-off `convert`/`invert`/`resize` — not
because PIL's algorithms are needed.  The model only ever requires
mode ∈ {L, RGB, RGBA}, size, and packed raw bytes that C can read and
fill.  `Graphics/image.py` even states the original intent:
"It uses the Python Image Library for file I/O."

#### Options (decision made: option 4, implemented 2026-10-24)

1. **Buffer-protocol shim**: pass raw pixel bytes
   (`PIL.Image.tobytes()` / `frombytes`) plus mode and size into the C
   functions instead of `ImagingObject*`.  Keeps all the C math;
   changes ~15 call sites in skimage.c plus the Python callers; adds
   one copy per operation (acceptable for display-sized images).
2. Reimplement the fill/scale math in Python (numpy or plain) — no C
   build issue, but the canvas redraw path gets slower.
3. Vendor a minimal Imaging subset inside skimage (own struct, convert
   from PIL at the boundary) — most work, keeps zero-copy; superseded
   by option 4, which achieves the same from the model side.
4. **Internal image object (decided, preferred)**: replace the PIL
   object as the model's image representation with a minimal internal
   payload in `ImageData` — mode ∈ {L, RGB, RGBA}, size, packed
   `bytes`/`bytearray` pixels — and keep PIL strictly as the format
   codec at the boundaries (all import filters, `.sk` embedded-PNG
   encode/decode, ghostscript temp files for EPS previews,
   `export_raster.py`).  `skimage.c` then consumes the internal buffer
   via the buffer protocol: no PIL symbol remains in any C source;
   `Imaging.h`, the `ImagingObject` re-declaration, the untyped `"O"`
   casts and `setup.py`'s `/usr/include/python2.7/Imaging` handling all
   disappear.
   - **Faster than option 1**: display scale/transform reads
     zero-copy from the stored buffer and gradient fills write
     zero-copy into a `bytearray` scratch buffer (replacing
     `PIL.Image.new`); copies remain only at format boundaries
     (PIL decode → `tobytes()` → internal object on load; internal
     object → PIL → PNG on `.sk` save).
   - **RGBA is part of the design**: current display treats RGBA as
     opaque RGB (`scale_image` dispatches on
     `strncmp(image->mode, "RGB", 3)` and reads 4-byte pixels;
     `write_ps_hex` also ignores A).  This accident must become
     explicit behavior: the internal model keeps the alpha channel
     when present (never discards A at load), so image transparency
     support can be added later without another representation
     change; display keeps compositing onto the background for now.
   - **Off-display-path PIL operations are fine**: the Invert and
     Grayscale commands, the PS-export tile `resize`, and any future
     image operations may round-trip internal → PIL → PIL operation →
     internal; one copy per operation is acceptable there, since
     these run per user command or at export time, never per redraw.
   - Cost: touches ~10–12 files (`Graphics/image.py`, `external.py`,
     `pattern.py`, `skloader.py`/`sksaver.py`, `Base/load.py`,
     `psdevice.py`, the `graphics.py` display sites, `colordlg.py`,
     `gradientedit.py`) plus the skimage call sites.  Image
     caching/undo semantics (`ExternalData` filename cache,
     `SetData`) and the `.sk` file format (filename link or
     base64-PNG blob) must be preserved; the format round-trip and
     Xvfb tests are the gate.
   - Staging: fully doable on python2 first (stage A below,
     suite-gated): introduce the internal buffer, add
     buffer-protocol variants of the `_sketch` image functions,
     switch the call sites.  The py3 port of skimage then becomes
     mechanical (standard `PyModuleDef`/`PyUnicode`/`PyBytes` work).

Implementation notes (as done, 2026-10-24):

- **C side** (`skimage.c`): a local `SKImageData` struct (xsize/ysize/
  mode/pixelsize/linesize plus `image32`/`image8`/`image` row-pointer
  arrays) replaces the PIL `Imaging`/`ImagingObject` types; it is built
  from the Python-side packed buffer by `skimage_from_buffer()`
  (`PyObject_GetBuffer`, `PyBUF_WRITABLE` for the fill functions,
  `PyBUF_SIMPLE` for reads; `INT32`/`UINT8` are now defined locally —
  they used to come from `Imaging.h`).  All 11 entry points
  (`copy_image_to_ximage`, `transform_to_ximage`, the 3 gradient
  fills, `fill_transformed_tile`, the 4 HSV/RGB ramps, `write_ps_hex`)
  now take `(buffer, mode, width, height)` in place of the image
  object; the inner per-pixel loops are unchanged.  Wrong sizes and
  unsupported modes raise `ValueError` instead of being able to
  segfault (the former untyped-cast hazard).
- **Python side**: `Sketch/Graphics/image.py` defines `RasterImage`
  (mode ∈ {L, RGB, RGBA}, size, packed `data`; RGB/RGBA are 4 bytes per
  pixel like PIL's internal layout, L is 1) with the PIL boundary
  helpers `image_from_pil`/`image_to_pil` (raw modes `L`/`RGBX`/
  `RGBA`; note PIL's `frombuffer` map-buffer fast path returns mode
  `RGBX` for rawmode `RGBX`, so `image_to_pil` converts back to
  `RGB`).  `ImageData` stores that payload directly (no `__getattr__`
  forwarding, no `.im` anywhere); `Convert`/`Invert`/`Resize` round-trip
  through PIL off the display path.  Call sites switched: `graphics.py`
  (pattern images and gradients use `RasterImage` scratch buffers,
  `DrawImage` uses the ImageData/RasterImage buffer directly),
  `psdevice.py`, `colordlg.py`, `gradientedit.py`, `sksaver.py`,
  `aisaver.py`; `eps.py` converts the ghostscript preview to a
  `RasterImage`.
- **Behavior preserved**: the display treats RGBA as opaque RGB
  (unchanged), but the alpha channel is now kept end to end; `.sk`
  embedded-image format (base64 PNG) and the EPS/PS hex output are
  byte-identical to master (the format baselines pass unchanged).
  One subtlety worth remembering: in the display functions the
  source width/height are the image's own pixel size while the
  destination rectangle is computed separately in the caller
  (`DrawImage` scales/transforms the full image into a possibly
  different dest rect) — the initial port got this mixed up and the
  Xvfb smoke tests caught it.

`setup.py`'s `/usr/include/python2.7/Imaging` include-dir handling is
gone.

## Porting plan

Status 2026-10-26 (end of session): **stage A complete; stage B
complete (all six C extension modules build and import under py3);
stage C mostly done (Tkinter renames applied, headless model layer
works); 86 of 97 headless tests pass; the UI/Xvfb tests and the
remaining content diffs are open (stage C/D).**

Work is on the branch `py3` (py3-only sources; the `modernize` branch
remains the py2 reference).  Builds: `python3 setup.py build` →
`build/lib.linux-x86_64-3.10`; suite: `PYTHON=python3 test/run_tests.sh`.

Remaining py3 issues, verified by the suite (in rough priority order):

1. **Glyph-encoding round-trip -- FIXED 2026-10-27 (the .sk
   txt/pt byte contract).**  Root cause: the skread C lexer decoded
   every string literal as utf-8, including the txt/pt arguments,
   whose bytes are font-encoding codes; TextGids then resolved them
   as unicode characters (via glyph names) instead of font-encoding
   codes (MTMI txt(':') resolved the NAME colon, not code 58, and
   saved back as code 0).  The save side had the mirror problem:
   Font.EncodedText returned a str of codes which skrepr then
   utf-8-encoded.  Fix: parse_sk_line2 now takes a sequence of
   function names (skloader passes ('txt', 'pt')) whose string
   arguments are returned as the raw un-escaped bytes;
   Font.EncodedText returns bytes; TextGids iterates the bytes as
   ints; the PS/X11 sinks (quote_ps_string, xlfd_char_range, pax
   DrawString) receive bytes.  Also fixed on the way: the PS quote
   table's octal escapes (py3 oct() yields 0o251, breaking the
   three-digit \251-style escapes), Lib/type1.py bytes handling
   (BytesIO, int indexing, charstring interpreter), two stray
   Py_DECREF(value) calls on an uninitialized local in pstokenize.c's
   number branches (segfault in the charstring tokenizer), and the
   missing PY_SSIZE_T_CLEAN define in skaux.c (required for the s#
   format of _sketch.xlfd_char_range under py3.10; SystemError in the
   X11 core-font drawing path).  The save/reload-stable,
   fixture-baseline and sk2ps tests pass again (93 of 97 headless
   tests).
2. **`sys.exc_traceback` remnants** in `UI/prompt.py` and
   `Plugins/Filters/xfigloader.py` (use `sys.exc_info()[2]`).
3. ~~`reader_decodes_style_names_for_use_style`~~ and
   ~~`test_menu_tree_byte_string_path_rejected`~~ — FIXED 2026-10-27:
   both failures were py2 remnants in the *tests*, not the model.  The
   registry already rejects non-str menu components under py3 (the
   test used the py2-era plain literal 'TeX', now b'TeX'); the style
   name and EPS filename tests built their .sk fixtures with py2
   %r-of-bytes and bytes filenames — ported to skrepr() and unicode
   names.  The headless suite is 101/101 (ui tests still excluded).
5. **UI layer (stage C/D):** the Xvfb smoke tests are not run yet
   (`--ignore=test/ui`); `Sketch/UI/*` imports tkinter now, but the
   pax Tk integration (`call_py_method`, `wantobjects(0)` behaviour)
   needs the pre-flight experiment under Xvfb described above.
6. **Stage D:** devtools (`build-skencil`, `collect-app-dir`,
   AppImage), README, `.vscode`, `skconvert`/`skshow` launchers
   (already version-parameterized), user plugin in
   `~/.config/skencil/Plugins/latextext2.py` (TabError — a user file,
   not a repo file).

Stages are ordered so that everything that *can* be validated under
python2 happens first (stage A), the C port happens on a branch (stage
B), and the final switch is small (stages C–D).  The test suite is the
gate throughout; baselines are compared against master's
(`test/run_tests.sh --record` refreshes them when master moves).

- **Stage A — py2-compatible modernization — DONE 2026-10-26:**
  all of it, in suite-validated commits on the `modernize` branch:
  the 12 syntax-error files; `reduce` → `functools.reduce`;
  `__bool__` aliases; the `wrapper.py` `__cmp__` entry dropped;
  `execfile` → `exec(compile(...))`; the svgloader rewrite to
  `xml.sax` (ContentHandler/make_parser — and it turned out the
  plugin had been broken all along: it imported `skread` from
  `Sketch`, which does not re-export it; fixed, verified with a
  smoke SVG load); dead C sources deleted (see above);
  version-parameterized launcher build-dir paths
  (`sys.version_info`).  The stale `*.patch`/`*.sav` clutter is kept
  (not code; per AGENTS.md it is not touched without an explicit
  request).  Gate after every batch: build + 111 tests, green.
   Post-mortem note (2026-10-27): the tab/space normalization carried
   a semantic risk; one instance was found and fixed in the GUI work --
   UI/plugindlg.py TextParameter.build_widgets had the Text widget and
   the set/get adapter nested into the else branch (master had them
   tab-indented outside it), crashing every plugin dialog with a text
   parameter (Create -> LaTeX text).  When reviewing the other former
   syntax-error files, watch for the same pattern.
- **Stage B — C extensions on a port branch (python3):** in the order
  `_sketch` (geometry) → `streamfilter`/`_type1`/`skread`/
  `pstokenize` → `pax` → `skimage` last (its design decision is made
  and the model-side rework is already implemented on the main branch
  — option 4; the py3 port of skimage is now mechanical).
  Per module: `PyModuleDef` + `PyInit_`, the bytes/unicode split per
  the taxonomy, `PyCapsule` bridges, warning-free compile.  Gate per
  module: import + the headless model tests under py3
  (`test/testsupport.py` needs `Sketch.init_lib`, which requires
  `_sketch` and `streamfilter` first — order the work accordingly);
  formats/Xvfb once the Tk layer works.
- **Stage C — Python switch (same branch):** `Tkinter` → `tkinter`
  renames (43 files), the `TextEditor.py` dialog modules, removal of
  the stage-A shims, dict-view cleanups the suite surfaces.  Gate:
  full suite under py3 (model + formats + Xvfb smoke + LaTeX).
- **Stage D — environment and packaging:** devtools
  (`install-dev-packages`, `build-skencil`, `build-devroot`,
  `collect-app-dir` → python3 payload), `README.md`, `.vscode`
  settings, AppImage rebuild.  Gate: the app runs from the build tree
  and from the AppDir.

## Known risks

- **skimage/PIL** — solved (option 4 implemented 2026-10-24: internal
  image object, PIL as boundary codec; see the implementation notes
  in the C-extensions section).  Remaining py3 work there is
  mechanical; `write_ps_hex`'s `PyFile_AsFile` is py2-only and is
  handled with the rest of the stage-B module port.
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

