# Text Input — the Unicode Keyboard Input Path

Status: implemented.  This document describes how key events reach the
text editor, and lists the open follow-up items.  See also
`devdocs/glyph-text.md` (the glyph-index representation this builds
upon).

## The input path (`src/Sketch/UI/canvas.py`)

`canvas.KeyPressEvent`:

* `char = as_unicode(event.char)` — Tk returns `str` under py3;
  `as_unicode` normalizes stray bytes.  Control characters
  (`ord(char) < 32`) are blanked.
* Keymap strokes keep using the character form (`mod + char`, then
  `mod + keysym` as fallback), so existing bindings are unchanged.
* **Fallback for text editing:** a printable character that matches no
  keymap entry (e.g. non-latin-1 keyboard input — Cyrillic, Greek, …)
  is inserted into the text object being edited through the same
  `CallObjectMethod(CommonText, '', 'InsertCharacter', char)` path the
  keymap uses, so transactions, undo and the redraw queue are handled
  uniformly.

## Glyph-name resolution (`Sketch/Lib/glyphnames.py`, `Sketch/Graphics/font.py`)

* `InsertCharacter(char)` accepts a single unicode character: the gid
  comes from `font.GidForUnicode(char)`; insertion is gated by
  `IsPrintableGlyph` (a glyph the font cannot encode is rejected —
  same as unencodable latin-1 characters were; no invisible notdef
  spam).
* `unicode_to_glyphnames(char)` returns candidate Adobe glyph names,
  most canonical first: the encoding-table name for latin-1 (with the
  `minus`/`hyphen` pair for code 45, see the quirk below), else
  `'uniXXXX'` plus the legacy **afii** aliases (Cyrillic etc., from
  the Adobe Glyph List 2.0 as shipped in ghostscript's `gs_agl.ps`,
  since AGLFN 1.7 dropped the afii names).
* `GidForUnicode` tries each candidate against the font's own glyph
  name set first, so an afii-named font (URW Cyrillic, pscyr,
  cm-super/lh) resolves `afii10086` while an OpenType-named one
  resolves `uni0444`; if none matches, the canonical name is
  registered (and the insertion is then rejected by
  `IsPrintableGlyph`).
* The reverse mapping `glyphname_to_unicode` includes the afii table,
  so `TextAsUnicode()` displays afii-named glyphs correctly.

Tests: `test/model/test_glyphs.py` (Cyrillic candidate mapping,
reverse mapping, latin-1 insertion, rejection for fonts lacking the
glyph, synthetic afii-named font resolution, the typing path via
`CallObjectMethod`).

## Scope limits / open items

* No `.sk`/serialization change; glyphs absent from the font remain
  rejected — full-charset insertion (typing glyphs the font cannot
  encode) stays a future item (see `devdocs/glyph-text.md`, Future).
* The multilinetext dialog input stays latin-1 (`utf8_to_latin1` in
  `Plugins/Objects/Lib/multilinetext/`); it would crash the same way
  for non-latin-1 input — a separate follow-up decision, since that
  plugin's text is stored as K3 bytes in the file format (see
  `devdocs/string-handling.md`).
* X11 core-font drawing and PS export of typed non-latin-1 glyphs work
  only if the glyph is in the font's 256-code encoding (the
  `IsPrintableGlyph` gate guarantees this).
* `utf8_to_latin1` remains in `tkext` for the multilinetext dialog
  (that plugin's byte-level text is a separate, format-visible
  contract).

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

Under the glyph-identity representation this means a `-` typed in a
standard-encoding font resolves to the `'minus'` gid and **disappears
when the text is switched to a font whose AFM names code 45
`'hyphen'`** (which is virtually all of them).  Renaming the table
entry would change the glyph identity of existing files' `-`
characters (different widths → changed positions) and is therefore
deferred to the next `.sk` format version.  `unicode_to_glyphnames`
mitigates the typing side by trying both names for code 45.
