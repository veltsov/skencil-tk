# Dropping paxtkinter — Pre-flight Experiment Record

Date: 2026-10-20, branch `modernize`. Companion to
`devdocs/paxtkinter-analysis.md`. Test rig: Xvfb (user-installed for this
purpose), all test files in `/tmp/sk-preflight/`, no repo files touched.

## Result in one line

**The analysis was empirically confirmed: with stock `_tkinter`, the app
segfaults immediately at the first `pax → Python` call.** Additionally,
two facts of the original analysis had to be corrected (see below), and
they make the actual fix *simpler* than planned.

## Procedure

1. **Aliasing sitecustomize** (`/tmp/sk-preflight/sitecustomize.py`,
   injected via `PYTHONPATH`): makes `Sketch.init_ui()`'s
   `import paxtkinter` resolve to the stock `_tkinter` module, so
   `sys.modules['_tkinter'] = paxtkinter` becomes a no-op — the app then
   runs entirely on the stock system `_tkinter` without any repo change.

   **Critical subtlety discovered:** aliasing `sys.modules['paxtkinter']`
   alone is NOT enough. `init_ui()` lives in the `Sketch` package whose
   `__path__` includes `Sketch/Modules/`, so the statement
   `import paxtkinter` is a Python 2 **implicit relative import** that
   resolves as `Sketch.paxtkinter` (verified with `python2 -v`:
   `import Sketch.paxtkinter # dynamically loaded from .../paxtkinter.so`),
   bypassing the `sys.modules['paxtkinter']` entry entirely. The alias
   must be set under *both* names:
   `sys.modules['paxtkinter'] = _tkinter` AND
   `sys.modules['Sketch.paxtkinter'] = _tkinter`.
   (First probe run without this was invalid — proof via an
   `__import__` spy showed `sys.modules['_tkinter']` back on
   paxtkinter.so; the app then ran normally, as in the control.)

2. **Proof instrumentation:** an `__import__` spy in sitecustomize
   logged (to an unbuffered file, since stdout is block-buffered and
   lost when `timeout` kills the process) that
   `sys.modules['_tkinter']` was the stock
   `/usr/lib/python2.7/lib-dynload/_tkinter.so` at every import check.

3. **Stress script** (`--run-script /tmp/sk-preflight/stress.py`):
   executed by `mainwindow.py:594` (`execfile`) before the mainloop;
   scheduled 100 `after()`-driven hammers doing
   `canvas.configure(w+3, h)` (real X ConfigureNotify → pax event procs)
   + `root.update_idletasks()` + `root.update()` (nested Tcl event loops
   → `Tk_DoWhenIdle` → `PaxWidgetDisplay`).

## Runs

| Run | Config | Outcome |
|---|---|---|
| control | paxtkinter (as built) | ran 15–20 s under Xvfb, 100/100 hammers completed, zero errors, window mapped 766×470 |
| probe 1 | alias on `paxtkinter` only | invalid: implicit relative import re-loaded `Sketch.paxtkinter`; app behaved like control |
| probe 2 (gdb) | alias on both names | **SIGSEGV (exit 139)** during startup, before any stress hammer, at the first canvas widget creation |
## Crash backtrace (probe 2, gdb)

```
Program received signal SIGSEGV, Segmentation fault.
#0 PyEval_CallObjectWithKeywords ()
#1 paxWidget_CallMethodArgs (obj=..., method_idx=4, args=...)
      at src/extensions/Pax/paxmodule.c:104
#2 PaxWidgetConfigure (interp=..., paxwidget=..., ...)
      at src/extensions/Pax/paxmodule.c:399     (InitTkBorder callback)
#3 paxwidget_cmd (...) at src/extensions/Pax/paxmodule.c:327
#4 TclInvokeStringCommand () from libtcl8.6.so
#5 TclNRRunCallbacks () from libtcl8.6.so
#6 _tkinter.so frame        (inside Tkapp_Call: ENTER_TCL — GIL released)
#7 PyEval_EvalFrameEx ()    (Python: Widget.__init__ → tk.call('paxwidget',...))
```

Interpretation: the hazard is **not limited to the event loop**. Every
`pax → Python` call made from inside a `tk.call()` or a Tcl event
dispatch runs without the GIL under stock `_tkinter`, because stock
`_tkinter` releases the GIL around every Tcl invocation
(`ENTER_TCL`). The very first `PyWidget.__init__ → tk.call('paxwidget',
...) → PaxWidgetConfigure → InitTkBorder` already segfaults.

## Corrections to the original analysis (verified in CPython 2.7 source)

From `Modules/_tkinter.c` of CPython 2.7 (fetched to
`/tmp/_tkinter_2_7.c`):

1. **`tcl_lock` does not exist for threaded Tcl.** `Tkapp_New()`
   (lines 737-742) frees `tcl_lock` and sets it to NULL when
   `tcl_platform(threaded)` is set (our case: Tcl 8.6 threaded). All
   lock macros guard with `if(tcl_lock)`. ⇒ **the previously predicted
   deadlock (re-entrant `tk.call` from a GIL-acquired callback) cannot
   happen in this configuration.**
2. `ENTER_TCL` still releases the GIL (`Py_BEGIN_ALLOW_THREADS`) even
   with `tcl_lock == NULL` — the crash mechanism stands.
3. Commands registered via `tk.createcommand()` are dispatched through
   `Tkinter_CommandCmd` with `ENTER_PYTHON` (GIL re-acquired) — the
   supported callback path.

## Consequence: the fix is simpler than planned

Since there is no `tcl_lock` to deadlock on (threaded Tcl), the
redesign does **not** need the `Tcl_Eval`/string-marshaling dispatcher.
It suffices to make every pax → Python call site acquire the GIL:

- Wrap all `paxWidget_CallMethod*` call sites (paxmodule.c:104 is the
  single choke point — all callbacks funnel through it) and
  `call_py_method` (paxmodule.c:791) with
  `PyGILState_Ensure()` / `PyGILState_Release()`.
- `PyGILState_Ensure` from the same thread that released the GIL inside
  `_tkinter`'s `ENTER_TCL` simply does `PyEval_RestoreThread` of this
  thread's saved state — exactly the inverse of `_tkinter`'s release.
- Keep the raw `Tcl_CreateCommand('call_py_method', ...)` as is.
- Plus the previously identified items: remove the
  `sys.modules['_tkinter']` hack (Sketch/__init__.py:186-188), replace
  the 4 `utf8_*` helper uses with pure-Python helpers, set
  `root.tk.wantobjects(0)` after root creation (or audit result
  typing), drop the paxtkinter Extension from setup.py.

**Configuration caveat:** the no-deadlock property depends on
threaded Tcl (`tcl_platform(threaded)` set, ⇒ `tcl_lock == NULL`). With
a non-threaded Tcl build, `tcl_lock` would exist and GIL-acquired
pax callbacks re-entering `tk.call` could deadlock on it. All relevant
distros ship threaded Tcl 8.6; document this as a requirement.

**Py3 relevance:** py3's `_tkinter` keeps the same design (GIL released
around Tcl, `tcl_lock` freed for threaded Tcl, GIL-safe
`createcommand` dispatch), so the same fix carries over unchanged.

## Remaining risks / not yet validated

- The `wantobjects` typing difference on `tk.call` results (strings vs
  ints/tuples) — mitigate with an explicit `wantobjects(0)` call and
  a visual/functional pass.
- Encoding behavior of stock `_tkinter` + Tk 8.6 vs paxtkinter's
  latin-1 workarounds (the 4 `utf8_*` sites).
- `PyGILState_Ensure` inside `PaxWidgetConfigure` while `_tkinter`
  holds interpreter-internal state: the `Tcl_Preserve`/widget-command
  reentrancy of `paxwidget_cmd` needs a functional test after the fix.
- Interaction with modal dialogs / `tkwait` inner loops after the fix.

## Implementation (2026-10-20, done on branch `modernize`)

The fix was implemented as described and validated:

- `src/extensions/Pax/paxmodule.c`: every function that can run in a
  Tcl call/event context now acquires the GIL. Either by wrapping the
  whole body (impl + thin `PyGILState_Ensure`/`Release` wrapper for
  `paxwidget_cmd`, `paxwidget_widget_cmd`, `PaxWidgetEventProc`,
  `PaxWidgetDisplay`, `PaxWidgetDestroy`) or inline
  (`paxWidget_CallMethodArgs` — the choke point for all widget method
  callbacks — and `call_py_method`).
- `src/Sketch/__init__.py`: `init_ui()` no longer replaces
  `sys.modules['_tkinter']` with paxtkinter.
- `src/Sketch/UI/skapp.py`: `init_tk()` checks
  `tcl_platform(threaded)` right after root creation and aborts with
  an error message if Tcl is not threaded (required because with
  non-threaded Tcl `_tkinter`'s internal `tcl_lock` exists and the
  GIL-acquiring pax callbacks would deadlock re-entering `tk.call`).
  Also calls `self.root.tk.wantobjects(0)` so `tk.call` results come
  back as plain strings like paxtkinter returned them (verified:
  without it, e.g. `winfo rgb` returns `unicode`).
- `src/Sketch/UI/tkext.py`: pure-Python `utf8_to_latin1` /
  `utf8_to_system` helpers replace the former tkapp methods
  (used by `GetOpenFilename`/`GetSaveFilename`).
- `src/Sketch/UI/canvas.py`, `src/Plugins/Objects/multilinetext.py`:
  use the tkext helpers instead of `tk.utf8_to_latin1`.
- `setup.py`: paxtkinter Extension removed from `ext_modules` and from
  the `build&copy` list; the stale `paxtkinter.so` was removed from the
  build tree.

Validation (Xvfb, same harness as the pre-flight):

- stress run (`--run-script` with 100 hammers: canvas resizes — real X
  ConfigureNotify → `PaxWidgetEventProc` — plus nested `update()` /
  `update_idletasks()` event loops → `PaxWidgetDisplay`): **100/100
  hammers completed, zero errors**, and the stress script confirmed
  `sys.modules['_tkinter']` is the stock
  `/usr/lib/python2.7/lib-dynload/_tkinter.so`.
- `call_py_method` raw Tcl command: Python method invoked with
  arguments correctly; widget command subcommands (`bgpixel`,
  `cget -class`) work.
- plain startup: runs cleanly until killed by timeout.
- `wantobjects` behavior verified interactively (see above).

Not yet covered by automation: interactive menu/command activation
(the `call_py_method` path from real button/menu events — same code
path as the validated direct call), modal dialogs (`tkwait`), real
file dialogs, drag&drop. An interactive session is recommended.


