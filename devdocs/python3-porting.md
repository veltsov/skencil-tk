# Python 3 Porting — Findings and Plan Notes

Goal: port skencil-tk from Python 2.7 to Python 3 while keeping the app
working. This file collects everything discovered so far about
Python-2-only code. Counts are from greps over `src/` (count = number of
files containing the construct, not occurrences).

## Big risks / architectural blockers

1. **`paxtkinter` replaces `_tkinter`** (`Sketch/__init__.py:init_ui()`
   sets `sys.modules['_tkinter'] = paxtkinter`). This is C code written
   against the Python 2 `_tkinter` C API. It is the single biggest C
   porting job. Need to study `extensions/Pax/paxtkinter.c` against the
   Python 3 `_tkinter` internals; alternatively drop `paxtkinter` and see
   what still works (its comment says it exists to work around threaded
   `_tkinter` in Python 1.5.2 — modern Tk may make it unnecessary, but
   `UI/tkext.py` depends on `pax.register_object` /
   `pax.create_tcl_commands` behavior).
   **Update (2026-10-20):** fully analyzed in
   `devdocs/paxtkinter-analysis.md` — the 1.5.2 GIL/TclLock problem
   still exists in py2.7/py3, but pax's dependency surface on
   `paxtkinter` is tiny and a concrete redesign exists to drop it in
   favor of stock `_tkinter` (work planned on branch `modernize`).
   **Resolved on branch `modernize`:** paxtkinter was dropped; pax now
   works with the stock `_tkinter` (GIL-safe callbacks via
   `PyGILState_Ensure`, threaded-Tcl requirement checked at startup).
   See `devdocs/modernize-paxtkinter.md`. For the py3 port only
   `paxmodule.c` (937 lines) remains to port instead of paxtkinter +
   pax (~3200 lines).
2. **`pax` module** — X11 pixmaps/GC/windows/TkWin objects; C code using
   the Tk C API (`tkwinobject.c` uses `Tk_Window` internals via
   interpaddr) and Tcl command plumbing. Must be checked against the
   Tk 8.6 C API (fine) *and* the Python 3 C API (`TclObject` type etc.).
3. **Python C API migration** in all extension modules:
   `extensions/Modules/*.c`, `extensions/Pax/*.c`,
   `extensions/Filter/*.c`. They use old C-API idioms (`PyString_*` vs
   `PyUnicode_*`, `PyInt_*`, module init via `initname()` instead of
   `PyInit_name`). Each module needs: `PyMODINIT_FUNC PyInit_<name>`,
   module state (or simple statics), `PyUnicode` for text, `PyBytes`
   for binary, and review of integer handling (`PyInt` gone,
   `long` vs `Py_ssize_t`).
4. **`skreadmodule` / `.sk` parsing** — `parse_sk_line2` implements a
   restricted eval of save-file lines; its C code and the Python side
   (`Plugins/Filters/skloader.py`) need review during the port
   (the py2-idiom surface there was cleaned in the modernize batch).
5. **PIL naming** — resolved in the modernize batch: only the `PIL`
   package form is supported now.
6. **Binary vs text files** — file formats (.sk, SVG, EPS, PS, PDF) are
   read/written in text mode in py2. In py3, mixed text/binary and
   implicit `str`/`bytes` conversions need explicit encodings.
   Also ASCII assumptions in EPS/PDF code (`dscparser.py`, `type1.py`).
   For `.sk` the encoding is now decided: strings are utf-8 byte
   strings written as `\x`-escaped `repr()` literals without the `u`
   prefix, byte-compatible with master (see
   `devdocs/unicode-runtime-audit.md`); the loader-side explicit
   decode **is implemented** for the user-provided strings (K2:
   layer/guide/grid names, style names, paper-format names) — see
   `devdocs/string-handling.md` for the full string-kind taxonomy,
   which is the Stage-4 checklist for the remaining str/bytes work
   (text content and file names stay byte strings by design).

## Inventory of Python-2-only constructs (updated 2026-10-20)

The modernize batch (see `devdocs/modernize-roadmap.md`) already
converted, within py2-compatible syntax: print statements (+
`from __future__ import print_function`), `except X, e` → `as`,
`has_key` → `in`, `apply` → `*args`, old-style `raise`, backtick repr,
`<>` → `!=`, `exec` statements → `exec(...)`, `string.*` functions and
`from string import` names → str methods/builtins, `types.*` →
builtins/`isinstance` (FunctionType/MethodType remain as
`types.FunctionType`/`types.MethodType`), `cPickle` → `pickle`,
`os.popen` → `subprocess` helpers, `im_*`/`func_*` attrs → new-style
names, `__cmp__` → rich comparisons.

Remaining py2-only surface (approximate):

| Construct | Files | Notes |
|---|---|---|
| `import Tkinter` / `from Tkinter import` | ~40 | → `tkinter` renames |
| `tkFileDialog`/`tkMessageBox`/`tkSimpleDialog` | 1 | TextEditor.py |
| `unicode` / `basestring` assumptions | sparse | e.g. tkext MakeCommand `(str, unicode)` tuple |
| `string.maketrans` | 3 | dscparser.py, svgloader.py, font.py → `str.maketrans` |
| `sys.maxint`, `long(...)` | 2 | undo.py, drawfile.py |
| `imp` module (plugin loading) | 1 | plugins.py |
| dict `.keys()` indexing / sorting patterns | ~9 | need `list(...)` or rework |
| integer division `/` | sparse | audit geometry/pattern code |
| dict mutation during iteration; `sort` with `cmp`-style callbacks | audit | |
| `xml.sax.saxlib` (SVG loader) | 1 | broken already on py2.7; rewrite to `xml.sax` |
| `reduce` builtin | 4 | → `functools.reduce` |
| `sys.maxint` | 2 | `Base/undo.py`, `Filters/Lib/drawfile.py` → `sys.maxsize` |
| `long(...)` | 1 | `Filters/Lib/drawfile.py` |
| `getopt.error` | 1 | OK in py3 (alias of `GetoptError`) — no change needed |

(The rows for print/except/has_key/apply/string/types/cPickle/popen/
exec/funcattrs/`__cmp__`/`import new` were removed — all resolved by
the modernize batch. The `import new`/`SortedList` entry for
`Script/pathutils/base.py` was a false positive.)

Additional py3 semantics to audit everywhere (no reliable grep):
- integer division `/` → float (geometry code in `Sketch/Graphics/*`,
  dithering/pattern math, trafo code);
- implicit `str`/`int` mixing; `%`-formatting with tuples;
- `file(...)` builtin; `open` modes ('b' needed for images/PDF);
- `dict.items()` views; mutation of dicts during iteration;
- `Tkinter` constants (uppercase `END`, `BOTH`, ...) — mostly still
  present in py3 tkinter, verify per use;
- truth tests relying on `__nonzero__` in plugin objects.

## Recommended strategy (initial proposal)

1. **Keep python2 working until the end.** The build environment is
   python2-only today; port in stages, validating after each stage in
   the devroot/container.
2. **Stage 0 — tooling:** run `2to3` (or better, `futurize` from
   `python-future`) in a scratch branch to get a full diff of required
   changes; use it as a checklist, not as a blind patch.
3. **Stage 1 — pure Python, mechanical:** make `src/` py2/py3 syntax
   compatible (print functions, `except as`, `has_key`, `apply`, `<>`,
   `string` module, `types`, `tkFileDialog`) using six-style shims or
   `python-future` imports so both interpreters can run it during
   the transition.
4. **Stage 2 — C extensions:** port `streamfilter`, `skreadmodule`,
   `pstokenize`, `_type1module`, `_sketchmodule` first (mostly
   plain C-API), then `pax`, and decide the fate of `paxtkinter` (see
   risks). Update `setup.py` (it hardcodes
   `/usr/include/python2.7/Imaging`, and launcher/devtools assume the
   `lib.linux-x86_64-2.7` build dir name).
5. **Stage 3 — Tk layer:** rename `Tkinter` imports, audit `tkext.py`
   and `canvas.py` against pax changes, fix `im_func`-era
   introspection in `connector.py`, `command.py`, `tkext.py`, loaders.
6. **Stage 4 — semantics:** integer division, str/bytes in file
   filters, `__cmp__` → rich comparisons, dict views, exception
   hierarchies.
7. **Stage 5 — environment:** new build env (python3 + python3-tk +
   Pillow + tcl-dev/tk-dev); update `README.md`, `devtools/`
   (`install-dev-packages` pins `python2`), and
   `devtools/collect-app-dir` (copies `/usr/bin/python2.7`).

## Environment facts relevant to the port

- Current dev env is Ubuntu 20.04 focal with python2 at
  `/usr/bin/python2`; `.vscode/settings.json` points at it. The py3
  analogue of the package list would be `python3 python3-dev python3-tk
  python3-pil python3-pil.imagetk tcl-dev tk-dev`.
- Version-parameterize these hardcoded spots (search for `2.7`):
  `src/skencil` (sys.path insert of `lib.linux-x86_64-2.7`),
  `setup.py` (`build&copy`, DEBIAN section), `devtools/collect-app-dir`.
- `Sketch/VERSION` = `1.0`; `PKG-INFO` records the fork's history
  (Herzog 1996–2007, Novikov 2010, Eltsov 2018).
- Localization now uses the standard `gettext` module (the custom
  `intl` C extension was dropped on the `modernize` branch) — nothing
  to port here; in py3 the shim's `ugettext` calls become `gettext`.

