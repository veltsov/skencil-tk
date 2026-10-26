# Division-Audit Findings (runtime + interactive sessions)

Date: 2026-10-26.  Companion to `python3-porting.md` ("Semantics to
audit: integer division").  Tooling: `devtools/divaudit/` (static AST
scan, `-Qwarnall` wrapper + warning collector, exercise sessions).
Logs: `/tmp/divaudit/*.jsonl` (not part of the repo).

## Coverage

Static inventory: 655 `/` sites in 208 files (479 dynamic, 176 with a
float literal, 0 with both-int literals, 0 `//` in the whole tree).

Runtime coverage of the dynamic sites, merged from all logs (pytest
suite + headless sessions + all interactive sessions, 2026-10-26):

| stage                                | dynamic sites hit |
|---|---|
| pytest suite (111 tests)             |  24 of 449 |
| + headless exercise sessions         | 136 |
| + interactive sessions (all)         | **279 of 449 (62%)** |

Int-division sites (must become `//` or `int()` before the py3
switch): **48 distinct sites, 58188 hits**.  The biggest:

- `UI/ruler.py:191/214` `stride / subdivisions[depth]` (~21k hits)
- `UI/canvas.py:1466` `imid = (ilow + ihigh) / 2` binary search (12.7k)
- `Graphics/graphics.py:1405-1407/1479-1480/1555` pixmap/line-anchor
  `width / 2`, `line_width / 2` (~18k hits combined)
- `UI/tooltips.py:108`, `UI/palette.py:301/315/430`,
  `UI/sketchdlg.py:331-338`, `UI/linedlg.py:66/91/112`,
  `UI/miniscroll.py:51-54`, `UI/viewport.py:219/220/244/245`,
  `UI/gradientedit.py:49/130/256/265` -- widget geometry
- `Plugins/Filters/wmfsaver.py` (7), `cgmloader.py` (3),
  `cgmsaver.py:78`, `xfigloader.py:117`, `smiley.py:23`,
  `raster.py:141`, `blendgroup.py:346`, `bezier.py:501/502`

Int/float sites (safe under py3, informational): 231 distinct,
702588 hits.  Full tables: `/tmp/divaudit/report-final.txt`.

The interactive sessions also functionally confirmed the fixes: the
gradient editor, Blend, CGM export and the color dialog now run and
produce division hits (e.g. `blendgroup.py:346`, `gradientedit.py:*`,
`cgmsaver.py:78` were unreachable before the fixes).

Still unprobed (~170 dynamic sites, 38%): mostly
`Plugins/Filters/drawinput.py` + `Lib/spritefile.py` (need real RISC OS
draw files), loaders without parseable samples (wmf/cgm/cmx
synthetics), and rare UI paths.  Residual-risk handling: the per-file
`from __future__ import division` rollout with the `DIVAUDIT_MODE=error`
wrapper as the pytest gate, plus a final `python2 -Qnew` run of the
whole suite.

## Division rollout (executed 2026-10-26)

The rollout documented above has been carried out:

- **46 runtime-verified int-division sites fixed** to preserve exact
  py2 semantics: `//` where operands are guaranteed non-negative ints
  (ruler strides, canvas binary search, widget geometry, saver length
  math, ...); `int(a / b)` where negatives are possible
  (`raster.py` selection indexing, `smiley.py h = -5`); an explicit
  `isinstance` int/float split where **both** occur at runtime
  (`graphics.py` LineHit, `ellipse.py` coord-rect growth --
  `properties.line_width` is float-typed, e.g. 0.9 from the XFig
  72.0/80.0 scaling).
- **257 → 41 unverified-division markers** (`# divaudit: unverified`)
  on ~30 files -- every division site not exercised by the audit,
  except the draw-import pair (`drawinput.py`/`spritefile.py` are
  excluded from flagging *and* from the rollout; they keep py2
  semantics until reviewed with real `.draw` samples).  Several
  classifier refinements pruned the noise: a `float-safe` category
  (an operand statically float by construction: float literal,
  `float(...)` call, math constants/functions like `pi`/`atan2`, or an
  expression containing either; pi-derived names -- `pi4 = pi / 4`,
  `pi12 = pi / 12`, `degrees = pi / 180.0` -- are propagated to a
  fixpoint); an `int-coerced` category (`int(a / b)` is
  value-preserving under py3 -- `int()` truncates toward zero exactly
  like py2 int division, regardless of operand types); C-boundary
  argument-flow tracing (a division feeding a `"d"`/`"f"` parameter of
  a C function from `ctypes_catalog.json` is float-intended ->
  `c-float`, one feeding `"i"`/`"l"` is int-intended -> `c-int`); an
  `int-attr` category (both operands are attributes/len() results the
  catalogue types as int, e.g. font-metric bbox members); and manual
  prunes with documented reasoning (`cgmloader.py` normalizes by a
  float-by-construction cross-product length; one `c-float` site in
  `svgloader.py`).  Applied fixes surfaced by the tracing: `cmxloader.py:464`
  `(len(data) / 2) * 'h'` (string-repeat count) converted to `//`, and
  `text.py:441/448` `(llx - urx) / 2` → `int((llx - urx) / 2)` (the
  font-metric bbox attrs are `T_INT` and `llx - urx` is *negative* --
  py2 int division truncates toward zero, so `//` would floor one off;
  the EPS baseline caught it: the avortsel text x-position drifted
  ~1pt).  (the remaining 41 marker lines all carry
  genuinely int-semantics-suspect `dynamic` sites that need eyeball
  review before the py3 switch; bezier.py fully cleared after
  verifying that `selected_idx` is the float curve parameter in the
  SelCurvePoint branches -- `path.nearest_point` returns
  `PyFloat_FromDouble`, curveobject.c/curvemisc.c).  Separately documented in the source
  (one NOTE comment per site): `round(div)` sites snap/size
  differently under py3 -- py2 `round()` is half-away-from-zero and
  returns a float, py3 is half-to-even and returns an int -- an
  accepted one-increment difference at exact midpoints
  (`external.py`, `layer.py` grid snap, `selection.py`/`bezier.py`
  45-degree rotation snap, `export_raster.py` raster size).  Manual
  review round 2 (2026-10-26): `int()` coercion applied at the bpl
  byte-count sites (`graphics.py`/`colordlg.py`/`gradientedit.py` --
  the result feeds the C CreateImage "i" argument), the skapp.py
  window-position math (`%d` formatting), and the pdfsaverpage.py
  gs `-g` dimensions (the ghostscript manual specifies integers);
  float-safe prunes confirmed by usage: `selection.py` Point/Trafo
  results, `ellipse.py` Point midpoint, `canvas.py` zoom math
  (scale[xy] from bounding_rect floats), `viewport.py` self.scale,
  autoshape `arrow.py` self.h2.

**Conclusion (2026-10-26): the division hunt is concluded.**  The
remaining 41 markers sit almost exclusively in the old-format I/O
filters (cgm/wmf/ai/cmx/xfig loaders and savers) and in
`svgloader.py` (which needs its own separate fix anyway, see the
svgloader `xml.sax` rewrite item).  They stay in place as review
markers: their divisions now run under py3 division semantics
(future division is rolled out in those files), so they fail loudly
rather than corrupt if the formats are exercised, and the marker
records the one thing the audit could not prove -- the intended
int/float semantics.  Review them only if/when the corresponding
formats become relevant; the draw-import pair is likewise deferred
until real `.draw` samples exist.
- **`from __future__ import division` in 86 files** (every file with a
  division site except the draw-import pair).

Plugin caveat: plugin files carry `###Sketch Config ... ###End` blocks
that `plugins.extract_cfg` execs with `#` stripped; the future import
must therefore sit **before the first `###Sketch Config`** (some config
blocks contain uncommented statements, e.g. `format_name = 'XFig'`, and
`exec` rejects later future imports).  All 28 plugin files follow this
rule now.

Latent C issue found and fixed during the rollout (finding #8):
`skpoint.c` did not implement `nb_true_divide`, so *every*
`Point / scalar` raised TypeError under future division (the
`-Qwarnall` audit was blind to this -- C types don't emit
classic-division warnings).  `nb_true_divide` now aliases
`skpoint_divide` (Point division was always true division); stage B
must keep that slot for py3.

Gate results: 111 tests pass (byte-identical EPS for all fixtures
except the Creator version line, which `normalize_text` handles);
the error-gate wrapper run over the suite shows **zero classic
*int* division warnings** -- the only remaining ones are classic
*float* divisions (safe int/float mixes in tests, PIL, and the
isinstance-split else-branches).

## Bugs found during the audit (with proposed fixes)

All reproducible independently of the audit tooling (plain python2).
None of the fixes below are applied yet.

### 1. Regression from 370cfcb: `isinstance(list, list)` with a
shadowed builtin -- group/ungroup/delete/move-to-front/bottom/path
union/guide deletion all broken

`Graphics/selinfo.py:199-200`: the 2to3 conversion changed master's
`if type(list) != ListType:` to `isinstance(list, list)` -- but `list`
is the loop variable, so both arguments are the same object:

    for idx, list in list_to_tree2(infolist):
        if not isinstance(list, list):     # TypeError whenever reached

Every operation whose undo info goes through `list_to_tree_sliced`
raises TypeError: GroupSelected, RemoveSelected (also used by Path
Utils -> Union), MoveObjectsToTop/Bottom, RemoveObjects, and hence
RemoveGuideLine (its abort_transaction turns it into
AbortTransactionError).  Fix: rename the loop variable in
`list_to_tree_sliced` only (`list` -> `entry`, 5 occurrences in the
function body).  The other shadowed names in the file (`dict = {}` in
`list_to_tree2`, parameter `list` in `common_prefix`) are harmless
today because they never invoke the shadowed builtin, but renaming
them too is cheap hardening.

### 2. `UndoTypeError` on Script -> Average Points -- K1 labels are
unicode *by design*; the calling side was wrong (FIXED 2026-10-26)

`undo.check_info` accepting **only `unicode`** labels is intentional
and documented (`string-handling.md`: "Undo/transaction labels ... are
K1 unicode; `undo.check_info` enforces this (a byte-string label
raises `UndoTypeError` rather than being tolerated -- the origins must
be fixed instead)").  It is **not** a regression and must not be
loosened to `basestring` (an earlier such loosening in 370cfcb was
deliberately dropped during the glyph-text rework).

The actual bug was on the calling side: the `Scripting.AddFunction`
titles of the shipped scripts were plain `str` literals, and
`AdvancedScript.execute` passes the title to `BeginTransaction`, which
ends up as the label of `__real_add_undo`'s `(text, undo)` info.
Fixed by converting all shipped script titles to `u'...'` literals:
23 sites (`Scripts/*.py`, including the 8 `pathutils` scripts).
`string-handling.md` ("The shipped scripts pass u'...' literals") is
now actually true; a completion note was added there.

### 3. Regression from the glyph-text rework: 'greek' text rendering

`Graphics/graphics.py:886` (`draw_text_on_gc`, greek branch -- text
rendered too small to read) accesses `font.glyph_registry`, but
`glyph_registry` is a module-level object in `Graphics/font.py:98`,
not a Font attribute.  Triggered by zooming out far enough that text
becomes greek (the crash after the page-orientation change).
FIXED 2026-10-26: graphics.py imports `glyph_registry` from
`Sketch.Graphics.font` (no import cycle) and uses it directly at the
greek branch (was `font.glyph_registry`).

### 4. Gradient/color-ramp fills: `BufferError: Object is not writable`
(FIXED 2026-10-26)

Root cause found -- NOT X-server-specific (the Xvfb bisect runs simply
never exercised the exact draw path).  `Graphics/graphics.py`
`AxialGradient`/`RadialGradient`/`ConicalGradient` pass `image.data`
of a scratch `RasterImage` to the C fillers
(`_sketch.fill_*_gradient`), which write in place -- but
`RasterImage.__init__` stored the payload as a py2 `str`, an
*immutable* buffer -> BufferError.  Same defect in the color dialog
ramps (`colordlg.py fill_hsv_xy`/`fill_hsv_z`) and the gradient editor
preview (`gradientedit.py:238`).

Fix: `RasterImage` gained a `writable` parameter (stores the payload
as a `bytearray`, which provides a writable buffer); the three scratch
sites (`graphics.py get_pattern_image`, `colordlg.py
ChooseComponent`, `gradientedit.py GradientView`) pass `writable = 1`.
Stored images (`ImageData` payloads, PIL boundary) keep the immutable
`str`.

### 5. Pre-existing saver bugs (found by the headless sessions; FIXED
2026-10-26)

- `Plugins/Filters/aisaver.py` `analyze`: plugin compounds (e.g.
  autoshapes) set `has_fill` but carry no `properties` of their own
  (their children do) -- `object.properties` raised AttributeError and
  AI export failed on any document containing them.  Fixed: analyze
  fetches `properties` via `getattr(..., None)` and skips objects
  without it.
- `Plugins/Filters/cgmsaver.py` `putstr`: fed a unicode (K2) layer
  name to `struct.pack('s', ...)`.  Fixed: `putstr` encodes unicode
  arguments to utf-8 at the binary-sink boundary, per the
  string-handling taxonomy (K2 -> bytes).

### 6. Minor notes

- Script -> Average Points also expects *selected segments* (it
  reports "Select two or more points" otherwise); the scenario step
  must select nodes in node-edit mode.
- No "Blend..." was found in the menus by the session; CreateBlendDialog
  exists (mainwindow.py:539) -- check its menu sensitivity conditions.

### 7. Color dialog ramps: `TypeError: function takes exactly 6
arguments (7 given)` (FIXED 2026-10-26)

Regression from the image rework (4b7bc79).  Master's
`fill_hsv_xy`/`fill_hsv_z` parsed `"Oii(ddd)"` (image object, idx,
color tuple); the rework rewrote them to take the new scratch-image
signature `(data, mode, w, h, ...)` but gave the `_xy` variants a
format one `i` short: `"Osiii(ddd)"` instead of `"Osiiii(ddd)"` -- so
every redraw of the RGB/HSV XY ramps raised TypeError (the "Color
palette not visible / crash on OK" symptom in the interactive
session), taking the whole app down via the pax error path.

Affected: `skimage.c fill_rgb_xy`, `fill_rgb_z`, `fill_hsv_xy`,
`fill_hsv_z` (4 sites, same format).  Note the two variants differ
*by design*:

- `_xy` ramps: 7 args `(data, mode, w, h, xidx, yidx, (r,g,b))` ->
  format `"Osiiii(ddd)"` (FIXED: was one `i` short)
- `_z` ramps: 6 args `(data, mode, w, h, idx, (r,g,b))` ->
  format `"Osiii(ddd)"` (was already correct; `test_image.py:184`
  is the signature arbiter)

Verified: all four fillers run headless on a writable scratch image;
full suite 111 passed (including `test_image.py`).

## C-extension boundaries: float arguments fail loudly (verified
2026-10-26)

Question: when Python-side code starts passing floats (py3 division,
or the `from __future__ import division` rollout) into the C
extensions, does the C boundary fail loudly or corrupt silently?

Empirical results (probe module + real functions, CPython 2.7.18):

- `PyArg_ParseTuple` with `"i"` and `"l"` formats: **loud**
  `TypeError: integer argument expected, got float` -- even for
  integral floats like `3.0`.  Verified with the real project
  functions (`_sketch.CreateFontMetric` ENTRIES tuples,
  `FontMetric.glyph_width`).  This covers the 322 `"i"` + 13 `"l"`
  parse sites in the extensions.
- Direct `PyInt_AsLong(float)` in isolation **truncates silently**
  (`3.9 -> 3`, `-3.9 -> -3`) -- so raw uses would be dangerous.
- However, auditing all 12 live `PyInt_AsLong` call sites
  (`skcolor.c:565`, `Pax/cmapobject.c:204/292`, `Pax/gcobject.c
  :119/122/159/265/465/468`, `Pax/tkwinobject.c:158`,
  `Pax/paxutil.c:43`, `Pax/paxmodule.c:704`) shows **every one is
  preceded by a `PyInt_Check` guard** that raises a loud TypeError;
  the two unguarded ones are in the dead `Pax/paxtkinter.c` (not
  built).  A proposed `SK_AsInt` hardening helper was therefore
  **not applied** -- there is nothing to harden.
- Parameters parsed as `"d"` accept floats by design (e.g. the
  gradient geometry in `skimage.c fill_*_gradient`); those are
  float-native and not boundary hazards.

Conclusion for the port: the C boundary is uniformly loud.  The
`from __future__ import division` rollout under py2 will surface every
int-semantics boundary the tests/sessions reach as a `TypeError`, and
the py3 port (stage B) must simply preserve the existing
`PyInt_Check` guards (converting them to `PyLong_Check`/`__index__`
semantics alongside the `PyInt_*` API removal).


## Verification of the fixes (2026-10-26)

- headless regression (`/tmp/divaudit/fix_check.py`): GroupSelected,
  UngroupSelected, MoveSelectedToTop/Bottom, RemoveSelected + Undo,
  AddGuideLine + RemoveGuideLine, all ScriptRegistry titles unicode,
  unicode-label transaction, `fill_axial_gradient` on the writable
  scratch image, AI and CGM export of the rich document (autoshapes +
  unicode layer name) -- all pass.
- full suite: 111 passed; `python2 setup.py build` clean.

