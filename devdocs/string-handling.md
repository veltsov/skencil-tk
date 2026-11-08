# String Handling — Kinds, Origins, Conventions

This document is the contract for string handling in skencil-tk: every
string's origin is statically known, and its type follows from the
origin, so no defensive type checks or conversions are scattered over
the code.  All text-bearing model types are `str` (unicode); the only
byte kinds are text-object content in its serialization form and
external output.

## The string kinds

| Kind | Type | Origin | Conversion at the boundary |
|------|------|--------|----------------------------|
| K1 — UI/display strings | `str` | `_()` (gettext shim), Tk widget output | pass to Tk as-is |
| K2 — user-provided names/parameters **and file names** | `str` | Tk widget input (dialogs, entries); Tk file dialogs (`as_unicode`); `sys.argv` (lenient `as_display_name`); the `.sk` reader decodes on read; `os.listdir` | serialize via `sksaver.skrepr` (utf-8 `\x`-escaped repr form); pass to `open`/`os.*`/`subprocess` directly; never compare with K3 bytes |
| K3 — text-object content | `array.array('I')` of glyph ids into the global glyph registry (see `devdocs/glyph-text.md`) | canvas `KeyPressEvent` (unicode char), `txt()`/`pt()` in `.sk` (font-encoding codes), import filters (bytes or unicode) | coercion via `Font.TextGids` at construction/`SetText` (byte form interpreted with the font's encoding); serialization via `Font.EncodedText` then `skrepr`; display via glyph names → unicode (`SimpleText.TextAsUnicode`) |
| K5 — internal identifiers | ascii `str` | plugin class names, font PostScript names, keysyms, X resource names | no conversions |
| K6 — external output | `bytes`, target encoding | savers, generated files, subprocess input | explicit `.encode(...)` at the boundary (e.g. `psmisc.quote_ps_string` for PS headers) |

## Origin paths

### Sources of K1/K2 unicode
* All Tk widget input: entry/text/listbox/option-menu values and Tk
  variables (`layerdlg.GetName`, `styledlg.var_style_name`,
  `layoutdlg.var_format_name`, `plugindlg` parameters, `printdlg`,
  script dialogs, `fontdlg` lists).  Tk returns `str` under py3;
  `util.as_unicode` normalizes stray bytes where legacy callers may
  still hand them in (e.g. `canvas.KeyPressEvent`).
* `_()` — including plugin metadata translated by
  `Sketch/Base/plugins.py`.
* `tk_getOpenFile`/`tk_getSaveFile`: `tkext.GetOpen/SaveFilename`
  normalize the result via `util.as_unicode` — the single filename
  boundary.
* `sys.argv` (document filename, `--run-script`, CLI tools): decoded
  leniently (`util.as_display_name`) at the entry points
  (`main.py`, `sk2ps`, `skconvert`, `skshow.py`).
* `os.listdir` (`plugins.py`, `font.py`, `curvetext.py`);
  `SKETCH_FONTPATH`/`gethome()` decoded in `configutil.py`/`util.py`.
* The filesystem name representation is assumed to be utf-8 (modern
  Linux systems; Tcl itself also speaks utf-8 internally).  A file
  name in a foreign encoding (e.g. from a non-utf-8 locale's command
  line) degrades to a clear load error instead of silent corruption.

### The `.sk` reader boundary (K2 → unicode)
`parse_sk_line2` (`extensions/Modules/skreadmodule.c`) yields byte
strings only.  `Plugins/Filters/skloader.py` and
`Sketch/Base/load.py` decode user-provided strings immediately on
read, via `Sketch.Lib.util.decode_sk_string` (utf-8, strict):
* `layer(...)`/`guidelayer(...)`/`grid(...)` names,
* `dstyle(...)`/`use_style(...)` style names,
* `layout(...)` paper-format name,
* `bm(...)`/`eps(...)` file names,
* `PC(...)` class names (ascii identifiers, decoded for uniformity
  with the plugin registry keys).

Deliberately **not** decoded (they stay byte strings at the reader):
* `txt()`/`pt()` text — K3, font-encoding codes; the text objects
  convert them to glyph ids at construction (`Font.TextGids`, see
  `devdocs/glyph-text.md`);
* `PC(...)` arguments in general — the *plugin object* owns the kind
  of its text parameters (below).

### Plugin objects own the kind of their text parameters
`PC(...)` string arguments cannot be blanket-decoded by the reader
because plugin objects use their text parameters in different ways:
* `latextext.LtxObj.text` — user parameter text (K2): normalized to
  unicode in `__init__` (`as_unicode`), compared directly, encoded to
  utf-8 only when written to the LaTeX toolchain (the wrapper declares
  `\usepackage[utf8]{inputenc}`).
* `lcdtext.LCDText.text` — user parameter text (K2): normalized to
  unicode in `__init__`; rendering uses its own segment definitions,
  not the font encoding.
* `multilinetext.MultilineText.text` — **text content** (K3): the
  dialog explicitly converts to latin-1 bytes (`utf8_to_latin1`)
  because it feeds `SimpleText` children.

A new plugin object must classify its string parameters into K2 or K3
and normalize at construction.

### Sources of byte strings (K3/K5/K6)
* Import filters: SVG (SAX unicode), WMF/XFig (bytes) — text
  content (K3); the byte/unicode forms are coerced to glyph ids when
  the `SimpleText` is constructed (`Font.TextGids`).
* The preferences file — written by `configutil.save_repr` as plain
  string literals containing the utf-8 characters directly (only `\`,
  `'` and C0 controls escaped; the header declares
  `-*- coding: utf-8 -*-`; no `\x` byte escapes).  On load it is
  exec'd directly (py3 decodes the literals natively); the loader
  drops undecodable values with a console warning, so the model only
  ever sees K2 `str`.

## Sink rules

1. **Tk display sinks** (labels, titles, menus, message boxes) need
   unicode.  Names and file names (K2) are `str` everywhere, so no
   normalization is needed for them; K3 text is displayed via
   glyph names → unicode (`SimpleText.TextAsUnicode`; see
   `SimpleText.Info`, `PathText.Info`, `InternalPathText.Info`).
   `util.format` and `tkext.UpdatedLabel.Update` keep their
   `as_unicode` normalization as a safety net for stray bytes;
   `as_display_name` remains for lenient display of the rare byte name
   (e.g. from a foreign-locale argv).
2. **Serialization sinks** write K2 as utf-8 `\x`-escaped repr
   literals via `sksaver.skrepr`; K3 is first converted back to the
   font-encoding byte form via `Font.EncodedText` (in the text
   objects' `SaveToFile`) and likewise passed through `skrepr`.  No
   `repr()` of K2 anywhere else.
3. **External sinks**: `open`/`os.*`/`subprocess` take K2 `str` file
   names directly; K6 content (PS/PDF/generated files, embedded
   names in byte streams) is encoded explicitly, e.g.
   `psmisc.quote_ps_string` encodes non-ascii to utf-8 before quoting.
4. **Comparisons/dict lookups** on K2 values happen in `str` on both
   sides (styles dict, `style_names` lists, undo labels).

## Type-check policy

`isinstance(x, str)` checks are allowed only where the checked value
is a K5 identifier or where a genuine dispatch between kinds is needed
(e.g. undo info: string label vs callable; style name vs style object).
"Filename vs file object" boundary checks use `str`
(`load.py:load_drawing`, `skloader.py:Load`, `image.py:load_image`,
`psdevice.py`).  Anything else is a symptom of an unclear origin — fix
the origin, not the check.

Undo/transaction labels (the text shown by Edit→Undo, built from
command menu names and `BeginTransaction` arguments) are K1 `str`;
`undo.check_info` enforces this (a byte-string label raises
`UndoTypeError` rather than being tolerated — the origins must be
fixed instead).

Scripting menu paths (the `menu=` argument of the script commands,
used both as submenu titles and as the tree key) are K1 `str` as
well.  `ScriptRegistry.Add` rejects non-str paths and components with
a `TypeError` (a byte string would be iterated character by
character, producing single-letter nested submenus).

## Enforcement

* `test/model/test_unicode.py` guards the on-disk format: no `u'...'`
  prefixes, round-trip stability, unicode types in the model after
  load; it also injects unicode into object properties (layer name,
  LtxObj text parameter) and re-reads the saved file.
* `test/model/test_glyphs.py` pins `test_command_menu_names_are_unicode`
  (the undo-label rule).
