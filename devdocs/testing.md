# Test Suite

An automatic regression test suite lives in `test/` (tracked; the
gitignored `tests/` directory remains the hand-run scratch area).  It
exists to protect the Python 3 port and the modernization work from
regressions, and to pin the behavior of the last `master` commit as a
reference.

## Quick start

    test/run_tests.sh              # run everything, compare against baselines
    test/run_tests.sh -k tarr      # run a subset (pytest -k)
    test/run_tests.sh --record     # (re)generate baselines from master
    test/add-fixture tests/foo.sk  # install a new fixture + its references
                                   # and regenerate its baselines

`--record` creates a git worktree of `master` at the revision recorded
in `test/baselines/BASELINE-REV`, builds it, and runs the whole suite
against that build with `SKENCIL_TEST_RECORD=1`; all golden artifacts
are rewritten.  Normal runs use the repository's own `build/` tree.
When master has moved past the recorded revision, the runner prints a
staleness warning.

## Layout

| Path | Contents |
|------|----------|
| `test/testsupport.py` | build-tree bootstrap, fixture handling, comparisons (text/EPS raster/screenshot), Xvfb app runner |
| `test/conftest.py` | pytest bootstrap (imports testsupport before any test module) |
| `test/collect_refs.py` | extracts `eps()`/`bm()` file references from `.sk` files; used by add-fixture |
| `test/record.py` | regenerate baselines for given fixtures (used by add-fixture) |
| `test/data/` | fixtures: `.sk` files + every external file they reference, `fixtures.txt` manifest |
| `test/model/` | layer 1: headless document-model tests (load, save/reload, mutations, undo, bezier node edits) |
| `test/formats/` | layer 2: `sk2ps` output vs baseline EPS (byte compare, then ghostscript raster compare), fig import |
| `test/ui/` | layers 3+4: full app under Xvfb driven by `--run-script` payloads (`test/ui/scripts/`), screenshot comparisons |
| `test/baselines/` | golden artifacts recorded from master: `sk/` (.sk saves), `eps/` (EPS + rasterized PNG), `shots/` (screenshots), `BASELINE-REV` |
| `test/output/` | per-run artifacts (gitignored) |

## Test layers

1. **Model tests (no display).** `Sketch.init_lib()` + `load_drawing`;
   mutate documents via the public API: `TranslateSelected` (needs a
   `Point`, not a tuple), `TransformSelected(Scale(..))`,
   `RotateSelected` (degrees; 90° is known-buggy upstream),
   `SetLayerState`, `MoveLayerUp/Down`, `SetProperties` (note: the line
   property is `line_pattern`, a `SolidPattern`, not a color), bezier
   node edits via `Paths()`/`SetPaths()` with `path.Duplicate()`,
   `path.Translate()`, `path.SetLine(idx, (x, y))`.  Every mutation is
   checked for undo/redo and save/reload stability.
2. **Format tests.** Round-trip stability of saved `.sk` files and
   `sk2ps` output compared against master baselines (exact bytes, then
   ghostscript rasterization with a small pixel-diff tolerance).  SVG
   import/export is deliberately NOT tested (the SVG loader is broken
   on modern Pythons; separate project).
3. **App smoke tests.** The full application runs under `xvfb-run`,
   driven by a `--run-script` payload (executed by `mainwindow.py`
   before the mainloop).  Asserts exit status 0 and no traceback.
   Covers bare launch, every fixture, and opening the Layers dialog
   (the pax/GIL crash canary, see `modernize-paxtkinter.md`).
4. **Screenshot tests.** `shot_basic/shot_mutated/shot_xdotool`
   payloads capture the X root window (ImageMagick `import`) after a
   fixed set of document mutations, or after synthetic keyboard input
   (xdotool arrow keys move the selection).  Compared against master
   baselines with a tolerance (`tol` per-pixel, `max_frac` budget).

## Requirements

python2.7 + build tree, pytest 4.6.x (the last py2-compatible line),
xvfb, ghostscript (`gs`), ImageMagick (`import`), xdotool (for the
input test).  All comparisons go through `test/testsupport.py`.

## Known behaviors and findings (2026-10-21)

- **Master segfaults at interpreter shutdown** (exit 139,
  `Py_Finalize` → pax finalizer after Tcl teardown).  The app itself
  runs fine; fixed on `modernize` by the GIL-safe pax callbacks.
  Therefore all `--run-script` payloads end with
  `root.destroy(); os._exit(0)` — the suite measures app behavior, not
  interpreter teardown.  Revisit if pax finalization is ever fixed on
  master.
- **`u'...'` in saved .sk files (modernize regression).**  The gettext
  shim returns unicode, so layer/grid/guide names are saved as
  `layer(u'Layer 1',...)`; the `.sk` parser (parse_sk_line2) cannot
  parse the `u` prefix → `test_save_reload_stable[zz.fig]` and
  `test_fixture_baseline[zz.fig]` are RED on `modernize`, green on
  master.  **Fixed 2026-10-21** (write side): `sksaver.py` encodes
  unicode strings to utf-8 via `skrepr()` before `repr()`, so non-ascii
  text is saved as `\x`-escaped byte-string literals exactly as master
  wrote it; both tests are green again and no baselines needed
  re-recording.  Now guarded by `test/model/test_unicode.py`, which
  injects unicode into object properties (layer name, LtxObj text
  parameter), saves and rereads, using the `rustext.sk` fixture
  (Russian layer name and LaTeX text; untracked like all fixtures —
  install with `test/add-fixture`).  See
  `modernize-roadmap.md` (gettext item) and
  `devdocs/unicode-runtime-audit.md` (encoding decision + planned
  proactive tooling for this bug class).
- **UndoTypeError on every keystroke while typing text (modernize
  regression, fixed 2026-10-22).**  The text editor keystroke commands
  had an empty *byte-string* menu name (`AddCmd(..., '')`), which
  `ObjectCommand.Invoke` passes as the transaction name into the undo
  info: `__real_add_undo` builds `('', undo)`, and `undo.check_info`
  accepted a `str` label on master (`type(func) == StringType`) but
  only `unicode` after the string-handling work → `UndoTypeError` per
  keypress, which also killed the incremental redraw (the text only
  appeared after the next full redraw).  Fix at the **origins** (the
  type-check policy forbids tolerating both string kinds in checks):
  the command menu names are unicode now (`u''` in `text.py`,
  `autoshapelib.py`; byte menu names of the plain canvas/mainwindow
  commands normalized as well, plus `plugindlg.py`'s `u'Create ' +
  menu_text` concat), and `undo.check_info` enforces unicode labels.
  Guarded by `test_typing_via_call_object_method` and
  `test_command_menu_names_are_unicode` in
  `test/model/test_glyphs.py`.
- **`u'...'` in the preferences file (same regression class; fixed
  2026-10-22, superseded 2026-10-23).**  `configutil.save_repr` used
  plain `repr`, so unicode preference values (the `mru_files` list in
  particular, `sample_text` potentially) were saved as `u'...'` with
  `\u` escapes into `preferences.py`.  The 2026-10-22 fix serialized
  `.sk`-style (utf-8 `\x`-escaped byte reprs) and normalized
  `mru_files` after loading — but the post-hoc fix-up assignment
  compared the byte values read by `execfile` against the unicode
  list inside `ProgramDefaults.__setattr__`, printing the startup
  `UnicodeWarning` from `config.py:112` for non-ascii MRU names.
  Current fix: the preferences file has its own format — plain utf-8
  string literals (coding cookie in the header, no `u'...'` prefix,
  no `\x` escapes; identical syntax under py3, where no conversion is
  needed at all) — and the loader executes the file into an
  intermediate attribute bag (`configutil._LoadedPreferences`),
  converting all values strictly to unicode before anything is
  assigned to the live preferences object.  Guarded by
  `test_preferences_save_repr_plain_utf8_literals`,
  `test_preferences_load_converts_to_unicode` and
  `test_preferences_undecodable_values_dropped` in
  `test/model/test_unicode.py`.

- **bm()/im() ids.**  Saved `.sk` files embed `id(image_data)` in
  `bm(...)`/`im(...)` directives — never reproducible;
  `testsupport.normalize_sk()` masks ids of 12+ digits and rewrites
  the (absolute) external file references to `<DATA>/...`.
- **External references are stored relative to the CWD** the app/save
  ran in.  Fixtures are therefore always loaded by absolute path
  (`test/testsupport.data_path`), and the saved files are normalized
  for comparison.
- **Sketch classes are old-style Python 2 classes**: `type(obj).__name__`
  is `'instance'` for everything; use `testsupport.class_name(obj)`
  (`obj.__class__.__name__`).
- **LaTeX toolchain (`test/ui/test_latex.py`).**  The LtxObj recompile
  test needs latex/pdflatex, pstoedit and gs; it is skipped when they
  are missing.  It selects the pscyr preamble when installed (as in
  the rustext.sk fixture); without a Type 1 cyrillic font (pscyr or
  cm-super) the LaTeX output uses Type 3 bitmap fonts which pstoedit
  cannot interpret — the recompiled object then renders empty and the
  test only verifies the utf-8 path and the saved parameter (see
  `devdocs/unicode-runtime-audit.md`).
- The Xvfb app runner kills the whole process group on timeout (plain
  `proc.kill()` would leak Xvfb and skencil children).
