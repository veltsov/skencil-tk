# Modernize Roadmap (pre-Python-3 cleanups)

Simplifications that are useful in themselves and shrink the eventual
Python 3 diff. Everything here runs unchanged on Python 2.7; nothing
port-specific (Tkinter renames, bytes/str, module shims) is touched.
Executed on branch `modernize`, in small batches (build + Xvfb smoke
test after each).

## Status: batches A and B executed (2026-10-20); C items open

## A. Dead workarounds and dead code — EXECUTED

1. **PIL import workaround** (`_import_PIL` in `Sketch/__init__.py`):
   modern Pillow always provides the `PIL` package; all real code uses
   `from PIL import Image`. Collapsed to a plain package import + error
   message; the `create_packages('PIL')` / `sys.modules` patching
   fallback path is gone (`create_packages` itself is still used by
   plugins.py).
2. **`pax.do_one_event`**: unused anywhere → removed from
   `paxmodule.c`.
3. ~~Disabled locale-build dead code in `setup.py`~~ — kept as a
   reminder (per maintainer decision); `generate_locales` is still a
   no-op and the committed `.mo` files are used.
4. `string.split(sys.version)[0][0:3]` → `sys.version[:3]` in
   `setup.py` (2 sites, `build&copy` paths).
5. Tuple-parameter syntax `def rgb_to_tk((r, g, b)):` in
   `Sketch/UI/tkext.py` — illegal in py3 → unpacked body, py2+py3.

## B. Mechanical Python-2.6+/2.7-compatible modernizations — EXECUTED

Applied with `python3 -m lib2to3` restricted to *safe* fixers (which
produce py2.6+-compatible code), then manually reviewed, plus manual
work for what lib2to3 does not cover. Fixers used: `has_key`, `apply`,
`except`, `ne`, `funcattrs`, `exec`, `print`, `raise`, `repr`.
Deliberately NOT used: `import` (would rename Tkinter→tkinter etc.),
`types` (partial rewrites), `unicode`, `long`, `map`/`filter`/`zip`,
`idioms`.

| Change | Sites (at start) | Notes |
|---|---|---|
| `d.has_key(k)` → `k in d` | 91 in 36 files | fixer `has_key`; plus the bound-method assignment in UI/palette.py and the unused UndoDict.has_key removed |
| `apply(f, args)` → `f(*args)` | 255 in 73 files | fixer `apply`; chained calls (`apply(Trafo, m)(t)`) by hand |
| `except X, e:` → `except X as e:` | 32 in 21 files | fixer `except` |
| `print` statements → `print()` | 71 in ~24 files | fixer `print` + `from __future__ import print_function` in 24 touched files |
| old-style `raise X, msg` → `raise X(msg)` | 74 in ~30 files | fixer `raise` (found after the first pass) |
| backtick `` `x` `` → `repr(x)` | few | fixer `repr` |
| `func_name`/`im_self`/`im_func`/`func_code` → `__name__`/`__self__`/`__func__`/`__code__` | 7 sites, 5 files | fixer `funcattrs` + manual (2to3 does not rewrite all `im_*`) |
| `<>` → `!=` | 4 files | fixer `ne` |
| `exec` statements → `exec(...)` | 3 files | fixer `exec` (tuple form works in py2) |
| `string.*` → str methods / `int()` / `float()` | ~60 sites in 25 files | attribute form (`string.join`→`sep.join`) and bare `from string import` form (21 files, custom balanced-paren converter); `string.uppercase`→`string.ascii_uppercase`; `string.maketrans` kept (py2-only, py3-port item) |
| `types.*` → builtins/`isinstance` | ~140 sites in 31 files | `type(x) == StringType` → `isinstance(x, str)` etc.; `InstanceType` case by case; `FunctionType`/`MethodType` kept as `types.FunctionType`/`types.MethodType` (valid in py3) |
| `cPickle` → `pickle` | 1 file | manual |
| `os.popen` → `subprocess` | 8 in 8 files | new `util.popen_write`/`util.popen_read` (Popen with PIPE); no site uses the old close() exit status |
| `__cmp__` → rich comparisons | 5 classes | GraphicsObject (identity), SolidPattern/Arrow (identity-of-color/path — the old cmp fell back to address comparison), Scripting Wrapper, multilinetext Style; `__eq__`/`__ne__`/`__lt__` defined explicitly (py2 does not derive `__ne__` from `__eq__`) |

### Lessons learned during the batch (relevant for the py3 port)

- **lib2to3 fixer names**: the print fixer is `print` (not `paren`);
  unknown fixer names are silently ignored — verify each pass really
  changed something.
- **Plugin config sections**: `plugins.extract_cfg` extracts the
  `###Sketch Config ... ###End` block of every plugin file and `exec`s
  it. A `from __future__` import inserted inside that block is a
  SyntaxError and silently unregisters the plugin. Future imports in
  plugin files must go before the marker.
- **Shadowed builtins**: some functions have parameters/named locals
  shadowing builtins (`def make_menu_tree(dict)` in registry.py,
  `def flatten(list)` in util.py) — the old code used
  `types.DictType`/`ListType` to dodge that; after conversion those
  had to be renamed. Watch for this in the py3 port.
- **Nested-call rewrites**: multi-site rewriters must re-scan after
  every splice (nested calls shift offsets); position-list-based
  splicing corrupted files until rewritten to leftmost-first + rescan.
- **`has_key` → `in` on C types**: the has_key fixer converts calls on
  ANY receiver. `_sketch.SKCache` (extensions/Modules/skaux.c) is a C
  type that only supported `.has_key` via attribute delegation to its
  inner dict; `x in cache` raised
  `TypeError: argument of type 'SKCache' is not iterable`. Fixed by
  adding a `sq_contains` slot (SKCache_contains) AND the
  `Py_TPFLAGS_HAVE_SEQUENCE_IN` tp_flag — py2.7's `PySequence_Contains`
  ignores `sq_contains` without that flag, and in py2.7 its value is
  `(1L<<1)` (not 1<<17). Without the flag the type is treated as
  non-iterable. Audit remaining `in` conversions for other C-type or
  custom-class receivers during the py3 port.
- **distutils timestamp equality**: if a source file and its .o have
  equal mtimes, distutils may skip recompilation — a rebuilt .so can
  still contain old code. Force with `rm build/temp/**/<file>.o`.

## C. Deeper cleanups (py2-compatible, more care needed) — open

1. **SVG import filter is broken on any modern Python 2.7**:
   `Plugins/Filters/svgloader.py` imports `xml.sax.saxlib`/`saxexts`
   (PyXML-era modules that no longer exist). Needs a rewrite to
   `xml.sax.handler`/`xml.sax.make_parser`. Pre-existing, unrelated to
   the modernization batch (discovered while testing it).
2. `imp` module in `plugins.py` (`new_module`/`find_module`/
   `load_module`) — removed in py3.12; could be rewritten now, touches
   the plugin loader (deferred).
3. `gtkutils.py` → rename to `tkutils.py` (misleading GTK-era name) —
   cosmetic; deferred.
4. `tkFileDialog`/`tkMessageBox` in
   `Plugins/Objects/Lib/multilinetext/TextEditor.py` — py2-only module
   names; simplest during the py3 port.
5. `string.maketrans` call sites (dscparser.py, svgloader.py,
   font.py) — py2-only; py3 has `str.maketrans`.
6. The `*.sav*`/`*.patch` backup files — delete in a dedicated commit
   with maintainer approval.
7. **gettext shim returns unicode, old intl returned str** (found
   2026-10-20 via the LaTeX plugin Apply crash): every `_()`-produced
   string is now `unicode`, so `isinstance(x, str)` / `type(x) is str`
   checks that can receive translated (or other `_()`-derived) strings
   silently break.  Fixed in the undo chain (`undo.py` `Undo`,
   `_get_callable`, `check_info`, `UndoText`/`RedoText`;
   `document.py` `add_undo`) and `registry.py` (`Add` menu path) by
   using `basestring`.  Same class, second crash (found via the
   rotation-handle stream of `UnicodeDecodeError`s): the info
   converters in `Sketch/UI/converters.py` return byte strings,
   and `conv_angle` contains a latin-1 degree sign (0xb0);
   joined with the now-unicode `_()`-templates by `util.format`
   (selection.py: `_("Rotate by %(angle)[angle]")`) this raised
   `'ascii' codec can't decode byte 0xb0` on every rotation drag
   -- fixed by making `angle_format` a unicode literal
   (`u'%.1f�'`).  Other `isinstance(.*, str)` sites
   (`load.py`, `image.py`, `psdevice.py`, `type1.py`, `skloader.py`,
   `ailoader.py`, `tkext.py` bitmaps, `command.py`, `palette.py`,
   `warn.py`) currently only receive byte strings (file system or
   config data; Tk entry values come back as str because of
   `wantobjects(0)`) and were left alone -- revisit during the py3
   port, where `str` unifies both anyway.  Note: **lib2to3 has no
   `basestring` fixer**; the py3 port must rewrite `basestring` ->
   `str` by hand.
   **Third instance, found by the test suite (2026-10-21):** unicode
   names leak into *saved files*: `sksaver` writes
   `layer(u'Layer 1',...)` / `guidelayer(u'Guide Lines',...)` /
   `grid(...,u'Grid')` when the name came from `_()`-derived defaults
   (e.g. documents imported from .fig).  The `.sk` parser
   (`parse_sk_line2` in `skreadmodule.c`) rejects the `u` string
   prefix (`SyntaxError: ')' expected`), so such documents cannot be
   reloaded -- `.sk` round-trip of `zz.fig` fails (red tests
   `test_save_reload_stable[zz.fig]` /
   `test_fixture_baseline[zz.fig]` in the suite, green on master).
   Fix options: save plain `str` in sksaver (encode explicitly), or
   teach the C parser the `u''` prefix.
   **Fixed 2026-10-21, on the write side (the parser was left
   unchanged):** all file-bound `repr()` calls in `sksaver.py` now go
   through `skrepr()`, which encodes unicode strings to utf-8 first.
   Non-ascii text is therefore saved as `\x`-escaped plain byte-string
   literals, byte-identical to master's output (verified against
   master-saved files with Russian layer/text content; the full suite
   is green again, baselines unchanged).  Rationale, format decision
   and follow-up tooling: `devdocs/unicode-runtime-audit.md`.
8. **`map(f, lines)` rewriting picked the wrong string method**
   (found 2026-10-20 via the broken PDF export):
   `fix_leftovers` rewrote `map(lstrip,
   procfile.readlines())` in `psdevice.py` to
   `[l.rstrip() for l in ...]` -- stripping the NEWLINE
   instead of leading whitespace, gluing the whole
   PostScript prolog into one line (gs:
   `/undefined in defSketchDict`) and breaking PDF/EPS
   export.  Fixed to `l.lstrip()`.  Lesson: when
   rewriting `map(strip_fn, seq)` to comprehensions,
   preserve the function identity exactly
   (strip/lstrip/rstrip are not interchangeable; rstrip
   also eats the trailing newline).  The PDF export path
   (psdevice prolog -> gs pipe) is now part of the
   validation: `sk2ps` output must pass
   `gs -sDEVICE=nullpage` with exit 0.

## Non-goals for this phase

- `bytes`/`str` unification, `Tkinter`→`tkinter` renames, print
  function everywhere via future imports in ALL files, dict views,
  integer division — these are py3-port work, done later.
- `X.py` (X11 constants) is alive (used by const.py, graphics.py and
  4 dialogs) — stays.
- `undodict.py`, `skcompleter.py`, `loadres.py` are used — stay.

## Validation harness

- `python2 setup.py build` (must be warning-free)
- `python2 -m py_compile` over all touched files
- in-process: `Sketch._(...)` translation checks (de/C locale)
- Xvfb runs: 100-hammer stress (resizes + nested `update()`), Layers
  dialog repro, `call_py_method`/widget-command probes, German-locale
  app start with menu label probe
