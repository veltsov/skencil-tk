# Import Restructuring — Canonical Package Layout

Date: 2026-10-23, branch `modernize`.  This document records the
findings about the import machinery of the application (gathered while
re-evaluating `python3-porting.md`) and the executed restructuring into
a canonical, py3-compatible package layout.  It supersedes the
"implicit relative imports" entry in the py3 port inventory: after this
restructuring the Python side of the port no longer contains any
package/import mechanics work.

## Findings (verified empirically in the build tree)

### The effective module names differ from the file layout

| Directory | Effective import name(s) | Mechanism |
|---|---|---|
| `Sketch/*.py` | `Sketch.*` | normal package |
| `Sketch/Base/*.py` | `Sketch.warn` etc. — **not** `Sketch.Base.*` | `Base` prepended to `Sketch.__path__`; `Base/` had **no** `__init__.py` |
| `Sketch/Modules/X.py` | `Sketch.X` and bare `X` | `Modules` on `Sketch.__path__` **and** on `sys.path` |
| `Sketch/Modules/{paxmodule,_sketchmodule}.so` | `pax`, `_sketch` (bare), plus aliases `Sketch.Graphics.pax`, `Sketch._sketch` | legacy `module.so` import suffix + `sys.path` insert + py2 relative-fallback registration (verified: `sys.modules` contained all four names simultaneously) |
| `Sketch/Modules/{streamfilter,pstokenize,...}.so` | `streamfilter` (bare), `Sketch.pstokenize` | plain `.so` suffix + `sys.path` insert / `__path__` extension |
| `Plugins/**` | `Sketch.Plugins.Filters.ailoader` etc. | **fake packages**: `create_packages()` builds empty modules with `__path__ = []` in `sys.modules`; files loaded with `imp.load_module` under the synthetic dotted name |
| `Lib` dirs on the plugin path | `Sketch.Plugins.Filters.Lib.drawfile` | `_search_dir` turns any `Lib` directory into a fake subpackage whose `__path__` points at the real directory |
| `Script/` | real top-level package `Script.*` | has `__init__.py`; build root on `sys.path` (launcher); menu scripts via `__import__("Script.create_star")` |

### Why it existed

Pre-0.6 Sketch was a flat, non-package program; when it became a
package the old flat module names were preserved.  The bare/relative
imports themselves are pure py2-default convenience; the path
manipulations are load-bearing *only* as long as the bare names are
used.

### py3 blockers discovered in this mechanism (not visible from `.py` greps alone)

1. **~250 implicit-relative import statements** (`import tkext`,
   `from Graphics.arrow import`, …) — all `ImportError` under py3.
2. **The `module.so` suffix is gone in py3** (py3 `EXTENSION_SUFFIXES`
   has no `module.so`; verified on py3.10).  Bare `import pax` /
   `import _sketch` therefore fails on py3 even with the `sys.path`
   entry in place.  `streamfilter` is unaffected (plain `.so`).
   Related oddity: `import Sketch.Modules.paxmodule` (the distutils
   Extension name!) fails even on py2, because the C init function is
   `initpax` — the Extension name was never the runtime name.
3. **Plugin imports break on py3 for two reasons**: the fake-package
   resolution of `from Lib import drawfile` depends on implicit-
   relative `sys.modules` lookups, and the bare C-module imports
   depend on `sys.path` + `module.so`.
4. **Saved documents are rename-safe**: `.sk` files contain bare
   constructor names only, mapped through the loader's `func_dict`
   registry (`Base/load.py`, `Filters/skloader.py`); no module paths
   are embedded.  Plugin classes register under bare names via the
   `###Sketch Config` blocks.  Package renames therefore do not break
   the file format (proven by the unchanged baselines).

## The executed restructuring

Principles: one real package tree; canonical name == file path
everywhere; **absolute imports only**; no `sys.path`/`__path__` magic;
C extensions named after the names their C code declares; no
compatibility shims (old user plugin/script code may need its import
lines updated — the `###Sketch Config` blocks and the
`from Sketch import _` idiom are unchanged).

### Final layout

    src/
      Sketch/                        the one application package
        __init__.py                  public facade: _(), config, geometry + model re-exports
        VERSION
        x11.py                       <- Sketch/Modules/X.py
        Base/                        real subpackage (gained __init__.py)
        Graphics/  Lib/  UI/  Scripting/   real subpackages (as before;
                                     UI/gtkutils.py renamed to tkutils.py)
        Modules/                     real subpackage, C extensions only
          __init__.py
          pax.so                     <- paxmodule.so
          _sketch.so                 <- _sketchmodule.so
          streamfilter.so  pstokenize.so  skreadmodule.so  _type1module.so
        Plugins/                     <- src/Plugins, now real
          Filters/{__init__.py, Lib/ (__init__.py), ...}
          Objects/ {__init__.py, Lib/ (__init__.py, multilinetext/, autoshapes/), ...}
        Scripts/                     <- src/Script, real subpackage

Canonical import forms: `from Sketch.Base.warn import ...`,
`from Sketch.UI import tkext`, `from Sketch.Modules import pax`,
`from Sketch.Plugins.Filters.Lib import drawfile`,
`from Sketch.Scripts import unit`, `from Sketch import x11` (or
`from Sketch.x11 import ...`).

### Deleted mechanisms

- `create_packages()` and all `imp.*` use in `Base/plugins.py`
  (replaced by `importlib.import_module`; `imp` is gone in py3.12).
- The `sys.path.insert(1, Sketch/Modules)` hack in `Sketch/__init__.py`.
- The `__path__` extension loop for `Base` and `Modules`.
- The fake-`Lib`-package creation in `_search_dir` (user `Lib` dirs are
  appended to the real `Sketch.Plugins.<cat>.Lib.__path__` instead).
- The bare `import X` / `import pax` / `import tkext` universe.
- The dependence on the `module.so` legacy import suffix.

### User plugin/script directories

The user configuration directory is `$XDG_CONFIG_HOME/skencil`
(default `~/.config/skencil`), overridable with the `--configdir=DIR`
option (`Base/main.py`, applied between option parsing and `init_ui`;
the default itself is computed at `import Sketch` time by
`configutil.init_directories` via `user_config_directory()`).  This
deliberately differs from the pre-reorganization `~/.sketch`, so this
version and master can coexist without sharing any user state.

User content lives below the configuration directory, **without
`__init__.py` in the user's directories**:

- `Plugins/` is appended to `config.plugin_path` and scanned like the
  built-in tree; a user file `Plugins/Filters/myformat.py` imports as
  `Sketch.Plugins.Filters.myformat`, `Plugins/<name>.py` as
  `Sketch.Plugins.<name>`.
- `Scripts/` is appended to `Sketch.Scripts.__path__`; a user script
  `Scripts/myscript.py` is importable as `Sketch.Scripts.myscript`
  (usable in the `standard_scripts` preference).
- `userhooks.py` is executed by file path.  The `config` object
  (`Sketch.Base.config`) is predefined in its namespace — hooks
  reference `config.user_config_dir`, `config.plugin_path`, ... without
  imports or hardcoded paths.

Guarded by `test/model/test_config.py` (XDG resolution, --configdir
parsing).

### The import rule

Every import is absolute.  `from Sketch import ...` inside the package
works during `Sketch/__init__.py` execution (Sketch is already in
`sys.modules`, partially initialized).  No relative-import syntax is
used anywhere — also because `Script`-style payload files may be
exec'd top-level, where relative syntax raises `ValueError`.

## Status: executed (B0–B6, 2026-10-23); 85/85 tests green after every
batch, baselines unchanged

- **B0** — this document.
- **B1** — `Base` real (`__init__.py`; imports to `Sketch.Base.*`;
  `__path__` loop for `Base` removed).
- **B2** — C module canonicalization: setup.py Extension names
  `Sketch.Modules.pax` / `_sketch` / `skread` / `_type1` (the old
  Extension names never matched the C init functions; they only worked
  through the legacy `module.so` suffix, dropped in py3); Python
  imports to `Sketch.Modules.*`; `X.py` to `Sketch/x11.py`;
  `Modules/__init__.py`; `Modules` `__path__` extension and the
  `sys.path` insert removed.
- **B3** — `gtkutils.py` to `UI/tkutils.py`.
- **B4** — `src/Script` to `src/Sketch/Scripts`; `standard_scripts`
  names; script-internal sibling imports.
- **B5** — `src/Plugins` to `src/Sketch/Plugins`; real `__init__.py`s;
  loader on `importlib`; scanned directories registered on their
  package's `__path__` (user plugins import as `Sketch.Plugins.*` with
  no `__init__.py` of their own); `create_packages` prefers real
  packages and only fakes user-defined nested categories; `imp` fully
  removed; all plugin-internal imports rewritten.
- **B6** — sweep of all remaining bare sibling imports (58 files in
  UI, Graphics, Lib, Scripting, plus `Sketch/__init__.py` itself);
  `userhooks` executed by file path — the last `sys.path` insertion
  is gone.

## Additional findings made during execution

1. **The C extensions import sibling modules by bare name at init:**
   `_sketchmodule.c` did `PyImport_ImportModule("pax")` and
   `pstokenize.c` `PyImport_ImportModule("streamfilter")`.  Both are
   canonical now (`Sketch.Modules.pax` / `Sketch.Modules.streamfilter`).
   This was masked during B2 by a stale build tree (see item 3).
2. **Module-level import cycles** survive the from-submodule form only
   via the `sys.modules` partial-module idiom (plain `import` used to
   short-circuit them implicitly).  Two cycles existed:
   `config -> connector -> warn -> config` (fixed in B1) and
   `tkext -> tooltips -> tkext` (fixed in B6, `tooltips.py`).  The
   idiom: `import Sketch.PKG.X` + `X = sys.modules['Sketch.PKG.X']`.
3. **distutils quirks:** `build_scripts` skipped recopying the changed
   launchers (run `python2 setup.py build_scripts --force` after
   changing `src/skencil`/`src/sk2ps`); the known mtime-equality trap
   also applies to renamed extensions (delete the stale `.o`).
4. **User code had to be updated, as planned:**
   `~/.sketch/userhooks.py` (`import Sketch.config` ->
   `from Sketch.Base import config`) and the user plugin
   `~/.sketch/Plugins/latextext2.py` (`from Sketch import ..., main` ->
   `from Sketch.Base import main, load`).  Both failures surfaced as
   modal dialogs / missing fonts under the UI (the hooks extend the
   font path), i.e. they fail loudly, not silently.
5. **Remaining non-import py2 syntax** (for the py3 port): a py3
   `compileall` over `Sketch/` reports only 22 SyntaxErrors (old-style
   except/raise remnants in a handful of files) — the import-level py3
   blockers are all gone.  Pre-existing broken modules unrelated to
   this work and left as-is: `svgloader.py` (`xml.sax.saxlib`, roadmap
   item C1) and `simpleblocktext.py` (imports a `lib.blocktext` that
   does not exist anywhere in the tree).


