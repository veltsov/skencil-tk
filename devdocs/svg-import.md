# SVG Import

Status: implemented.  The importer is the package
`Plugins/Filters/Lib/svgimport/`; the import filter
`Plugins/Filters/svgloader.py` only declares it (`format_name` `SVG`,
`.svg`/`.svgz`).  Goal: the imported drawing looks like the SVG, as far
as Sketch's model allows; editing structure is restored where it is
known (Inkscape layers, arcs and guides; the Inkscape flavour of
Sketch's own export, `devdocs/svg-export.md`).

Targets that are handled in full: LaTeX output through dvisvgm (DVI
with or without SVG fonts, `-E` for EPS, `--pdf`), MATLAB SVG,
Sketch's own export; Inkscape SVG for everything that has a Sketch
equivalent.

## Entry points

- File → Open / Insert Document, `skconvert`, `sk2ps`: through the
  plugin (`load.load_drawing`).
- Programmatic (e.g. for converting the output of external tools):

  ```python
  from Sketch.Plugins.Filters.Lib import svgimport
  doc = svgimport.import_svg(source, filename='', base_dir=None, page=1)
  group, messages = svgimport.import_svg_group(source, **kw)
  ```

  SOURCE is bytes, a file name or a file object; BASE_DIR resolves
  relative image references; `page=0` keeps the default page layout.
  `import_svg_group` returns one group (the layers' groups, or the
  single layer's) and the load messages.

Messages (approximations, ignored features) are collected with counts
in `doc.meta.load_messages`; File → Open shows them.  Errors raise
`SketchLoadError`.

## Modules

| Module | Content |
|---|---|
| `tree.py` | `ElementTree` parse into `Node`s with parent links and normalized names (`xlink:href`, `inkscape:label`, ...); the cascade: presentation attributes < style sheet < `style` attribute, `!important`, inheritance, `inherit`, computed `font-size`, accumulated group opacity `_opacity` |
| `css.py` | `<style>` sheets: type/class/id/attribute selectors, descendant and child combinators, specificity; `@media` all/screen; `@font-face` kept as text |
| `values.py` | numbers, lengths (user unit = CSS px = 0.75 pt), colors (named, hex incl. alpha, `rgb[a]()`, `hsl[a]()`, `currentColor`), transform lists, 6-tuple matrices (SVG order = `Trafo` order) |
| `pathdata.py` | the full path grammar (compact numbers and arc flags) into `SubPath`s; arcs and quadratics become cubics; exact bounding boxes |
| `builder.py` | the tree walk: CTM, viewports (`svg`, `symbol`, `use`), shapes, paint and line properties, layers, page size |
| `paint.py` | colors, opacity blending, caps/joins, dashes (with offset) |
| `gradient.py` | gradients and patterns |
| `fillrule.py` | nonzero fills with the even-odd rule |
| `clip.py` | clip paths (MaskGroup) |
| `mask.py` | masks (image flattening, white masks as clips) |
| `image.py` | raster images (data URIs, files), SVG images |
| `marker.py` | markers; Sketch's arrows |
| `text.py` | text as curves (SVG fonts, Inkscape, fallback) |
| `extras.py` | Inkscape arcs and guides; plugin objects, LaTeX objects, EPS of Sketch's export |

## Geometry

The root maps viewBox/preserveAspectRatio onto width × height (CSS
units; px = 0.75 pt) and flips y (`Trafo(1,0,0,-1,0,H)`).  Each element
is rendered with its CTM; coordinates are baked into the document.  The
page size is the root size (a standard paper format is recognized); a
root without a size gets the bounding box of the content as its page.

| SVG | Sketch |
|---|---|
| `rect` (rx/ry) | `Rectangle`, trafo = CTM ∘ (w,0,0,h,x,y), radii as fractions (exact under any affine CTM) |
| `circle`, `ellipse` | `Ellipse`, trafo = CTM ∘ (rx,0,0,ry,cx,cy) |
| `path`, `line`, `polyline`, `polygon` | `PolyBezier` (one Sketch path per subpath; `Z` closes) |
| `path` with `sodipodi:type="arc"` | `Ellipse` arc (Inkscape arcs and those of Sketch's export) |
| `g`, `a`, `switch` | `Group` (groups with one child are dissolved) |
| `use`, `symbol`, nested `svg` | the referenced content re-rendered (never `Clone`); viewports clip unless `overflow` is visible |
| `image` | `Image` (embedded; alpha kept), SVG images as groups |
| `text`, `flowRoot` | curves (see Text) |
| Inkscape layers | layers (label, `display:none` = invisible, insensitive = locked, `skencil:printable/outlined`) |
| `sodipodi:guide` | guide lines (horizontal and vertical ones) |

Rectangles and ellipses get a positive orientation (the y flip is moved
into the unit square/circle).

## Paint and lines

- **Opacity** (Sketch has none): `fill-opacity`, `stroke-opacity`,
  `stop-opacity`, color alpha and the product of `opacity` along the
  ancestors are blended toward white (exact over a white background);
  image opacity goes into the alpha channel.  An invisible paint
  becomes none, but the object is kept (outline mode, construction
  lines).
- **Lines**: width × √|det CTM| (Sketch's lines are not distorted;
  strongly non-uniform scaling is reported), `non-scaling-stroke`
  uses the root scale; width 0 is no line (in Sketch 0 is a hairline);
  miter limit < 2 becomes a bevel join (Sketch's limit is fixed at
  10.433); dashes in units of max(width, 1), the offset applied by
  rotating the pattern (a pattern starting inside a gap needs a
  zero-length dash, used for butt caps only); paint servers on lines
  give a solid color; `paint-order: stroke` gives two objects.
  Zero-length subpaths with round or square caps become dots.
- **Fill rule**: Sketch fills even-odd.  For a nonzero fill with
  several subpaths, `fillrule.py` probes each subpath's boundary (a
  scanline through its middle, the fill on both sides of each
  crossing, evaluated with the winding numbers of polygonal
  approximations) and drops the boundaries that do not separate
  filled from empty; the even-odd fill of the rest is then checked on
  all scanline intervals.  Exact for subpaths that do not cross each
  other (glyphs, nested shapes of either orientation); crossing ones
  are reported.  If the line needs the dropped subpaths, the fill and
  the line become two objects.
- **Linear gradients** map exactly: an affine image of a linear
  gradient is linear, so its document direction gives Sketch's
  direction, and the SVG gradient is sampled at the positions where
  its stops fall within the object's extent (`bounding_rect`, as
  `LinearGradient` uses it); spread methods are expanded into stops
  (hard stops at repeat boundaries).  **Radial gradients** are exact
  for a circle with the focus at the center (Sketch's center is
  relative to the bounding rect, the radius set by the farthest
  corner, position 0 outside); elliptical ones and focal points are
  approximated.  The print output samples gradients in 50 steps, too
  coarse for many repeats.
- **Patterns**: a single image filling the tile becomes an
  `ImageTilePattern`; the hatching of Sketch's export a
  `HatchingPattern`; anything else copies of the tile clipped by the
  object (a solid mean color above 2000 tiles).

## Clips and masks

- **clip-path** → `MaskGroup` with the mask first, its fill and line
  empty.  The mask is the rectangle/ellipse if the clip path is just
  that, otherwise one curve with the union of the children (each with
  its clip-rule, merged by `fillrule.py`); clip paths of clip paths
  nest.  A rectangular clip containing the content is dropped (MATLAB
  and dvisvgm clip everything to the axes or the page); content outside
  the clip is removed.
- **mask**: the mask content is rendered with opacity blended toward
  black (a mask value is luminance × alpha).  On a single raster image
  the mask is computed on the image's pixel grid (images resampled,
  shapes rasterized with solid or gradient fills, the mask region
  applied) and multiplied into the alpha channel.  Opaque white mask
  content on anything else is a clip.  Other masks are reported and
  ignored.  Image alpha shows on screen and in print once
  `devdocs/image-transparency.md` is implemented; SVG export keeps it.
- **filter**: ignored (reported).

## Markers

Drawn as objects at the path vertices (start/mid/end, the closing
point of closed subpaths; `orient` auto, auto-start-reverse or an
angle; `markerUnits`; viewBox and refX/refY; clipped to the marker
viewport unless `overflow` is visible; content styled from the
marker's own ancestors).  In Sketch's own Inkscape SVG
(`skencil:version` on the root) the markers of a single open subpath
are matched against the standard arrows and become native arrows; the
path ends are extended again by the retraction the arrows imply
(`PolyBezier.retract_for_arrows`).

## Text

All text is imported as curves; editable text waits for a richer text
model.

- **SVG fonts** (`<font>` with `<glyph>`; dvisvgm's default output,
  which Inkscape does not render): laid out by `text.py` — characters
  with white space handling, the x/y/dx/dy/rotate lists of the
  elements, glyph advances, letter/word spacing, ligatures (not across
  elements), text anchors per chunk; one curve per run of characters
  with one style.
- **Everything else** is converted by Inkscape (`inkscape -T`, `$INKSCAPE`
  overrides the command), once per document: each text element is
  copied with its font properties made explicit (style sheets do not
  survive the copy) into a group `sktextN` of a temporary SVG, with
  the style sheets, SVG fonts and textPath paths.  The converted groups
  (one path per tspan, with the tspan's own style; a text of one line
  becomes a single path carrying the text's transform and style, which
  are moved to the group) replace the text
  elements, take the original's declarations and transform, and are
  imported like any content — the paint comes from the original
  cascade (so `use` instances get theirs).  This covers tspans,
  positions, anchors, textPath, flowRoot, kerning and the system fonts.
- **Without Inkscape**: each run becomes a `SimpleText` in the fallback
  font (`preferences.fallback_font`) with the size, color and anchor of
  the text; characters the font does not have are dropped.

Text that is already curves (dvisvgm `--no-fonts`, `-E`, `--pdf`, the
export) needs none of this.

## Sketch's own export

From the Inkscape flavour the editing structure comes back:

- `skencil:plugin` + `skencil:params` (the `PC()` arguments): the
  plugin object with `loading=1` and the imported children as its
  rendering, as the `.sk` loader does (LaTeX objects included);
- TexText groups without these (made by TexText itself): a LaTeX object
  from `textext:text`/`textext:scale`, the trafo by inverting the
  export's group transform;
- `skencil:eps-file`: a linked `EpsImage`, placed by the bounding box
  clip of the export, if the file exists;
- layers, guides, arcs, arrows as above.

Blend groups, clones and path text come back as their rendering.

## Limitations

No opacity (blended), no soft masks except on images, no filters, no
nonzero fill of crossing subpaths, no radial focus, no gradient lines,
print gradients in 50 steps, line widths under non-uniform scaling are
averaged, no dash offset inside gaps with round caps, text only as
curves (or in the fallback font).

## Tests

`test/model/test_svgimport_model.py` (headless: parsers, cascade, fill
rule cases, gradient colors against the SVG formulas, structure of
imported documents) and `test/formats/test_svgimport.py` (visual:
samples from `svgimport_samples.py` and the real-world files in
`test/data/svgimport` against Inkscape, round trips of
the fixtures through both export flavours, dvisvgm output of the EPS
fixtures, LaTeX generated at test time, MATLAB R2022b `print -dsvg`
output from `test/formats/matlab_svg_samples.m`); see
`devdocs/testing.md`.  Inkscape is not a reference where it departs
from the specification: it ignores `preserveAspectRatio` on images,
`rgba()` in attributes, marker clipping and places objectBoundingBox
pattern tiles differently; those cases are tested numerically.

## Follow-ups

- LaTeX objects through `dvisvgm --no-fonts` and `import_svg_group`
  (an alternative to pstoedit in `latextext.py`).
- An EPS/PS/PDF import filter through `dvisvgm -E` / `--pdf`
  (`svgsaver.eps_vector` already runs dvisvgm).
