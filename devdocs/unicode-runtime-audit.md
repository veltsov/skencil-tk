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

More instances of this class are expected; the py3 port changes the
semantics again (`str` unifies both, but bytes handling becomes
explicit), so the audit tooling below should also feed the port.

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

## Part 2 — proactive analysis of this bug class (PLANNED, NOT EXECUTED)

Three complementary layers, ordered cheap → thorough:

1. **Pin the sink in the test suite (regression net).**  For every
   fixture — after load and after the standard mutations — save the
   `.sk` and scan the bytes for a `u'`/`u"` string prefix
   (`(?<![A-Za-z_])u['"]`), plus assert reload succeeds.  Catches any
   future unicode→`.sk` leak regardless of which `_()` site grows
   next; no knowledge of sources required.  (Layer-1 model test, no
   display needed.)

2. **Runtime unicode-taint audit mode (finds unknown sinks app-wide).**
   Env-gated (e.g. `SKENCIL_UNICODE_AUDIT=1`, settable via
   `test/run_tests.sh`): make the gettext shim return a `unicode`
   *subclass* whose `__repr__` raises/warns (exactly the sksaver
   failure mode) and whose `__add__`/`__mod__`/`join` detect mixing
   with byte strings containing non-ascii (bug class (2), the `0xb0`
   incident).  Run the suite + Xvfb smoke tests under this mode to
   flush out sibling leaks: other savers (`cgmsaver`, `aisaver`,
   PS/EPS headers), clipboard/dialog flows, `warn()`/format paths.
   Zero cost when the flag is off.

3. **Static source/sink audit (one-time report + py3 checklist).**
   A small AST-based script (e.g. `devtools/unicode_audit.py`) that,
   per module, cross-references
   *sources* (`_(`, `gettext`/`ugettext`, `.decode(`, Tk `get()` /
   `getvar`) with *byte-str sinks* (`repr(`, `isinstance(..., str)` /
   `type(...) == str`, computed values written to files, `%`/`+`
   concatenation into byte literals) and ranks files containing both.
   Results go into `devdocs/python3-porting.md`; the audit doubles as
   the py3 checklist (`basestring` → `str` rewrite sites, bytes
   literals in file filters).

Status: decision to fix on the write side made and implemented; the
tooling above is agreed in principle, not started.  Revisit after the
next modernize/py3 batches.
