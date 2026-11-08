# Test Suite

An automatic regression test suite lives in `test/` (tracked; the
gitignored `tests/` directory remains the hand-run scratch area).  It
protects the application code from regressions and pins the behavior
of `master` as a reference.

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
| `test/model/` | layer 1: headless document-model tests (load, save/reload, mutations, undo, bezier node edits, glyph/text behavior, internal raster image representation) |
| `test/formats/` | layer 2: `sk2ps` output vs baseline EPS (byte compare, then ghostscript raster compare), fig import, headless `.sk.gz` load, the `skconvert` script |
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
   export (`test/formats/test_svg.py`) is compared differently: the
   SVG rasterized by Inkscape against the ghostscript rendering of the
   `sk2ps -e` output of the *same* build (fonts embedded, as most are
   unknown to ghostscript; no baselines; 4x downsampled to
   remove antialiasing differences), plus structural checks; its own
   fixture `svgall.sk` is not in the manifest (path text, which the
   master build cannot load).  Skipped without `inkscape`.  SVG import
   is deliberately NOT tested (the SVG loader is broken on modern
   Pythons; separate project).
3. **App smoke tests.** The full application runs under `xvfb-run`,
   driven by a `--run-script` payload (executed by `mainwindow.py`
   before the mainloop).  Asserts exit status 0 and no traceback.
   Covers bare launch, every fixture, and opening the Layers dialog
   (the pax/GIL crash canary); `smoke_export.py` exports through the
   main window's `SaveToFile` with every export plugin, Export Again
   and a gzip-compressed save.
4. **Screenshot tests.** `shot_basic/shot_mutated/shot_xdotool`
   payloads capture the X root window (ImageMagick `import`) after a
   fixed set of document mutations, or after synthetic keyboard input
   (xdotool arrow keys move the selection).  Compared against master
   baselines with a tolerance (`tol` per-pixel, `max_frac` budget).

## Requirements

python3 + build tree, pytest, xvfb, ghostscript (`gs`), ImageMagick
(`import`), xdotool (for the input test), inkscape (SVG export tests),
dvisvgm (EPS objects in SVG export; inkscape is the fallback).  All comparisons go through
`test/testsupport.py`.

## UI test isolation and harness behavior

- The ui tests run with an isolated `--configdir` and the AppDir fonts
  via `SKETCH_FONTPATH` (the user config must not leak: its plugins
  abort loads with modal dialogs, its default unit changed the
  screenshots).
- The app answers MessageBoxes with Cancel under
  `SKENCIL_TEST_HEADLESS=1` instead of blocking on modals.
- `--run-script` payloads must schedule work via `root.after(...)`
  inside the mainloop; a long synchronous body before the mainloop can
  deadlock in the Tk/pax layer.  Payloads end with
  `root.destroy(); os._exit(0)` — the suite measures app behavior,
  not interpreter teardown (pax finalization at `Py_Finalize`).
- The Xvfb app runner kills the whole process group on timeout (plain
  `proc.kill()` would leak Xvfb and skencil children).

## Baseline pitfalls

- **bm()/im() ids.**  Saved `.sk` files embed `id(image_data)` in
  `bm(...)`/`im(...)` directives — never reproducible;
  `testsupport.normalize_sk()` masks ids of 12+ digits and rewrites
  the (absolute) external file references to `<DATA>/...`.
- **External references are stored relative to the CWD** the app/save
  ran in.  Fixtures are therefore always loaded by absolute path
  (`test/testsupport.data_path`), and the saved files are normalized
  for comparison.
- **LaTeX toolchain (`test/ui/test_latex.py`).**  The LtxObj recompile
  test needs latex/pdflatex, pstoedit and gs; it is skipped when they
  are missing.  It selects the pscyr preamble when installed (as in
  the rustext.sk fixture); without a Type 1 cyrillic font (pscyr or
  cm-super) the LaTeX output uses Type 3 bitmap fonts which pstoedit
  cannot interpret — the recompiled object then renders empty and the
  test only verifies the utf-8 path and the saved parameter.
- The LaTeX undo behavior is pinned by `test/ui/test_latex_missing.py`
  (rejection when the toolchain is missing, tools hidden) and
  `test_latex.py::test_latex_undo_exact_state` (byte-identical
  undo/redo, no toolchain runs).
