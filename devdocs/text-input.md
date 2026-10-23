# Text Input Rework — Findings and Plan

Status: **planned, not implemented** (2026-10-22).  This document
records the analysis of the keyboard input path and the design for a
dedicated "improve text input" task.  See also `devdocs/glyph-text.md`
(the glyph-index representation this builds upon).

## Current state (verified on the glyph-index representation)

* `canvas.KeyPressEvent` (`src/Sketch/UI/canvas.py`, ~line 564) converts
  every key event to a **latin-1 byte** via `tkext.utf8_to_latin1` and
  uses it both as the keymap stroke and as the argument of the
  `InsertCharacter` editor command:
  `cmd.Invoke(stroke)` → `CallObjectMethod(CommonText, '', 'InsertCharacter', char)`.
* `utf8_to_latin1` raises `UnicodeEncodeError` for any character outside
  latin-1 (e.g. `u'\u0444'`), so typing Cyrillic (or Greek, etc.)
  crashes in the Tk callback.  This predates the glyph-index rework.
* Even without the crash, non-latin-1 characters can never reach the
  editor: the `InsertCharacter` command is registered with
  `key_stroke = tuple(printable)` where `printable` is the latin-1
  printable byte string, and the keymap only dispatches strokes that
  match a registered `key_stroke`.
* The model side is already encoding-agnostic (see
  `devdocs/glyph-text.md`): text is a gid array, `SimpleText` accepts
  unicode, and `glyphnames.unicode_to_glyphname` maps any character to
  a glyph name (`'uniXXXX'` convention outside latin-1).  Only the
  input path is latin-1-bound.
* Fonts: none of the bundled AFMs contain Cyrillic.  Classic Cyrillic
  Type 1 fonts (URW Cyrillic, pscyr, cm-super/lh) name their glyphs
  with legacy `afiiNNNNN` names (e.g. `U+0444` → `afii64352`), not
  `uni0444`; OpenType-derived AFMs use `uniXXXX`.  For a typed
  character to resolve against a font's charset, both conventions must
  be tried.

## Undo-label lesson (fixed 2026-10-22, keep in mind here)

The per-keystroke transaction is labelled with the command's menu name,
which for the editor keystroke commands is an empty **byte string**;
`undo.check_info` must therefore keep accepting `str` labels
(`isinstance(f, (str, unicode))`, see `devdocs/testing.md`).  Any input
rework must not regress this (guarded by
`test_typing_via_call_object_method`).

## Planned design

1. **`Sketch/Lib/glyphnames.py` — expand the unicode↔name table**
   * Fetch the official AGLFN list (adobe-type-tools/agl-aglfn) once
     and extract its `afiiNNNNN ↔ Unicode` entries (~300, the Cyrillic
     block U+0400–U+04FF and related) into an embedded alias dict.
   * New `unicode_to_glyphnames(char)` → tuple of candidate names:
     latin-1/control exact names, else `('uniXXXX', 'afii…')` for
     Cyrillic, else `('uniXXXX',)`.  The existing
     `unicode_to_glyphname` (canonical single name) stays.
   * Extend `glyphname_to_unicode` with the reverse alias table so
     `TextAsUnicode()` displays afii-named glyphs correctly.
2. **`Font` — charset-aware resolution** (`src/Sketch/Graphics/font.py`)
   * `Font.__init__` stores the font's full glyph-name set (all AFM
     names; they are already registered in the global registry).
   * `GidForUnicode(char)`: try each candidate name against the font's
     own name set first (so `afii64352` wins for a pscyr font,
     `uni0444` for an OpenType-named one); if none matches, register
     the canonical name.
3. **Editor — accept unicode** (`src/Sketch/Graphics/text.py`)
   * `InsertCharacter(char)` accepts a single unicode character: gid
     via `font.GidForUnicode(char)`; insertion stays gated by
     `IsPrintableGlyph` (a glyph the font cannot encode is rejected —
     same as today's unencodable latin-1 characters, no invisible
     notdef spam).  The byte-char path stays as is.
4. **`canvas.KeyPressEvent` — unicode input without breaking the
   keymap** (`src/Sketch/UI/canvas.py`)
   * Normalize once: `char = as_unicode(event.char)` (Tk returns
     unicode or ascii bytes; `util.as_unicode` handles both).
   * Keymap strokes keep using the latin-1 byte form when encodable
     (zero change to existing bindings; py2 dict keys for non-ascii
     would not match between unicode and bytes), falling back to the
     raw unicode char in the stroke otherwise.
   * New fallback after both keymap lookups fail: if `char` is
     printable (the existing `ord >= 32` filter) and
     `self.document.IsEditMode()`, invoke
     `self.document.CallObjectMethod(CommonText, '', 'InsertCharacter',
     char)` — the same call path the keymap uses, so transactions,
     undo and the redraw queue are handled uniformly.
   * `utf8_to_latin1` remains in `tkext` for the multilinetext dialog
     (that plugin's byte-level text is a separate, format-visible
     contract).
5. **Tests**
   * `test/model/test_glyphs.py`: Cyrillic mapping (`u'ф'` → candidates
     `('uni0444', 'afii64352')`), reverse mapping, `InsertCharacter(u'é')`
     inserts, `InsertCharacter(u'ф')` is a no-op under Times-Roman
     (font lacks the glyph), and a synthetic font-name-set test proving
     an afii-named font resolves.
   * Full suite re-run; baselines must stay green (input only, no
     serialization changes).  Headless reproduction of the typing path:
     `SetMode(EditMode)` + `document.CallObjectMethod(CommonText, '',
     'InsertCharacter', <char>)` (see `test_typing_via_call_object_method`).

## Scope limits / open items

* No `.sk`/serialization change; glyphs absent from the font remain
  rejected — full-charset insertion (typing glyphs the font cannot
  encode) stays a future item.
* The multilinetext dialog input stays latin-1 (`utf8_to_latin1` at
  `Plugins/Objects/multilinetext.py:242`); it would crash the same way
  for non-latin-1 input — a separate follow-up decision, since the
  plugin's text is stored as K3 bytes in the file format.
* X11 core-font drawing and PS export of typed non-latin-1 glyphs work
  only if the glyph is in the font's 256-code encoding (the
  `IsPrintableGlyph` gate guarantees this).

## Known quirk: code 45 is named 'minus' (intentional, keep)

**Do not "fix" this without a new `.sk` format version** (see the
compatibility note at the end).

The hardcoded standard-encoding table `Sketch/Lib/encoding.py`
(`iso_latin_1`) maps byte 45 to the glyph name **`'minus'`**, although
the Adobe Standard Encoding position 0x2D is the ASCII hyphen-minus,
named `'hyphen'` in the AGL and in essentially every real AFM (Times,
Helvetica, Courier, Palatino, URW, and the cyrillic pscyr fonts —
verified against all bundled `Fontmetrics/*.afm`: code 45 is the only
ASCII-region divergence between the table and the AFMs; the table even
has `'hyphen'` at code 173, the ISOLatin1Encoding position).  This was
an intentional decision of the original author (the ASCII `-` doubling
as a minus), not an oversight — and it is disliked, but it is the
byte-level contract of the existing `.sk` files.

With the glyph-index representation (`devdocs/glyph-text.md`) the
*name* becomes the cross-font identity, which surfaces the quirk:

* `-` typed with a standard-encoding font (e.g. Times) becomes the gid
  of `'minus'` (the table overrides the font's own AFM names for
  standard-encoding fonts).
* Changing that text to a font whose AFM names code 45 `'hyphen'`
  (e.g. `TextbookPSCyr`, or any other font) leaves the `'minus'` gid
  unresolvable: the glyph is not in the new font's charset, so it is
  not encodable → code 0 → notdef → **the `-` disappears**.
* Master's byte representation reinterpreted the byte `0x2D` in the
  new font's encoding, where it is again a hyphen — so it "worked"
  accidentally, relying on byte positions coinciding across encodings.

**Decision (2026-10-22): leave the code as is.**  Renaming byte 45 to
`'hyphen'` in the table would change the glyph identity that existing
`.sk` files' `-` characters resolve to; `'minus'` and `'hyphen'` are
distinct glyphs with different widths (and different AFM entries), so
re-mapping old files' `-` through the new name would change glyph
widths and therefore the positions of subsequent characters — a
compatibility break for existing documents.  The rename belongs to the
next `.sk` format version, together with the other format extensions
outlined in `devdocs/glyph-text.md` (glyph-name serialization).

Interim consequences to keep in mind:

* A `-` (and only that character — code 45 is the sole ASCII
  divergence) may vanish when its text object is switched to a font
  whose encoding names code 45 differently.  Workaround until the
  format bump: retype the `-` *in the target font* (then it maps
  through the target font's own name), or avoid switching fonts on
  texts containing `-`.
* `glyphnames.unicode_to_glyphname('-')` returns `'minus'` for the
  same reason; the unicode↔name layer planned above must be designed
  around this (candidate names should include both `'hyphen'` and
  `'minus'` for U+002D) rather than silently "correcting" the table.

**Interim workaround implemented (2026-10-23): Ctrl+H inserts
'hyphen'.**  The text editor command `InsertHyphen`
(`src/Sketch/Graphics/text.py`, bound to `C-h`, active during text
input) inserts the gid of the glyph named `'hyphen'` directly,
bypassing the code-45 mapping.  The glyph is encodable in every font
that has it — code 173 (0xAD) for standard-encoding fonts (the
`iso_latin_1` table has `'hyphen'` there), code 45 for fonts whose own
encoding names it so — so the usual `IsPrintableGlyph` gate accepts
it; fonts without the glyph reject the insertion (no fallback to
'minus').  Ordinary `-` typing keeps producing `'minus'` unchanged.
Pinned by `test_insert_hyphen_vs_minus` (`test/model/test_glyphs.py`).
