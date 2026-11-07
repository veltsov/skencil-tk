# Glyph-Index Text Representation

Status: implemented.  This document describes the internal
representation of text-object content and the conversion points to and
from the byte-code serialization form.

## Why

The content of `SimpleText` (and `InternalPathText`) is **not** a byte
string with one byte per glyph (the code of the glyph in the font's
256-code encoding), as it was in the original Sketch format's in-memory
form.  That representation

* hard-limits text to the 256 glyphs of the font encoding,
* makes sensible unicode conversion impossible (a byte only means
  something together with the font's encoding),
* couples the model to the external 256-code worlds (PostScript, X11
  core fonts) instead of treating them as sinks.

The representation is now an **array of glyph indices** (`array.array('I')`)
into a **process-global glyph registry** — a monotonic table of Adobe
glyph names (`'.notdef'`, `'A'`, `'eacute'`, `'fi'`, …) that grows as
fonts are loaded.  Everything a glyph needs (metrics, outline, name,
unicode mapping) is addressable through the name; the 256-code
encodings become conversion details at the boundaries.

## The glyph registry (`Sketch/Graphics/font.py`)

* One global `GlyphRegistry` instance per process (`glyph_registry`).
  Entries are never removed; indices are session-local and **never
  serialized** — files always store glyph names or font-encoding codes.
* Reserved entries, registered at import: gid 0 is `'.notdef'`,
  gid 1 is `'newline'`, gid 2 is `'carriagereturn'` (control-code names,
  see below).
* `read_afm_file` registers **every glyph of the font** (all names in
  the AFM char metrics, not just the 256 encoded ones) and builds the
  font's `FontMetric` indexed by gid (sparse; glyphs unknown to the font
  have zero metrics).

## Text objects (`Sketch/Graphics/text.py`)

* `SimpleText.text` / `InternalPathText.text`: `array.array('I')` of
  gids.  Caret positions, `len()`, slicing and undo work on the array;
  one index = one glyph.
* Constructors and `SetText` coerce their argument via
  `Font.TextGids()`:
  - `array('I')` — model form, stored as-is;
  - unicode — per character via `Sketch.Lib.glyphnames.unicode_to_glyphname`
    (latin-1 via the `encoding.iso_latin_1` table, control codes to the
    reserved names, everything else as AGL `uniXXXX` names);
  - byte string — legacy form: codes in the font's encoding, converted
    through `Font.code_to_gid`.  This is what `.sk` readers and import
    filters hand in; it is interpreted with the font of the object's
    property stack exactly as the bytes were written.
* `Text()` returns the gid array; `TextAsUnicode()` gives a display/
  interchange unicode string via glyph names (unknown names become `?`).

## Conversion sinks and sources

| Boundary | Direction | Where |
|---|---|---|
| `.sk` files (`txt()`/`pt()`) | save: gids → codes (`Font.EncodedText`, skrepr'd); load: codes → gids (constructor coercion) | `text.py` SaveToFile, `sksaver.py`, `skloader.py` |
| PostScript `show`/`Tx` | gids → codes, quoted | `psdevice.py`, `aisaver.py` |
| X11 core fonts (`DrawString`, XLFD charset range) | gids → codes | `graphics.py draw_text_on_gc` |
| Keyboard input (canvas key events) | latin-1 byte (K3 input) → gid via `Font.GidForChar` | `text.py` editor |
| Import filters (SVG/AI/WMF/CMX/XFig, `drawinput`) | bytes or unicode → gids (coercion inside the `Font` methods keeps byte callers working) | unchanged call sites |
| Display (`Info()`, SVG text) | gids → names → unicode | `glyphnames.glyphnames_to_unicode` |
| Metrics/outlines/typesetting | gids used directly (C `FontMetric` is gid-indexed) | `skfm.c`, `font.py` |

Out-of-encoding glyphs (possible in memory now, not representable in
the 256-code sinks yet) are written as code 0 (`notdef`) by
`EncodedText`/`GlyphCodes`.  A future `.sk`/PS extension can store
glyph names (`glyphshow`) instead.

## Font-metric C module (`skfm.c`)

`FontMetric` objects are indexed by gid: `CreateFontMetric(asc, desc,
bbox, italic, entries)` takes a sequence of 6-tuples
`(gid, width, llx, lly, urx, ury)` and stores a sparse, zero-filled
array sized to the highest gid.  `string_bbox`, `string_width` and
`typeset_string` accept any buffer of native `unsigned int` gids (what
`array('I')` provides) or a single int gid; `glyph_width`/`glyph_bbox`
take one gid.  Gids at or beyond the array size are treated as notdef
(zero metrics) — this covers texts that reference glyphs of fonts
loaded later than the font in question.

## Control codes

The reserved names `'newline'` (0x0A) and `'carriagereturn'` (0x0D)
exist because historical `.sk` files contain `\n`/`\r` bytes inside
quoted `txt()`/`pt()` strings (e.g. multi-line text saved by old
versions).  On load, those codes map to the reserved gids; on save they
map back, so byte-compatibility with existing files is preserved.
`InternalPathText.DrawShape` skips them, as it skipped the byte
characters before.  All other C0 control bytes map to notdef.

## Serialization form

`array.array('I')` has identical semantics everywhere.  The model-side
byte-per-glyph kind is gone; the byte form remains a *serialization*
form only, at the `.sk`/input boundary.

## Known quirk: code 45 is 'minus'

The hardcoded standard-encoding table (`Sketch/Lib/encoding.py`
`iso_latin_1`) names byte 45 **`'minus'`** — an intentional legacy
decision of the original author, kept for `.sk` compatibility.  Under
the glyph-identity representation this means a `-` typed in a
standard-encoding font resolves to the `'minus'` gid and **disappears
when the text is switched to a font whose AFM names code 45
`'hyphen'`** (which is virtually all of them).  Renaming the table
entry would change the glyph identity of existing files' `-`
characters (different widths → changed positions) and is therefore
deferred to the next `.sk` format version.  Full analysis, the
decision record and workarounds: `devdocs/text-input.md` ("Known
quirk: code 45 is named 'minus'").

## Future (not implemented)

* Full-charset access: let text reference any glyph of a font (the
  registry already carries all AFM glyph names); the
  `IsPrintableGlyph` gate currently rejects glyphs outside the font's
  256-code encoding when typed.
* PS export via `/name glyphshow` for out-of-encoding glyphs; a
  `.sk` directive carrying glyph names.
* A complete Adobe Glyph List in `glyphnames.py` for full unicode
  round-tripping beyond latin-1 (the afii alias table exists; the
  full AGL name set does not).
