# String Handling — Origins, Kinds, Conventions

This document is the contract for string handling in skencil-tk: every
string's origin is statically known, and its type follows from the
origin, so no defensive type checks or conversions are scattered over
the code.  It supersedes the piecemeal fixes described in
`unicode-runtime-audit.md` (which remain in place) and feeds the
Python 3 port (`python3-porting.md`).

## The string kinds

| Kind | Type in the model | Origin | Conversion at the boundary |
|------|-------------------|--------|----------------------------|
| K1 — UI/display strings | `unicode` | `_()` (gettext shim), Tk widget output | pass to Tk as-is |
| K2 — user-provided names/parameters **and file names** | `unicode` | Tk widget input (dialogs, entries); Tk file dialogs (`as_unicode`); `sys.argv` (utf-8 decode); the `.sk` reader decodes on read; `os.listdir` (given a unicode dir) | serialize via `sksaver.skrepr` (utf-8 `\x`-escaped repr form); pass to `open`/`os.*`/`subprocess` as unicode (py2 encodes via the filesystem encoding — utf-8 on the assumed systems); never compare with K3 bytes |
| K3 — text-object content | `array.array('I')` of glyph ids into the global glyph registry (see `devdocs/glyph-text.md`; **redefined 2026-10-22**, formerly font-encoding byte strings) | canvas `KeyPressEvent` (single byte char via `utf8_to_latin1`), `txt()`/`pt()` in `.sk` (font-encoding codes), import filters (bytes or unicode) | coercion via `Font.TextGids` at construction/`SetText` (byte form interpreted with the font's encoding); serialization via `Font.EncodedText` then `skrepr`; display via glyph names → unicode (`SimpleText.TextAsUnicode`) |
| K5 — internal identifiers | ascii content, either type | plugin class names, font PostScript names, keysyms, X resource names | py2's implicit ascii coercion makes them type-agnostic; no conversions |
| K6 — external output | `bytes`, target encoding | savers, generated files, subprocess input | explicit `.encode(...)` at the boundary (e.g. `psmisc.quote_ps_string` for PS headers) |

Note (2026-10-22): file names were briefly a separate byte-string kind
(K4, utf-8); that was reverted — the byte representation leaked into
every display sink (`Info()`s, message templates, titles) and required
per-site normalization, while py2's os layer accepts unicode file
names natively.  All names are unicode now; only the *assumption* that
the filesystem encoding is utf-8 remains (see below).

## Origin paths (verified sites)

### Sources of unicode (K1/K2)
* All Tk widget input: entry/text/listbox/option-menu values and Tk
  variables (`layerdlg.GetName`, `styledlg.var_style_name`,
  `layoutdlg.var_format_name`, `plugindlg` parameters, `printdlg`,
  script dialogs, `multilinetext`'s TextEditor *before* its explicit
  conversion, `fontdlg` lists).
* `_()` / `ugettext` — including plugin metadata translated by
  `Sketch/Base/plugins.py`.
* `tk_getOpenFile`/`tk_getSaveFile`: stock `_tkinter` returns either
  ascii byte strings or unicode (it converts any result containing
  non-ascii characters); `tkext.GetOpen/SaveFilename` normalize both
  to unicode via `util.as_unicode` — the single filename boundary.
* `sys.argv` (document filename, `--run-script`, CLI tools): decoded
  from utf-8 leniently (`util.as_display_name`) at the entry points
  (`main.py`, `sk2ps`, `skconvert.py`, `skshow.py`).
* `os.listdir`: called with a unicode directory (`plugins.py`,
  `font.py`, `curvetext.py`) so the entries come back unicode;
  `SKETCH_FONTPATH`/`gethome()` decoded in `configutil.py`/`util.py`.
* The filesystem name representation is **assumed to be utf-8**
  (modern Linux systems; Tcl itself also speaks utf-8 internally), so
  the utf-8 decode at the byte origins is lossless on them, and py2's
  implicit unicode-to-fsencoding conversion at `open`/`os.*` is a
  no-op.  No `sys.getfilesystemencoding()` lookups; a file name in a
  foreign encoding (e.g. from a non-utf-8 locale's command line)
  degrades to a clear load error instead of silent corruption.

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
* Import filters: SVG (SAX unicode), AI/WMF/CMX/XFig (bytes) — text
  content (K3); the byte/unicode forms are coerced to glyph ids when
  the `SimpleText` is constructed (`Font.TextGids`).
* The preferences file — written by `configutil.save_repr` as plain
  string literals containing the utf-8 characters directly (only `\`,
  `'` and C0 controls escaped; the header declares
  `-*- coding: utf-8 -*-`; no `u'...'` prefix, no `\x` byte escapes).
  The syntax is identical under python3, where no conversion is
  needed at all.  On load (python2) the file is executed into an
  intermediate attribute bag (`configutil._LoadedPreferences`) and
  `_decode_item` converts the byte strings strictly to unicode (K2)
  before anything is assigned to the live `preferences` object;
  undecodable values are dropped with a console warning (undecodable
  list entries are skipped, `image_dir` is reset to the current
  directory), so the model only ever sees K2 unicode.

## Sink rules

1. **Tk display sinks** (labels, titles, menus, message boxes) need
   unicode.  Names and file names (K2) arrive as unicode everywhere,
   so no normalization is needed for them; K3 text is displayed via
   glyph names → unicode (`_display_text`/`SimpleText.TextAsUnicode`;
   see `SimpleText.Info`, `PathText.Info`, `InternalPathText.Info`).
   `util.as_latin1_text` remains as a lenient display helper for stray
   byte strings.  `util.format` and
   `tkext.UpdatedLabel.Update` keep their `as_unicode` normalization as
   a safety net for stray bytes; `as_display_name` remains for lenient
   display of the rare byte name (e.g. from a foreign-locale argv).
2. **Serialization sinks** write K2 as utf-8 `\x`-escaped repr
   literals via `sksaver.skrepr`; K3 is first converted back to the
   font-encoding byte form via `Font.EncodedText` (in the text
   objects' `SaveToFile`) and likewise passed through `skrepr`.  No
   `repr()` of K2 anywhere else.
3. **External sinks**: `open`/`os.*`/`subprocess` take K2 unicode file
   names directly (py2 encodes via the filesystem encoding — utf-8 on
   the assumed systems); K6 content (PS/PDF/generated files, embedded
   names in byte streams) is encoded explicitly, e.g.
   `psmisc.quote_ps_string` encodes non-ascii to utf-8 before quoting.
4. **Comparisons/dict lookups** on K2 values happen in unicode on both
   sides (styles dict, `style_names` lists, undo labels).  K5 values
   may be either type (ascii).

## Type-check policy

`isinstance(x, str)`/`basestring` checks are allowed only where the
checked value is a K5 identifier or where a genuine dispatch between
kinds is needed (e.g. undo info: string label vs callable; style name
vs style object — those use `unicode` since K2 is unicode).
"Filename vs file object" boundary checks use `(str, unicode)`
(`load.py:load_drawing`, `skloader.py:Load`, `image.py:load_image`,
`psdevice.py`).  Anything else is a symptom of an unclear origin — fix
the origin, not the check.

Undo/transaction labels (the text shown by Edit→Undo, built from
command menu names and `BeginTransaction` arguments) are K1 unicode;
`undo.check_info` enforces this (a byte-string label raises
`UndoTypeError` rather than being tolerated — the origins must be
fixed instead; see `devdocs/testing.md`, UndoTypeError finding).

Scripting menu paths (the `menu=` argument of the script commands,
used both as submenu titles and as the tree key) are K1 unicode as
well.  `ScriptRegistry.Add` rejects byte-string paths and byte-string
components with a `TypeError` (a byte string would be iterated
character by character, producing single-letter nested submenus; see
`devdocs/unicode-runtime-audit.md`, instance 6).  The shipped scripts
pass `u'...'` literals.  (2026-10-26: the division-audit interactive
session surfaced 23 straggler plain-str `AddFunction` titles --
Script -> Average Points crashed in `check_info` for exactly this
reason; all shipped titles are `u'...'` literals now, see
`divaudit-findings.md`.)

## Validation and enforcement

* The suite guards the on-disk format: `test/model/test_unicode.py`
  (no `u'...'` prefixes, round-trip stability, unicode types in the
  model after load).
* The static audit tool `devtools/unicode_audit.py` (see
  `unicode-runtime-audit.md`, Layer 3) checks these conventions and
  doubles as the py3 port checklist.

## Python 3 port impact (summary)

* K1/K2/K5 collapse into `str`; K3 is `array.array('I')`, whose
  semantics are identical on py2 and py3 — with file names unicode in
  the model, the model described here is already the py3
  shape; py2's implicit filename conversions at `open`/`os.*` simply
  vanish and no `os.fsdecode`/`fsencode` is needed in the model.
  The glyph-index representation was introduced precisely to remove
  the last bytes-with-encoding kind from the model (see
  `devdocs/glyph-text.md`).
* `decode_sk_string` keeps its call sites (or is deleted if
  `skreadmodule.c` is ported to return `str`); the site list above is
  the complete work list.
* The removed/`unicode`-ized checks are one fewer `basestring` rewrite
  each, and comparisons no longer rely on py2's implicit ascii
  coercion.
* Port-time rewrites stay localized: `skrepr` (py3 `repr` of bytes is
  `b'...'`).  In py3 the K4 helpers collapse into
  `os.fsdecode`/`fsencode` (surrogateescape); on a utf-8 system the
  py2 utf-8 assumption and the py3 default agree.
