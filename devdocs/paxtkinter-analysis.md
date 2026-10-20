# paxtkinter Analysis — Can It Be Dropped Under Python 2.7?

Date: 2026-10-20. Environment: Ubuntu 20.04, python2.7.18 (system),
Tcl/Tk 8.6, `tcl_platform(threaded) == 1`, X display available.

## What paxtkinter is

`src/extensions/Pax/paxtkinter.c` (2241 lines) is a copy of Python
1.5.2's `_tkinter.c` with all thread machinery compiled out:

```c
#ifdef WITH_THREAD
#define PAX_THREAD_HACK      /* keep the stdin/readline event hook */
#endif
/* turn off all other threading specific code here */
#undef WITH_THREAD
```

Consequence: `ENTER_TCL`/`LEAVE_TCL` (paxtkinter.c:212-227) expand to
nothing, so **the GIL is never released around Tcl calls** — the whole
process runs as if single-threaded. Pax's C code relies on this: it
calls Python directly from Tcl event context, which is only safe when
the GIL is guaranteed to be held.

Note: `#undef WITH_THREAD` happens *after* `#include "Python.h"`, so the
threaded `Py_BEGIN_ALLOW_THREADS` macros from `ceval.h` are still in
effect; the trick works because paxtkinter never *uses* them (they only
appear inside the `#ifdef WITH_THREAD` lock macros, which are compiled
out). `PAX_THREAD_HACK` (defined because WITH_THREAD was set when
Python.h was read) only keeps the `PyOS_InputHook` event hook for
interactive stdin; it is irrelevant for the GUI app.

## Why paxtkinter exists, and why the reason still holds in 2.7

Header comment (paxtkinter.c:33-48): Python 1.5.2's threaded `_tkinter`
introduced an internal `TclLock` that cannot be accessed from outside
`_tkinter.c`, but pax needs it to call Python from Tcl event handlers.
So pax ships its own non-threadable `_tkinter` instead.

This problem did **not** disappear in Python 2.7 (nor in py3):

- The system python2.7 is built with `WITH_THREAD`
- Pax calls Python directly from Tcl event context:
  - `PaxWidgetDisplay` (queued via `Tk_DoWhenIdle`) →
    `paxWidget_CallMethodArgs(obj, RedrawMethodIdx, ...)` (paxmodule.c:627)
  - `PaxWidgetEventProc` → Map/Resized/Destroy/Extension methods
    (paxmodule.c:560-608), scroll callbacks (:505-538)
  - the raw `call_py_method` Tcl command (paxmodule.c:732-800), fired
    for every menu/button command via `tkext.MakeMethodCommand` strings
    `('call_py_method', key, name, *args)`.

Failure modes if the app were switched to stock `_tkinter` unchanged:

1. **Crash:** during `mainloop()` the GIL is released while X events
   fire pax's C event procs; they then call `PyObject_CallObject`
   without a current thread state → `PyThreadState_Get: no current
   thread state` fatal error on the first canvas redraw.
2. **Deadlock:** adding `PyGILState_Ensure()` in pax's handlers is not
   enough: the handler runs while *our own thread holds `tcl_lock`*
   (inside `Tcl_DoOneEvent` under `ENTER_TCL`); any re-entrant
   `tk.call` (menu command → dialog → anything) hits stock
   `_tkinter`'s `ENTER_TCL` → re-acquisition of the non-recursive
   `tcl_lock` on the same thread → deadlock.
   **Correction (see `devdocs/modernize-paxtkinter.md`):** this does
   not apply when Tcl itself is threaded — py2.7's `_tkinter` frees
   `tcl_lock` at tkapp creation for threaded Tcl (source lines
   737-742), so the macros reduce to pure GIL release/acquire and
   re-entrant `tk.call` cannot deadlock. On threaded Tcl the fix is a
   simple `PyGILState_Ensure`/`Release` wrap of pax's Python-call
   sites.
3. **Nested event loops:** file dialogs (`tk_getOpenFile` runs a
   `tkwait` inner loop inside `Tkapp_Call`), `update`, `grab` all
   dispatch X events inside Tcl with the GIL released — so even driving
   `pax.do_one_event()` from a Python-level main loop would not help.

The header comment "only necessary if Python was compiled with thread
support" means it is always necessary on distro Pythons today. Not a
vanished 1.5.2 problem. **Empirically confirmed 2026-10-20:** running
the app on stock `_tkinter` (via a sitecustomize alias, validated by an
import spy) segfaults at the first `pax → Python` call — gdb backtrace
in `devdocs/modernize-paxtkinter.md`.

## Complete dependency surface (verified)

- `sys.modules['_tkinter'] = paxtkinter` — single site,
  `Sketch/__init__.py:init_ui()` (lines 186-188).
- `tkapp.interpaddr()` — used at `Sketch/__init__.py:202`,
  `UI/tkext.py:680`, `UI/tkext.py:944-946`. **Not paxtkinter-only:**
  stock py2.7 `_tkinter` also provides `interpaddr` (verified at
  runtime), and the Python code already has `hasattr(tk, 'interpaddr')`
  fallbacks that pass the tkapp object directly.
- The `TkappObject` struct cast in `paxmodule.c:145-149`
  (`{ PyObject_HEAD; Tcl_Interp *interp; }`): in stock py2.7
  `_tkinter`, `interp` is also the first member after `PyObject_HEAD`,
  so the cast works. **Verified empirically**: with the stock system
  `_tkinter`, `pax.create_tcl_commands(tkapp)` and
  `pax.name_to_window('.', tkapp)` both succeed.
- `tk.utf8_to_latin1` / `utf8_to_system` / `system_to_utf8` —
  paxtkinter-only helpers (thin wrappers over
  `Tcl_UtfToExternalDString` with iso8859-1 / system encoding), used at
  `UI/tkext.py:711,717` (file dialog filenames),
  `UI/canvas.py:567` (key events; **already has an
  `except AttributeError: pass` fallback** for "Python's own
  _tkinter"), `Plugins/Objects/multilinetext.py:244`. All replaceable
  with pure Python (`s.decode('utf-8').encode('latin-1')`, etc.).
- `wantobjects` behavioral difference: py2.7 `Tkinter.py` passes
  `wantobjects=1` to `_tkinter.create()` (Tkinter.py:49,1828); stock
  `_tkinter` then returns typed results (ints/tuples) from `tk.call`,
  while paxtkinter's `wantobjects` is a deliberate no-op ("Yet another
  sketch specific hack... Tkinter calls the wantobjects method",
  paxtkinter.c:1755-1766) and always returns strings. Mitigation: call
  `root.tk.wantobjects(0)` once at startup (stock `_tkinter` supports
  it as a setter) or audit call-result typing.
- `pax` does **not** link against `paxtkinter` (no shared symbols); the
  only coupling is the struct cast above.

  (verified in the multiarch pyconfig.h).
- Stock py2.7 `_tkinter` has the same lock design: `Tkapp_MainLoop`
  wraps each `Tcl_DoOneEvent` in `ENTER_TCL/LEAVE_TCL` — **GIL
  released, internal `tcl_lock` held** while Tcl dispatches events.
## Viable redesign (Option C): drop paxtkinter, use stock _tkinter

The supported, deadlock-free pattern already exists in `_tkinter`:
commands registered via `tk.createcommand()` are dispatched by
`Tkinter_CommandCmd`, which does `ENTER_PYTHON` (releases `tcl_lock`,
acquires the GIL) before running Python — the same mechanism as normal
Tk `-command` scripts. Therefore pax's event-context callbacks must be
marshaled through a `createcommand`-registered dispatcher instead of
calling Python directly.

**Simplified after the pre-flight experiment** (see
`devdocs/modernize-paxtkinter.md`): with threaded Tcl there is no
`tcl_lock` at all, so the simple fix works — wrap pax's Python-call
choke points (`paxWidget_CallMethodArgs` at paxmodule.c:104 and
`call_py_method` at :791) with `PyGILState_Ensure()`/`Release()`.
The `createcommand`-dispatcher variant below remains a fallback if
the `PyGILState` approach shows reentrancy problems.

Python side:
1. `Sketch/__init__.py:init_ui()` — remove the paxtkinter hack.
2. `UI/tkext.py:InitFromTkapp` — register the dispatcher via
   `tk.createcommand('call_py_method', pax.dispatch)`; keep
   `pax.create_tcl_commands(tk)` only for the `paxwidget` widget
   command (verified to work with the stock tkapp object); add a
   Python-side dispatcher (registry lookup + per-method argument
   conversion for `ResizedMethod`/`ExtensionEvent` ints).
3. Replace `utf8_*` helper uses with pure-Python helpers in tkext.py.
4. `UI/skapp.py` — after root creation, set `wantobjects(0)`.
5. `setup.py` — remove the paxtkinter Extension.

C side (`paxmodule.c`, ~150-250 lines):
- In `PaxWidgetDisplay` and `PaxWidgetEventProc` only, replace
  `paxWidget_CallMethod*` with `Tcl_Eval(interp,
  "call_py_method <key> <method> <args...>")`.
- For `RedrawMethod(region)`: at event time stash the `PaxRegion` in a
  C-side pending slot (or the existing `object_registry` under a
  generated string key) and pass the key; the dispatcher fetches it
  via a new `pax.take_pending_object(key)`.
- `InitTkWinObject`/`InitTkBorder` calls from `PaxWidgetConfigure`
  happen inside `tk.call` (GIL held) — can stay direct.

Alternative variant: move event wiring to Python entirely — bind
`<Expose>`/`<Configure>` through Tkinter (GIL-safe by construction),
expose `pax.add_expose(tkwin, ...)` / `pax.take_exposed_region(tkwin)`
for the C-side region accumulation, schedule redraws with
`after_idle`. Larger behavioral change; the `Tcl_Eval` variant
preserves current redraw timing exactly.

## Other options considered

- **Option B**: keep paxtkinter but regenerate it from the actual
  py2.7.18 `_tkinter.c` + ~20-line patch (empty lock macros, no-op
  `wantobjects`, keep `interpaddr`/utf8 helpers). Removes 1.5.2 drift,
  ~half a day, doesn't remove the module.
- **Option D**: drop pax rendering entirely (pure Tk Canvas / ImageTk).
  Weeks of UI rewrite; not now.

## Payoff for the Python 3 port

After the redesign, `paxmodule.c`'s coupling to `_tkinter` shrinks to:
the `interp`-first struct cast (same layout in py3), the `paxwidget`
command invoked via `tk.call`, and a `createcommand`-registered
dispatcher — all stable across py2.7 → py3.x. The 2241-line
`paxtkinter.c` disappears from the py3 porting list entirely, and py3's
`_tkinter` (same lock architecture) is then used the supported way.

## Pre-flight probe

Executed 2026-10-20 — see `devdocs/modernize-paxtkinter.md` for the
full procedure, results, gdb backtrace and the corrected conclusions.
Short version: the probe (run under Xvfb with a sitecustomize aliasing
*both* `paxtkinter` and `Sketch.paxtkinter` to the stock `_tkinter`,
validated by an `__import__` spy) **segfaulted at the first
`pax → Python` call**, confirming the GIL analysis; the deadlock
concern was disproven for threaded Tcl, which makes the actual fix a
simple `PyGILState_Ensure`/`Release` wrap.


