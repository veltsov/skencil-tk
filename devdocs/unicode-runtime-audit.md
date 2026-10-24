# Unicode at Runtime — Bug Class, .sk Encoding Decision, Audit Plan

Collects everything known about the "unicode string used at runtime"
bug class on the py2 `modernize` branch, the decision taken for the
`.sk` file format, and the (planned, **not yet executed**) proactive
tooling to find further instances before they bite.

## Background

Since commit `9f85dd9` (drop of the `intl` C extension) the gettext
shim in `Sketch/__init__.py` returns **unicode** from every `_()` call
(standard `gettext.ugettext`).  This is deliberate: stock `_tkinter`
converts it correctly, and translated messages may be non-ascii.  But
the rest of the codebase was written in the C-intl era, when `_()`
returned plain byte `str` — so every place that (a) type-checks with
`isinstance(x, str)`, (b) mixes the value with byte strings, or
(c) serializes it with `repr()`, is a latent bug.

Known instances (see also `modernize-roadmap.md`, section C, item 7):

1. **isinstance checks in the undo chain / registry** (found 2026-10-20
   via the LaTeX plugin Apply crash): `undo.py`, `document.py`,
   `registry.py` — fixed with `basestring`.
2. **bytes+unicode mixing in `util.format`** (found 2026-10-20 via the
   rotation-handle `UnicodeDecodeError` stream): byte-string converters
   in `UI/converters.py` (one contains a latin-1 `0xb0`) joined with
   unicode `_()`-templates — fixed by making `angle_format` a unicode
   literal.
3. **unicode leaks into saved `.sk` files** (found 2026-10-21 by the
   test suite, `zz.fig` round trip): `sksaver.py` wrote names with
   plain `repr()`, so gettext-derived layer/grid/guide names were saved
   as `u'...'` with `\u` escapes, which `parse_sk_line2`
   (`skreadmodule.c`) cannot parse — documents became unloadable.
   **Fixed** (see below).
4. **unicode/bytes mixing in the display and LaTeX-plugin paths**
   (found 2026-10-21 by hand with Russian layer names and LtxObj text):
   * selecting the LtxObj crashed the status bar: `selection.InfoText()`
     produces a unicode `_()`-template whose dict values are utf-8 byte
     strings (layer name `База`), and `util.format()` mixed both in a
     `%` operation → `UnicodeDecodeError`.  Sibling: `LtxObj.Info()`
     sliced the utf-8 text bytes before formatting (would split a
     multibyte character / crash on non-ascii prefixes).
   * `LtxObj.recompute` compared `self.text != self.ptext` across
     types (bytes from file vs unicode from the dialog) →
     `UnicodeWarning` and spurious recomputes.
   * `create_tex_sk` wrote the tex wrapper (unicode once the dialog's
     unicode text was substituted) to a text-mode file →
     `UnicodeEncodeError`; the subsequent transaction abort cascade
     (`AbortTransactionError`) was only a symptom of this.
   **Fixed**: `Sketch.Lib.util` gained `as_unicode(s)` (utf-8 decode of
   byte strings) and `format()` normalizes template, dict values and
   converter outputs and always returns unicode; the status-bar label
   sink `tkext.UpdatedLabel.Update` normalizes its text the same way
   (Tk labels expect unicode — this also covers e.g. Russian file
   names); `latextext.py` compares and slices via `as_unicode` and
   encodes the tex wrapper to utf-8 before writing (the wrapper declares
   `\usepackage[utf8]{inputenc}`, so utf-8 is exactly what the
   toolchain expects).
5. **the preferences file round trip** (found 2026-10-23 via the
   startup console): the preferences file serialized unicode
   `.sk`-style (utf-8 `\x`-escaped byte reprs), `execfile` read the
   values back as byte strings, and the post-hoc `normalize_mru_files`
   fix-up assignment compared bytes against unicode inside
   `ProgramDefaults.__setattr__` → `UnicodeWarning` at `config.py:112`
   on every startup with non-ascii MRU names.
   **Fixed**: the preferences file now uses plain utf-8 string
   literals (its own format; coding cookie in the header, no u prefix,
   no \x escapes — identical syntax under py3, where no conversion is
   needed) and the loader executes it into an intermediate attribute
   bag, converting all values strictly to unicode before assigning
   them to the live preferences object
   (`configutil._LoadedPreferences`/`_decode_item`).  The py2
   str/unicode handling for preferences is contained in the
   reading/writing code (`configutil`) only.

More instances of this class are expected; the py3 port changes the
semantics again (`str` unifies both, but bytes handling becomes
explicit), so the audit tooling below should also feed the port.

6. **single-letter nested submenus in the Script menu** (found
   2026-10-23 by hand): `ScriptRegistry.Add` (Scripting/registry.py)
   wraps a string `menu=` argument into a tuple only when it is
   `unicode`.  Commit `7359b47` had tightened the check from the old
   `type(menu) == StringType` (via the modernize batch's
   `isinstance(menu, basestring)`) to unicode-only, assuming menu
   paths are K1/K2 — but the shipped scripts passed *byte-string*
   literals (`menu = "TeX"`, `menu="PathUtils"`, `menu = 'Arrange'`,
   `menu = "User's Guide"`).  A byte string fell through the check and
   `for item in menu:` iterated its characters: the Script menu showed
   `Script -> T -> e -> X` and `Script -> P -> a -> t -> h ...`
   (scripts using `_()`-wrapped unicode menus, e.g. `Create Objects`,
   were unaffected).  **Fixed on the origins** per the strict unicode
   policy: all shipped scripts pass `u'...'` menu paths now, and
   `ScriptRegistry.Add` raises `TypeError` for byte-string paths or
   components (same enforcement style as `undo.check_info`).
   Guarded by `test/model/test_scripting.py` (menu tree structure and
   the TypeError rejections); an Xvfb probe of the running app asserts
   the real menu tree has no single-character submenu keys.  Audit
   note: all other `isinstance(..., unicode)` sites introduced by
   `735b947` were reviewed against this class; the remaining ones sit
   on genuine K1/K2/K3 boundaries or behind an explicit
   `decode_sk_string` (skloader `layout()`), none accepts script
   identifiers.

## The .sk fix and the encoding decision (2026-10-21)

**Fix (write side only; the input route was deliberately left
untouched):** `sksaver.py` defines

    def skrepr(s):
        if isinstance(s, unicode):
            s = s.encode('utf-8')
        return repr(s)

and all file-bound `repr()` calls (layer/guide/grid names, `layout`
format, style names, `txt`/`pt` text, `bm`/`eps` filenames, `PC`
plugin name/args/keyword values) go through it.  Non-strings pass
through unchanged.

**Format decision:** strings in `.sk` files are utf-8 encoded byte
strings written in `repr()` form — `\x` escapes for non-ascii bytes,
*no* `u` prefix.  This is what master (C-intl gettext) always wrote,
and the C parser accepts only that.

* Why the write side, not the parser: master's files must stay
  byte-comparable (the test suite byte-compares saves against master
  baselines — with the fix no baseline re-recording was needed); the
  format was defined by 25+ years of master output; `skrepr` at the
  single serialization choke point guards every current and future
  unicode source (names today, text/paste/clipboard tomorrow), while a
  parser change would only paper over the symptom.
* Why utf-8: round-trips any translation, unambiguous, and it is what
  the py3 port will use natively (`str` is unicode there; the loader
  side will need an explicit decode decision then — noted in
  `python3-porting.md` scope).
* Alternatives rejected: converting `_()` results to `str` at the
  gettext shim or at the model boundary (layer constructors) — would
  silently re-create bug class (1)/(2) elsewhere and does not guard
  text objects etc.; teaching `parse_sk_line2` the `u''` prefix —
  masks the leak and diverges the format from master.

Validation: master-saved file with Russian layer name and LtxObj text
loads, saves **byte-identical** to master's output, and a unicode name
created inside modernized skencil is saved as `\x`-escaped utf-8 and
reloads; full suite green (51/51), including the previously red
`test_save_reload_stable[zz.fig]` / `test_fixture_baseline[zz.fig]`.

**Conventions after instance 4 (2026-10-21):**

Superseded/completed 2026-10-22 by the string-kind taxonomy in
`devdocs/string-handling.md`: the `.sk` reader now decodes
user-provided strings (K2) to unicode at the boundary, display sinks
are enumerated per kind, and the remaining byte-string kinds
(text-object content, file names) have dedicated normalizers.  The
rules below remain valid; the taxonomy document is authoritative.

* *Serialization sinks* (`sksaver`) write utf-8 `\x`-escaped byte
  strings (above).
* *Display sinks* (`util.format`, `tkext.UpdatedLabel.Update`) normalize
  to unicode via `util.as_unicode` (Tk labels expect unicode; byte
  strings at runtime are utf-8).  New display code should route text
  through one of these.
* *Type-mixed comparisons* (e.g. model attributes that can come from a
  file as bytes or from a dialog as unicode) must compare via
  `as_unicode` on both sides.
* External programs: pass utf-8 bytes explicitly (encode before
  `file.write`/subprocess), and declare the encoding in the generated
  content (the LaTeX wrapper uses `inputenc utf8`).

**Toolchain note (instance 4 testing):** pstoedit 3.78 itself is fine
(`pstoedit -f sk oms.eps` produces a valid sketch).  But when the LaTeX
preamble does not select a **Type 1** cyrillic font (e.g. plain
`\usepackage[T2A]{fontenc}` without pscyr or cm-super), dvips/pdflatex
fall back to Type 3 **bitmap** fonts, which pstoedit's ghostscript
frontend cannot interpret: it prints `Error: /undefined in --get-- ...
FontName` but still writes a header-only `sk.sk` (~62 bytes), so the
plugin gets a "successfully produced" but empty document and the
recompiled object renders empty (and is then deliberately not loaded
again — `Sketch/Base/load.py: check_object` ignores empty plugins).
With a Type 1 font setup (pscyr — as in the rustext.sk fixture
preamble — or cm-super) the whole pipeline works, cyrillic included.
The LaTeX test (`test/ui/test_latex.py`) selects the pscyr preamble
when `kpsewhich pscyr.sty` finds it, tolerates the empty case
(`LTXGROUP:empty`) and asserts the full round trip when the object
renders (`LTXGROUP:ok`).

## Part 2 — proactive analysis of this bug class (PLANNED, refined 2026-10-22)

Revised after fixing instances 1–4 (commits `04b1a59`, `6d9d868`,
`961321e`).  The original three-layer plan is kept, but redesigned
from experience: the actual bug taxonomy is richer than assumed, and
the detection layers caught different subsets of it.

### Lessons from instances 1–4 (what the plan must cover)

Bug classes actually encountered, and how each was caught:

| class | instance | caught by |
|---|---|---|
| (a) `repr(unicode)` into file formats | 3 (.sk leak) | suite round trip |
| (b) unicode template `%`/concat/join with bytes | 2 (angle), 4 (status bar) | hand testing only |
| (c) type-mixed comparison of model attributes | 4 (`text != ptext`) | hand testing only (UnicodeWarning) |
| (d) slicing byte strings (splits utf-8 chars) | 4 (`Info[:20]`) | hand testing only |
| (e) writing unicode to text-mode files / external programs | 4 (`create_tex_sk`) | hand testing only |
| (f) `isinstance(x, str)` type checks | 1 (undo chain) | hand testing only |
| (g) display sinks needing unicode (Tk labels) | 4 (`UpdatedLabel`) | hand testing only |

Consequences:

* The suite's round-trip tests only guard class (a).  Classes (b)–(g)
  live in display/comparison/IO paths and need their own nets.
* The working remedies are all *sink-side normalizations* with named
  helpers — `skrepr()` (serialization), `as_unicode()` (display),
  `as_unicode` on both sides (comparisons), explicit `.encode('utf-8')`
  (files/external programs).  Source-tainting alone is insufficient:
  instance 4's comparison mixed two *non-gettext* strings (bytes from
  the file vs unicode from a Tk dialog), and Tk entry values are
  unicode in the app without ever passing through `_()`.  Tainting
  must be complemented by sink/convention checks and targeted tests.

### Layer 1 — pin the sinks in the test suite (partially done)

Done: per-fixture save/reload round trips plus the unicode-injection
tests in `test/model/test_unicode.py` (scan saved bytes for
`(?<![A-Za-z_])u['"]`), and the LaTeX UI test scanning its saved file.

Remaining:

1. Generalize the scan: one parametrized model test that, for *every*
   fixture, after load and after the standard mutation set, saves and
   scans (today only the rustext injection paths are scanned).
2. A headless display-path test set: build `(template, dict)` pairs
   via the document API (`SelectionInfoText` etc.) and run them
   through `util.format` with the real `Sketch.UI.converters` —
   reachable without a display (this is how instance 4's status-bar
   bug was reproduced headlessly).
3. Model-level comparison tests: set model string attributes from both
   bytes and unicode (layer names, LtxObj `text`/`ptext` where no
   recompute fires) and assert no `UnicodeWarning` and stable
   behavior.  A `-W error::UnicodeWarning` run mode makes these loud.

### Layer 2 — runtime unicode-taint audit mode (designed, not started)

Env-gated (`SKENCIL_UNICODE_AUDIT=1`; warn mode default, strict mode
`SKENCIL_UNICODE_AUDIT=strict` raises instead of warning):

* The gettext shim returns a `unicode` subclass `TrStr` with alarms
  on: `__repr__` (class (a) — the sksaver failure mode), `__mod__`,
  `__add__`/`__radd__` with a byte-str operand, `join` when the
  sequence mixes bytes (class (b)).
* Byte-str *sink* wrappers (same flag): `sksaver.skrepr` and
  `util.as_unicode` log when they actually convert non-ascii bytes
  (shows where bytes cross into display land).
* Install the hooks in `Sketch/__init__.py` behind the flag; collect
  alarms in a module list and dump a summary at exit (do not raise
  inside Tk callbacks in warn mode — see harness pitfalls below).
* Run the full suite plus the Xvfb smoke/screenshot payloads under
  the mode; expected first catches: other savers (`cgmsaver`,
  `aisaver`, PS/EPS/PDF headers), clipboard and dialog flows,
  `warn()`/message formatting.
* Known blind spots (covered by layers 1/3 instead): type-mixed
  comparisons where neither side is tainted (class (c)), and unicode
  entering from Tk dialogs without `_()`.

### Layer 3 — static source/sink audit (designed, calibration cases known)

A small AST-based script (`devtools/unicode_audit.py`), py2-parseable
(lib2to3 or the `ast` module), reporting per module:

* sources: `_(` / `gettext`/`ugettext`, `.decode(`, Tk
  `get()`/`getvar()` (dialog values!), config string values;
* sinks: `repr(`, `isinstance(..., str)` / `type(...) == str`,
  `%`-formatting and `+`/`join` with byte-str literals, `file.write`
  in text mode / `open(..., 'w')` of computed values, external
  process input (args/env of `subprocess`/`os.system`), slicing of
  suspected-bytes values, `==`/`!=` on attributes that can be
  bytes-or-unicode;
* convention conformance: save-file writers should use `skrepr`/
  explicit `.encode`; display text should flow through
  `util.format`/`as_unicode`.

Calibration requirement: on the current (fixed) tree the tool must
flag nothing in the fixed sites, and flag all of them when run against
the pre-fix revisions (`04b1a59^` for sksaver/util/tkext/latextext) —
a measurable precision/recall check before trusting its output.
Results go into `devdocs/python3-porting.md`; the audit doubles as the
py3 checklist (`basestring` → `str` rewrites, bytes literals in file
filters, `as_unicode`/`skrepr` call sites that simplify away in py3).

### Harness pitfalls for UI-layer unicode tests (learned in instance 4)

For whoever implements the Xvfb-based parts
(`test/ui/scripts/latex_recompile.py` is the working template):

* `--run-script` payloads must schedule work via `root.after(...)`
  inside the mainloop; a long synchronous body before the mainloop
  can deadlock in the Tk/pax layer.
* `sys.stderr` is redirected inside the app — route diagnostics to
  stdout; Tkinter callback tracebacks appear on stdout too, so
  `assert_clean_exit`'s stderr check is not sufficient: communicate
  status via stdout markers (`LTXGROUP:ok|empty|error`) and check the
  exit code.
* Modal error dialogs (`MessageBox` from plugin `write_error`, load
  warnings) hang an unattended Xvfb run — stub/patch them in the
  payload; give the runner a generous timeout and kill the whole
  process group (`testsupport.run_app` does).
* Empty plugin compounds are dropped by the loader
  (`load.py:check_object`) — round-trip assertions on a recompiled
  object only work when it actually rendered; use a status marker and
  downgrade assertions accordingly.
* External toolchain variability (font types, pscyr/cm-super
  presence) must be probed (`kpsewhich`), not assumed — see the
  toolchain note above.

### Status / suggested task breakdown

Partially executed: sink fixes + conventions + injection tests + LaTeX
UI test are in (`04b1a59`, `6d9d868`, `961321e`).  Remaining, ordered
by cost/effect, each a self-contained step with a green suite as the
gate:

1. Generalize the saved-file u-prefix scan to all fixtures +
   mutations (small; pure layer 1).
2. Headless display-path test set + UnicodeWarning-as-error run mode
   (small/medium).
3. Static audit script with calibration against pre-fix revisions
   (medium; also feeds the py3 port checklist).
4. Runtime taint audit mode + suite/Xvfb runs under it (medium; the
   exploratory part — budget time for triaging what it finds).
5. Optional, heavy: dialog-input taint probes (drive Tk entries with
   non-ASCII text via payloads) for the Tk-source blind spot.
