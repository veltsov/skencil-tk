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
   (`Plugins/Filters/skloader.py`, uses `types.StringType`,
   `string.atoi`, `apply`) are deeply Python-2.
5. **PIL naming** — `Sketch/__init__.py:_import_PIL()` already supports
   `PIL` as a package, but also has a legacy path importing top-level
   `Image`; modern Pillow under py3 only exposes the package form.
6. **Binary vs text files** — file formats (.sk, SVG, EPS, PS, PDF) are
   read/written in text mode in py2. In py3, mixed text/binary and
   implicit `str`/`bytes` conversions need explicit encodings.
   Also ASCII assumptions in EPS/PDF code (`dscparser.py`, `type1.py`).

## Inventory of Python-2-only constructs (by grep, file counts)

| Construct | Files | Notes |
|---|---|---|
| `print` statement (py2 syntax) | 24 | plus `print >>file` in `Sketch/Graphics/document.py`, `graphics.py` |
| `except X, e:` syntax | 21 | must become `except X as e:` |
| `d.has_key(k)` | 36 | → `k in d` |
| `apply(f, args)` | 73 | → `f(*args)`; many in graphics/UI code |
| `import Tkinter` / `from Tkinter import` | 40 | → `tkinter` camelCase renames (`Tkinter→tkinter`, `TclError→tkinter.TclError`, ...) |
| `import string` + `string.*` functions (`strip`, `atoi`, `join`, ...) | 7 / 21 | use `str` methods / `int()` |
| `im_func`/`func_code`/`im_self`/`func_name` | 5 | `ailoader.py`, `skloader.py`, `connector.py`, `UI/command.py`, `UI/tkext.py` — renamed to `__func__`, `__code__`, `__self__` |
| `os.popen` / `commands` module | 13 | e.g. `pdfsaver.py`, `mainwindow.py`, `curvedlg.py`, `drawfile.py`; → `subprocess` |
| `exec` statement (as statement) | 3 | `Base/plugins.py`, `UI/mainwindow.py`, `UI/prompt.py` |
| `types.StringType` etc. | 1 | `Filters/cmxloader.py`; also `from types import StringType, TupleType` in `load.py`, `skloader.py`, etc. |
| `reduce` builtin | 4 | → `functools.reduce` |
| `<>` operator | 4 | → `!=` |
| `sys.maxint` | 2 | `Base/undo.py`, `Filters/Lib/drawfile.py` → `sys.maxsize` |
| `long(...)` | 1 | `Filters/Lib/drawfile.py` |
| `cPickle` | 1 | `Objects/Lib/multilinetext/TextEditor.py` → `pickle` |
| `tkFileDialog`/`tkMessageBox`/`tkSimpleDialog` | 1 | `TextEditor.py` → `tkinter.filedialog` etc. |
| `import new` / `SortedList` | 1 | `Script/pathutils/base.py` |
| `__cmp__` (also `__div__`, `__rcmp__`, `__nonzero__`) | 7 | `Graphics/base.py`, `pattern.py`, `arrow.py`, `clone.py`, `selection.py`, `Scripting/wrapper.py`, `iterator.py` → rich comparisons / `__truediv__` |
| `for k in d.keys()` patterns | 9 | views in py3; `list(d.keys())` where indexing/sorting needed |
| `getopt.error` | 1 | OK in py3 (alias of `GetoptError`) — no change needed |

Additional py3 semantics to audit everywhere (no reliable grep):
- integer division `/` → float (geometry code in `Sketch/Graphics/*`,
  dithering/pattern math, trafo code);
- ordering of objects (`sorted`, `max`) relying on `__cmp__`;
- implicit `str`/`int` mixing; `%`-formatting with tuples;
- `file(...)` builtin; `open` modes ('b' needed for images/PDF);
- `dict.items()` views; mutation of dicts during iteration;
- `raise X, msg` / `raise X, msg, tb` syntax (grep found none, but
  re-check after 2to3-style conversion);
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

