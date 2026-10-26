# Display backends: modern alternatives, antialiasing, font model

Status: **exploratory analysis, no code** (recorded 2026-10-25, branch
`modernize`). Motivated by the question "the internal image model now
preserves alpha — rather than reimplementing compositing by hand, what
modern composition-supporting display pipelines fit Skencil's design
and its performance requirements?" — to be considered after the
Python 3 port. Companion: `devdocs/image-transparency.md` (near-term
transparency plan inside the current pipeline).

## Maintainer's stated future goals (2026-10-25)

1. **Antialiasing of vector shapes** on the display is a future goal.
2. **Modernizing the font model** is a further future goal (as a new
   alternative to the Type1 stack).
3. **The draw-glyphs-as-curves part must remain**: PS fonts are
   converted to glyph outlines (bezier curves) and drawn as curves —
   this stays in the future (it is what keeps PS/PDF export exact).
   It should also benefit display: outlines-as-curves are exactly what
   path-based renderers antialias, so a path-based display backend +
   curve-outlined glyphs gives antialiased, fast text for free.
   See also `devdocs/glyph-text.md` (glyph-id text) and
   `devdocs/text-input.md` (unicode input rework, planned).

## What "fits Skencil's design" constrains

- **Device abstraction.** All drawing goes through one interface
  (`CommonDevice`/`GraphicsDevice` in `Sketch/Graphics/graphics.py`):
  nested `PushClip/PopClip` (X regions + depth-1 bitmaps),
  `PushTrafo/PopTrafo`, algorithmic pattern fills executed as
  *clip + re-executed fill*, outline mode; non-display devices
  (`InvertingDevice` for handles, `HitTestDevice`,
  `PostScriptDevice`) share the interface. A new display backend = a
  new device class; the model (`Sketch/Graphics/*`) is toolkit-free.
- **Redraw model.** Incremental, dirty-region based: the `paxwidget`
  custom Tk widget (registered by the pax C extension,
  `Sketch/UI/tkext.py`) delivers Expose regions; drawing goes directly
  onto the Tk window's X drawable through pax GC;
  `StartDblBuffer/EndDblBuffer` (offscreen pixmap); images uploaded
  via `XImage`/`ShmPutImage`.
- **X11-bound already.** pax is X11-direct (XShm, XImage, XGetImage,
  X fonts); Tk stays X11 on Linux, so this does not change with the
  py3 port — only *what we composite with* can change.
- **Text stack.** glyph-id text with Type1 fonts and custom
  encodings; no FreeType/fontconfig anywhere. Biggest friction point
  for any full renderer; but with goal 3 above (curves, not font
  rasterizers) a path-based backend needs no font backend at all on
  the display side.
- **Gradients.** axial/radial/**conical**, currently rasterized
  per-object into scratch buffers by `skimage.c`.
- **Performance profile.** Interactive editing: dragging
  objects/handles, zoom/pan, dirty-rect repaints on mostly-vector
  scenes; images secondary.

## Candidates

### A. pixman compositing inside the current pipeline — smallest genuinely-modern step

pixman is the SIMD-optimized client compositing library underneath
cairo and the Xorg server. Keep the model (rasterize → composite →
`ShmPutImage`), replace hand-written blend/scale loops in skimage.c
with pixman operators (`PIXMAN_OP_OVER`, ARGB32 sources,
`pixman_transform`). C-only, Python-version-independent (works now and
after the port). Full Porter–Duff OVER per pixel; multi-GB/s
compositing with runtime CPU dispatch — a full-HD RGBA blit is a few
ms; dirty-rect redraws trivial. Cost: `libpixman-dev` dependency,
moderate C work. Limit: modernizes images/tiles/blending only; vector
shapes keep today's rasterization (no AA).

### B. XRender — the composition extension of X11, used where Skencil already lives

Render provides exactly the missing primitive:
`dest = (source IN mask) OP dest` with per-pixel alpha,
`SetPictureTransform` (projective, filters, v0.6), and — notably —
linear/radial/**conical gradient source pictures (v0.10)** and blend
modes (v0.11), i.e. it even matches Skencil's gradient set
(renderproto.txt, version 0.11, 2009).

Two integration depths: (1) *minimal* — upload RGBA images as ARGB
pictures and `Composite` (with transform) onto the window/buffer
pixmap; deletes the `copy_image_to_ximage`/`transform_to_ximage`
visual-conversion machinery for images. (2) *fuller* — ARGB buffer
pixmap as canvas backing store, composite everything server-side.

- `libxrender-dev` is **already in the dev container package list**
  (`devtools/build-devcont.log`) — no new dependency.
- Speed: modern Xorg accelerates Render ops on GPU via glamor where
  the driver supports it; falls back to server-side pixman otherwise.
  Works unchanged under XWayland (Wayland-era path for an X11 Tk app).
- Risk: Render is in maintenance mode (feature-frozen since ~0.11) —
  but it is the foundation of every compositing window manager,
  present everywhere, and Skencil needs no future features from it.
  Do not use server trapezoids for vector AA (slow/deprecated); keep
  client rasterization for vectors.

### C. Cairo as the display renderer — the strategic modernization

A new device class rendering into a cairo `ImageSurface` (ARGB32),
uploading dirty rects through the existing pax image-blit path. Cairo
gives AA, full transparency, axial/radial gradients natively (conical
via `cairo_pattern_create_mesh`, 1.12+), dashing, path-based clipping —
replacing the skimage.c raster loop collection and much of `SimpleGC`.

- **Fit:** good *because* of the device abstraction — the interface
  maps almost 1:1 onto cairo concepts (trafos → cairo matrices;
  pattern fill via clip+paint is cairo's natural idiom). `pycairo`
  is Python-3-only → this is the **post-py3-port** move.
- **Speed:** pixman-backed software raster (same engine as option A);
  with dirty-region-only rendering the cost profile stays close to
  today's. Full-frame ARGB32 at 1920×1080 ≈ 8 MB per full repaint —
  not a bottleneck at interactive rates. Cairo's GL backend is poorly
  maintained; software is the right choice.
- **Export synergy:** a cairo **PDF** surface supports
  transparency/SMask natively (`devdocs/image-transparency.md`,
  "Future alternative"). Cairo's **PostScript** surface does *not*
  support transparency — the hand-rolled `PostScriptDevice`/
  `sketch-proc.ps` stays for `.ps`/print regardless.
- **Cost/risks:** text — solved by goal 3: draw glyph outlines as
  bezier paths through the device (correct, cacheable per font+size;
  no cairo font backend needed). Weeks-scale device rewrite; X11
  handles/modes stay on pax GC (`InvertingDevice` must stay X anyway);
  Expose-region clipping maps onto cairo path/rectangle clips.
- **Variant rejected:** cairo `XlibSurface` drawing directly onto the
  Tk window. It transparently uses XRender when available, but is
  TrueColor-only ("Currently, only TrueColor visuals are fully
  supported" — cairo manual), forces cairo/X-GC coexistence on one
  drawable with flush management, and buys nothing over A+C hybrids.

### D. GPU tier: OpenGL/EGL or skia-python — power tools, wrong size

skia-python is alive and real: wheels for Python 3.9–3.15, GLX/EGL GPU
acceleration plus CPU raster; but a large dependency (libEGL,
fontconfig required; per-m116… migration notes signal real API churn).
Integration would mirror option C (render to raster surface, blit via
pax). Raw PyOpenGL onto a GLX/EGL context bound to the Tk window means
re-implementing tessellation, text, dashes, pattern caches — a
rendering-engine project. Both require the same full device rewrite as
C with far more risk/dependency weight, and Skencil's scenes don't
need GPU: pixman/cairo raster is already far beyond the hand-written
C. Revisit only if profiling of real user documents proves a wall.

### E. Tk-native (Tk 9 photo compositing, canvas items) — no

Photo images have alpha compositing (`-compositingrule`) since 8.6,
but the reason for `paxwidget` is to bypass Tk's slow, Python-object-
heavy path. Whole-frame rendering through Tk photo/canvas was already
evaluated and rejected — `devdocs/paxtkinter-analysis.md`, Option D
("drop pax rendering entirely (pure Tk Canvas / ImageTk). Weeks of UI
rewrite; not now").

## Recommendation (timeline)

| Phase | When | What |
|---|---|---|
| 1. Transparency without hand-rolled compositing | now / any time | **A + B(1)**: pixman (or XRender) compositing for RGBA images inside skimage.c. Modern composition, minimal risk, keeps every performance property (Shm uploads, dirty rects, pixmap tile cache). |
| 2. The strategic move | after the py3 port | **C**: cairo `ImageSurface` display device as a new device class behind the existing interface; X11 device kept as fallback. AA + transparency everywhere; later option to swap PDF export to a cairo PDF surface (SMask free). The device-interface cleanliness is what makes this swappable — keep all new display code behind `CommonDevice`, not ad-hoc `gc.` calls. |
| 3. Non-goals | — | GPU/skia (unless profiling demands), Tk-native rendering, Wayland-native (XWayland covers the X11 backend; an EGL backend would be the escape hatch if ever needed). |

Phases 1 and 2 are not wasted work relative to each other: pixman (1)
and cairo (2) share the same raster engine, and the phase-1 code
(blend-over-destination for images) remains the fallback when cairo is
unavailable. Conversely, if phase 2 is committed to, phase 1 can be
slimmed to the minimal destination-fetch-and-blend fix, and the full
modernization budget spent on C.

## Antialiasing and the font model (how the goals fit together)

- Pre-cairo, vector AA has no good home: server trapezoids (Render)
  are slow/deprecated, and hand-adding coverage AA to skimage.c would
  be reimplementing pixman/cairo badly. **Vector AA therefore rides on
  phase 2 (cairo device)** — paths, then pattern/gradient fills, then
  glyph outlines all antialias uniformly.
- Font-model modernization should land the **outline (curve)
  extraction** as the single glyph representation (goal 3: keep
  draw-glyphs-as-curves). With that:
  - display gets AA text for free once the cairo device exists
    (outlines drawn as paths, cached per font+size as cairo paths or
    raster tiles);
  - the Type1-specific machinery (bitmap strikes, X fonts, encoded
    text bytes) becomes replaceable without touching renderers;
  - `devdocs/glyph-text.md`'s gid representation stays the model-level
    truth; `devdocs/text-input.md` (unicode input) is the input-side
    companion of the same modernization.

## Facts verified 2026-10-25

- gs 9.55.0 installed; `-dALLOWPSTRANSPARENCY` gating in `gs_init.ps`
  (see `devdocs/image-transparency.md`).
- XRender spec version 0.11 (renderproto.txt): SetPictureTransform
  v0.6, linear/radial/conical gradient pictures v0.10, blend modes
  v0.11.
- cairo manual: Xlib surface "automatically takes advantage of X
  render extension if it is available"; "only TrueColor visuals are
  fully supported".
- skia-python README: Python 3.9–3.15 wheels, GLX/EGL acceleration,
  libEGL/fontconfig required on Linux, per-version migration notes.
- `libxrender-dev` already present in the dev container package list.
