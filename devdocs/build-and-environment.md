# Build, Run and Environment

## Requirements

For the python3 build (the `py3` branch, matching `README.md`; on
Ubuntu 22.04 jammy `python3` is 3.10, matching
`build/lib.linux-x86_64-3.10`):

```
apt install python3 python3-dev python3-tk python3-pil python3-pil.imagetk \
        tcl-dev tk-dev
```

The test suite additionally uses `xvfb`, `ghostscript`, `pstoedit` and
`python3-pytest` (the same set as
`devtools/devcont/install-dev-packages`).

Historical (the py2 `modernize` branch, Ubuntu 20.04): `python2
python2-dev python-tk python-pil python-pil.imagetk tcl-dev tk-dev
python-gi`.  The old python-gtk2 deb note is obsolete — recent commits
removed attempts to set fonts/colors via gtk (`gtkutils.py` is Tk-only
now).

## Build and run

```
python2 setup.py build
```

- Builds the 6 C extension modules (into
  `build/lib.linux-x86_64-2.7/Sketch/Modules/`) and copies the Python
  tree into `build/lib.linux-x86_64-2.7/`, plus `compileall` on it.
- **The copy step applies to all Python sources, not only to
  C-extension-dependent files.** The runtime imports exclusively from
  `build/lib.linux-x86_64-2.7/` (`src/` is not on `sys.path`), so any
  edit to a `.py` file under `src/` (and `Plugins/`, `Script/`) is
  invisible to the running application until you re-run
  `python2 setup.py build`. Incremental builds are cheap: distutils
  only re-copies changed files (by timestamp) and re-runs `compileall`.
- Also regenerates locale `.mo` files from `po/` into
  `src/Resources/Messages` (done automatically for every command except
  `sdist`).
- `setup.py` requires tcl/tk 8.5 or 8.6 headers (`/usr/include/tcl8.6` or
  `/usr/include/tcl8.5`), exits with an error otherwise. It also looks for
  `Imaging.h` (PIL headers) at `/usr/include/python2.7/Imaging/` (CentOS
  fix); on Debian/Ubuntu, PIL headers come from `python2-dev`/`python-pil`
  and the `_sketchmodule` builds fine without an explicit include dir.

### Never run the py2 build from the py3 checkout (2026-10-27 incident)

Since the py3 port, the two branches (`modernize` = py2 reference,
`py3` = port branch) share **one** `build/` directory, with per-version
subdirectories (`lib.linux-x86_64-2.7` / `lib.linux-x86_64-3.10`, etc.).
The subdirectory separation is *not* enough to make cross-branch builds
safe:

- **What happens:** running `python2 setup.py build` while the `py3`
  branch is checked out makes distutils `build_py` copy *all* `.py`
  files — including py3-only sources with `Tkinter`→`tkinter` renames,
  `str.maketrans`, etc. — into `build/lib.linux-x86_64-2.7/` *before*
  `build_ext` fails on the py3-only C extension sources.  The failed
  build still leaves the py3-only Python tree in place.
- **Symptom:** the py2 app (`/home/ve/bin/skencil` →
  `build/scripts-2.7/skencil`) crashes at startup with
  `AttributeError: type object 'str' has no attribute 'maketrans'`
  from `Sketch/Graphics/font.py` (or an `import tkinter` /
  syntax error, depending on how far the port got).
- **Diagnosis:** compare the build tree against the branch that is
  supposed to own it, e.g. diff
  `build/lib.linux-x86_64-2.7/Sketch/Graphics/font.py` against
  `git show modernize:src/Sketch/Graphics/font.py`.  Tell-tale signs of
  py3 content in the py2 tree: `from __future__ import division`,
  `as_unicode` imports, `str.maketrans`.  Fresh `.py` timestamps later
  than the last py2 commit are another hint.
- **Recovery:** check out the correct branch in a detached worktree
  (`git worktree add --detach /tmp/wt <commit>`), build there
  (`python2 setup.py build`), verify (Xvfb smoke run), then replace
  `build/lib.linux-x86_64-2.7`, `build/scripts-2.7` and
  `build/temp.linux-x86_64-2.7` with the worktree's copies.  Done
  2026-10-27: the working build was restored from the `modernize` tip
  (`43d4667`), which was never actually broken — only the build tree was.
- **Prevention:** always build from a checkout (or worktree) of the
  branch whose interpreter you invoke; never share one working tree
  between `python2 setup.py build` and `python3 setup.py build`.

Run (directly from the build tree, no install):

```
./build/scripts-2.7/skencil [file.sk]
```

The launcher script (`src/skencil`) inserts `sys.path[0] +
'/../lib.linux-x86_64-2.7'` — i.e. it relies on the relative position of
`build/scripts-2.7` and `build/lib.linux-x86_64-2.7`. Keep this layout
intact when changing the build.

Other CLI tools in `src/`: `sk2ps` (sk→PS converter, installed as a
script), `skconvert.py`, `sk2ppm.py`, `skshow.py`.

### Development shortcut

`setup.py` supports `python2 setup.py build&copy` — builds and then copies
the freshly built `.so` files (`paxmodule, pstokenize,
_sketchmodule, skreadmodule, streamfilter, _type1module`) into
`src/Sketch/Modules/` so that the app can also be started from `src/` via
`src/skencil.py` (which imports `Sketch` from the source tree).
`src/skencil.sav` is a backup of the older launcher.

## Dev environment options (`devtools/`)

There are three ways to get a build environment:

1. **Native (host system)** — used on the current machine for the py3
   branch.  Since the py3 port the default build environment is simply
   the host (Ubuntu focal with python3.10, tkinter, PIL, headers;
   see `devdocs/python3-porting.md`); the debootstrapped `devroot` (bwrap
   container, `devtools/build-devroot`, `enter-devroot`) and the podman
   container are the alternative environments, selected with the
   `SK_DEV_ENV` variable (see below).
   Note: numpy is installed on the dev host but is **not** a dependency
   — the application's only third-party import is PIL (verified by an
   import sweep of `src/`; see the comment in `collect-app-dir`).  Do
   not add it to the package lists of the environments.
   - `devtools/build-command <cmd>`: changes to the skencil development
     directory (the parent of the directory containing the script,
     resolved with the `dirname $(dirname $(readlink -f ...))` trick,
     like the old `enter-devroot`) and execs the arguments in the
     environment selected by `SK_DEV_ENV`:
     - empty or `host` (default) — the host system;
     - `cont` — the podman container (via `devtools/build-command-cont`);
     - `devroot` — the bwrap devroot (via `devtools/enter-devroot`);
     any other value is rejected with an error.
   - Typical usage: `devtools/build-command python3 setup.py build`
     (wrapped by `devtools/build-skencil`).

2. **Podman container** — `devtools/devcont/Dockerfile` (FROM
   ubuntu:22.04 + `install-dev-packages`, the python3.10 package list
   including the test-suite tools: xvfb, ghostscript, pstoedit, pytest).
   - `devtools/build-devcont` builds image `skdev`;
     `devtools/build-command-cont` runs commands in the container and
     `devtools/enter-devcont` gives an interactive shell; both resolve
     the development directory with the dirname/readlink trick and
     mount it at `/skdev`, so they work from any CWD (previously they
     relied on being run from `devtools/`, mounting `..`).
   - The container is normally driven through `SK_DEV_ENV=cont
     devtools/build-command <cmd>` (e.g. `SK_DEV_ENV=cont
     devtools/build-command python3 setup.py build`).

3. **AppImage packaging** — `devtools/make-appimage` runs
   `devtools/collect-app-dir` and then
   `appimagetool-x86_64.AppImage --appimage-extract-and-run` to produce
   `build/Skencil-x86_64.AppImage` (the extract-and-run mode works also
   on systems without FUSE, e.g. sandboxed environments without
   `/dev/fuse`; appimagetool is an AppImage itself).

   `devtools/collect-app-dir` collects the **python3 payload** (run from
   the repository root, which `build-command` ensures):
   - the py3 build tree (`build/lib.linux-x86_64-3.10` and
     `build/scripts-3.10`) into `AppDir/build`;
   - `/usr/bin/python3.10` into `AppDir/usr/bin`;
   - the stdlib `/usr/lib/python3.10` (incl. `lib-dynload`) plus
     `/usr/lib/tcl8.6`, `/usr/lib/tk8.6` and `libBLT` (needed by the
     `_tkinter` C module) into `AppDir/usr/lib`;
   - **only PIL** (the only third-party package the application imports;
     verified by an import sweep of `src/`) from the shared
     `/usr/lib/python3/dist-packages` into
     `AppDir/usr/lib/python3.10/dist-packages` — the Debian-patched
     `site.py` adds the prefix's *dist-packages* (not upstream's
     site-packages) once `PYTHONHOME` points at the bundled prefix;
   - the PIL-9/tcl-tk shared libraries it needs
     (`libpython3.10`, `libtcl8.6`, `libtk8.6`, `libXss`, `libBLT`,
     `libjpeg8`, `libtiff5`, `libwebp7`, `libwebpdemux`, `libwebpmux`,
     `libopenjp2`, `liblcms2`, `libimagequant`, `libjbig`,
     `libdeflate`, `libraqm`, `libfribidi`, `libharfbuzz`) into
     `AppDir/usr/lib/x86_64-linux-gnu`;
   - `/usr/share/tcltk` into `AppDir/usr/share`; the gsfonts
     (`/usr/share/fonts/type1/gsfonts`, without `*.pfm`) merged into the
     *AppDir copy* of
     `AppDir/build/lib.linux-x86_64-3.10/Resources/Fontmetrics/` (no
     `--delete`: it would remove the files bundled from
     `src/Resources/Fontmetrics`; there are no filename collisions).
     `config.font_path` includes the app's Fontmetrics directory
     (`configutil.py`), so this makes the AppImage self-contained for
     the URW Type1 fonts.
     Bug fixed 2026-10-28: this rsync used to write into the *build
     tree* (`build/lib.linux-x86_64-3.10/Resources/Fontmetrics/`) — and
     after the build tree had already been rsynced into the AppDir — so
     the AppDir/AppImage payload contained only the 43 files bundled in
     the repository while the build tree grew to 113 files with the
     host gsfonts (the AppImage only worked on machines that had
     `/usr/share/fonts/type1/gsfonts` installed, and running
     `make-appimage` a second time silently "fixed" the payload since
     the polluted build tree was then copied verbatim). The polluted
     gsfonts-only files were removed from the build tree.
   Stale payload dirs are wiped first (`rsync --delete` does not remove
   top-level extraneous entries).  If a future change makes the
   application import another third-party package, a corresponding
   rsync line must be added here — the runtime smoke tests below catch
   the missing package as an `ImportError`.

### Testing the AppImage without FUSE

The AppImage cannot be executed directly where FUSE is unavailable
(`/dev/fuse` missing), but both relevant operations work without it:

- **Building:** appimagetool is run with `--appimage-extract-and-run`
  (see `devtools/make-appimage`).
- **Testing:** extract with the runtime's own extractor (no FUSE
  involved): `./build/Skencil-x86_64.AppImage --appimage-extract`
  creates `squashfs-root/`; run `squashfs-root/AppRun` from there.
  Note that AppRun selects the tool from the *invocation name*
  (`basename $0`, or `ARGV0` when `APPIMAGE` is set — the AppImage
  runtime sets both when the image is invoked through a symlink), not
  from `$1`; a bare `AppRun` launch runs the GUI.  To exercise the CLI
  tools directly from the AppDir/extracted tree, set the variables
  explicitly, e.g. `env APPIMAGE=x ARGV0=sk2ps AppRun file.sk out.ps`.

Verified 2026-10-27 (this sandbox, FUSE-less): sk2ps output byte-identical
apart from the CreationDate line, and the GUI screenshot under Xvfb
(`--run-script test/ui/scripts/shot_basic.py` with `SKENCIL_SHOT_FILE`)
pixel-identical to `test/baselines/shots/tarr-basic.png`, for both the
AppDir and the extracted AppImage.

## X11 runtime notes

- The app needs an X server (Xlib/X11 is used directly by `paxmodule`).
- Type 1 font handling: fonts are looked up via `Sketch/Base/config.py`
  `font_path` (`/usr/share/fonts/type1/gsfonts` etc.) and the
  `SKETCH_FONTPATH` environment variable is supported (added in this fork).
  Text can be drawn as curves when the X11 font is missing (new feature).
- `pstoedit` is needed in the dev image (used somewhere in filters/tests).

## Known build artifacts / cruft

- `build.log` (root of repo) — an old build log from 2018.
- `*.sav`, `*.sav2`, `*.sav3` — manual backups; `*.patch` — leftover
  patch files. All are gitignored; treat as history, not dead code to
  delete.
- `.vscode/settings.json` sets `python.pythonPath` to `/usr/bin/python2`.
