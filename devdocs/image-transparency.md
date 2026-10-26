# Image Transparency: display and PS/PDF export — analysis and plan

Status: **planned, not implemented** (recorded 2026-10-25, branch `modernize`).
Scope: raster images whose alpha channel the internal model already
preserves (see `Sketch/Graphics/image.py`, `RasterImage`/`ImageData` and
`test/model/test_image.py`); vector-object opacity is a separate,
larger topic (see `devdocs/display-backends.md`).

## Current state (where alpha is dropped)

- **Model — done.** `RasterImage` stores `L`/`RGB`/`RGBA` as packed
  buffers, 4 bytes per pixel for RGB/RGBA (`_RAWMODE` in
  `Sketch/Graphics/image.py`). Alpha survives load, `.sk` embed
  (PNG), and roundtrips; covered by `test/model/test_image.py`
  (`test_image_from_pil_keeps_alpha`,
  `test_imagedata_embed_save_reload_roundtrip`).
  The code comments say explicitly that the display treats RGBA like
  RGB "but the data is kept for future transparency support".
- **Display — alpha dropped.** `CommonDevice.DrawImage`
  (`Sketch/Graphics/graphics.py`, "def DrawImage", ~line 1066) calls
  `_sketch.copy_image_to_ximage` (axis-aligned) or
  `_sketch.transform_to_ximage` (rotated) in
  `src/extensions/Modules/skimage.c`; both treat `RGBA` exactly like
  `RGB` (4th byte = padding), drawing transparent pixels opaque.
- **PostScript export — alpha dropped.** `PostScriptDevice.DrawImage`
  (`Sketch/Graphics/psdevice.py` ~line 563) writes hex data via
  `_sketch.write_ps_hex`; the RGB writer in skimage.c *skips every
  4th byte* (`write_ps_hex_rgb`). The PS side consumes the data
  through `skcimg`/`skgimg` procs in
  `src/Resources/Misc/sketch-proc.ps` (plain Level 2 `colorimage`,
  3 channels). `PostScriptDevice.TileImage` explicitly flattens
  RGBA→RGB ("We don't support transparency in textures").
- **PDF export — inherits PS.** `Plugins/Filters/pdfsaver.py` pipes
  the PostScriptDevice output through ghostscript `pdfwrite`
  (`-dCompatibilityLevel` defaults to `1.4`,
  `config.preferences.pdf_compatibility_level`). So PDF transparency
  is entirely determined by what the PostScript stream expresses.

## Verified environment facts (2026-10-25)

- Ghostscript **9.55.0** is installed in the dev environment.
- gs's PostScript transparency operators
  (`.begintransparencygroup`, `.endtransparencygroup`,
  `.begintransparencymaskimage`, `.endtransparencymask`,
  `.setblendmode`, `.setfillconstantalpha`, ...) exist in the
  interpreter but are gated for user PostScript behind
  **`-dALLOWPSTRANSPARENCY`** since gs 9.52
  (`Resource/Init/gs_init.ps`, `/ALLOWPSTRANSPARENCY //false def`).
- Standard PostScript has **no per-pixel alpha** (Level 3 masked
  images are 1-bit only) — but ghostscript's own PDF interpreter
  implements image SMask entirely in PostScript, in
  `Resource/Init/pdf_draw.ps` (SMask-in-image flow ~lines
  2340–2385; `makesoftmaskimage` at 836 building an internal
  **ImageType 103** soft-masked image dict at 858). The recipe is
  reproducible from our PostScript output; pdfwrite converts it into
  a real PDF image XObject with `/SMask` (the `/.image_with_SMask`
  comment in pdf_draw.ps points at `gdevpdft.c`).

## Plan

### Step 0 — pre-flight experiment (de-risks the PDF design)

Standalone script (in `/tmp`, not the repo): emit a minimal PS with
an RGBA image using the recipe below, run
`gs -dALLOWPSTRANSPARENCY -sDEVICE=pdfwrite -dCompatibilityLevel=1.4`,
check the PDF for `/SMask` and rasterize it to verify blending.
Do this before touching the codebase.

### Step 1 — display: software blending (near-term)

- **skimage.c**: alpha-aware variants of `copy_image_to_ximage` /
  `transform_to_ximage` (or a `blend` flag) that, for
  `mode == "RGBA"`, composite `src*a + dst*(1-a)` per pixel into the
  destination XImage. Destination pixels: copy the affected region
  from the current drawable (buffer pixmap during double buffering,
  else the widget) into the XImage first (XGetSubImage semantics), so
  the image composites over whatever is *beneath it*. Requires a
  reverse mapping X pixel → RGB (visual masks / colormap; the forward
  conversion already exists in the `image_scale_rgb_*` helpers).
- **graphics.py `DrawImage`**: for RGBA, fetch the destination region
  into the XImage (or pass drawable info down to C), call the
  blending variants; clip/shm/put logic unchanged. The EPS-preview
  path (`DrawEps` → `DrawImage`) benefits automatically.
- **Out of scope initially:** alpha in `ImageTilePattern` fills
  (display tiles + PS `TileImage`) — keep the current RGBA→RGB
  behavior there.
- Rejected for now: XRender compositing — see
  `devdocs/display-backends.md` for why it is deferred to a modern
  backend decision rather than done here.
- Open decision: 8-bit pseudocolor displays cannot invert pixel→RGB
  losslessly; either accept background blending there or approximate
  via colormap lookup.

### Step 2 — plain PostScript: explicit flatten

Portable PostScript cannot express per-pixel alpha, so for
`sk2ps` / `.ps` / print, `PostScriptDevice.DrawImage` and `TileImage`
should explicitly flatten RGBA over white (or a configurable
background) before writing hex — making the drop deliberate and
correct-looking on a white page instead of an accident of
byte-skipping. Small Python-side helper on `RasterImage`/`ImageData`
(e.g. `FlattenAlpha(bg)`); `write_ps_hex` stays unchanged.
Open decision: white vs. a preference for the background color.

### Step 3 — PDF export with real alpha

- **sketch-proc.ps**: new proc (e.g. `/skacimg`) implementing the gs
  recipe from pdf_draw.ps: alpha channel drawn as a gray image inside
  `.begintransparencymaskimage` … `0 .endtransparencymask`, RGB image
  drawn inside an isolated `.begintransparencygroup`, guarded at
  runtime by `systemdict /.begintransparencygroup known` — fallback
  to plain `skcimg` (flattened RGB) on real printers / non-gs
  interpreters.
- **psdevice.py `DrawImage`**: for `mode == 'RGBA'` additionally emit
  the alpha bytes as a second hex stream and call the new proc.
  Small skimage.c change: parameterize `write_ps_hex` (or add a
  separate entry) so the 4th byte is emitted for the alpha stream.
- **pdfsaver.py**: add `-dALLOWPSTRANSPARENCY` to `gs_command`
  (compat level already defaults to 1.4).

### Step 4 — rebuild, tests, baselines, docs

- `python2 setup.py build` (after C *and* .py changes), then run
  `test/` (model, formats, ui via Xvfb) — see `devdocs/testing.md`.
- Re-record affected baselines (`test/add-fixture` / `record.py`):
  at minimum the `alphares.sk` EPS baseline (formats layer compares
  sk2ps output byte-wise); UI screenshot baselines if the display
  change alters them.
- New tests: flatten helper (model layer); formats test asserting the
  alpha PS stream / PDF `/SMask` presence.

## Future alternative

Once the cairo display device from `devdocs/display-backends.md`
exists, PDF export could switch to a cairo PDF surface, which
supports transparency/SMask natively — no gs, no
`-dALLOWPSTRANSPARENCY` recipe. Note the asymmetry: cairo's
PostScript surface does *not* support transparency, so the hand-rolled
`PostScriptDevice`/`sketch-proc.ps` stays for `.ps`/print regardless.
