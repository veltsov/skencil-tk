# Build, Run and Environment

## Requirements (Ubuntu 20.04, matching `README.md`)

```
apt install python2 python2-dev python-tk python-pil python-pil.imagetk \
        tcl-dev tk-dev python-gi
```

For the proper color scheme (older setups used gtk2 defaults):
```
wget http://archive.ubuntu.com/ubuntu/pool/universe/p/pygtk/python-gtk2_2.24.0-5.1ubuntu2_amd64.deb
sudo apt-get install ./python-gtk2_2.24.0-5.1ubuntu2_amd64.deb
```
Note: recent commits removed attempts to set fonts/colors via gtk, so this
package is no longer strictly required (`gtkutils.py` is Tk-only now).

## Build and run

```
python2 setup.py build
```

- Builds the 7 C extension modules (into
  `build/lib.linux-x86_64-2.7/Sketch/Modules/`) and copies the Python
  tree into `build/lib.linux-x86_64-2.7/`, plus `compileall` on it.
- Also regenerates locale `.mo` files from `po/` into
  `src/Resources/Messages` (done automatically for every command except
  `sdist`).
- `setup.py` requires tcl/tk 8.5 or 8.6 headers (`/usr/include/tcl8.6` or
  `/usr/include/tcl8.5`), exits with an error otherwise. It also looks for
  `Imaging.h` (PIL headers) at `/usr/include/python2.7/Imaging/` (CentOS
  fix); on Debian/Ubuntu, PIL headers come from `python2-dev`/`python-pil`
  and the `_sketchmodule` builds fine without an explicit include dir.

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
the freshly built `.so` files (`paxmodule, intl, pstokenize,
_sketchmodule, skreadmodule, streamfilter, _type1module`) into
`src/Sketch/Modules/` so that the app can also be started from `src/` via
`src/skencil.py` (which imports `Sketch` from the source tree).
`src/skencil.sav` is a backup of the older launcher.

## Dev environment options (`devtools/`)

There are three ways to get a build environment:

1. **Native (no container)** — used on the current machine.
   - `devtools/build-devroot`: debootstraps a minimal Ubuntu focal root
     into `../devroot` (`fakechroot fakeroot debootstrap`), fixes
     symlinks, adds the user's passwd/group, and runs
     `devtools/devcont/install-dev-packages` inside it. Saves
     (`build-devroot.sav1..3`) exist.
   - `devtools/build-command <cmd>`: runs a command inside that root using
     `bwrap` (bubblewrap) bind-mounts: `devroot` as `/`, the repo as
     `/skdev`, plus `/proc`, `/dev`, `/tmp`, `/run`.
   - `devtools/enter-devroot`: interactive shell in that root.
   - Typical usage: `devtools/build-command python2 setup.py build`
     (wrapped by `devtools/build-skencil`).

2. **Podman container** — `devtools/devcont/Dockerfile` (FROM
   ubuntu:20.04 + `install-dev-packages`).
   - `devtools/build-devcont` builds image `skdev`; `devtools/build-skencil`
     was originally `./build-command ...` (now the bwrap variant);
     `devtools/build-command-cont` runs commands in the container;
     `devtools/enter-devcont` gives an interactive shell.

3. **AppImage packaging** — `devtools/make-appimage` runs
   `devtools/collect-app-dir` (rsyncs the build tree into `AppDir/build`,
   copies python2.7 binary, tcl/tk libs, X11/PIL shared libs and gsfonts
   into `AppDir/usr/...`) and then calls `appimagetool-x86_64.AppImage` to
   produce `build/Skencil-x86_64.AppImage`.

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
