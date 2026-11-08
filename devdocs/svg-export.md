# SVG Export

Status: implemented.  One export filter, `Plugins/Filters/svgsaver.py`
(`format_name` `SVG`), in two flavours chosen by the option `flavour`:

| Flavour | `flavour` | Goal |
|---|---|---|
| Inkscape SVG (default) | 0 | all layers, visually identical to the PostScript output of the printable ones, plus as much editing structure as Inkscape can keep |
| Plain SVG | 1 | the printable layers only, visually identical to the PostScript output; no editing structure |

The SVG import (`devdocs/svg-import.md`) restores the editing
structure of the Inkscape flavour: layers, guides, arcs, arrows, plugin
and LaTeX objects, linked EPS files.

`plugins.guess_export_plugin` prefers the plugin whose format name
equals the extension (`SVG` for `.svg`, `PDF` for `.pdf`),
independently of the plugin scan order.

## Reference semantics

"Visually identical" means identical to what `PostScriptDevice`
(`Graphics/psdevice.py`) and the prolog `Resources/Misc/sketch-proc.ps`
produce; PDF export is the same PostScript run through ghostscript.
The saver reimplements the drawing semantics of each object instead of
going through a device, so that it can emit structure (groups,
gradients, clip paths, ...) rather than a flat stream.

Coordinates: the SVG user unit is the point (`width="..pt"` plus a
`viewBox` of the same size).  The document is mapped by
`Trafo(1,0,0,-1,-left,top)` (y flipped) and coordinates are baked into
the path data; layers carry no transformation.  Stroke widths are thus
document points, like the PostScript `S` (which strokes in the page
matrix).  Elements that need a local coordinate system (rotated
rectangles and ellipses, text elements, images) get an orthonormal
`transform`, so strokes are not distorted; paint servers of such
elements get the inverse in their `gradientTransform` /
`patternTransform`.

## Options

Declared as `#parameters` in the plugin headers and asked for by the
export options dialog of File → Export (see `devdocs/architecture.md`,
Plugins); `skconvert` takes them as `-o NAME=VALUE` (e.g. `-o
flavour=plain -o box=bounding`), and the options dict of
`ExportInfo.__call__` (tests, scripts) can override them.

| Option | Values (default first) | Flavours |
|---|---|---|
| `flavour` | 0 Inkscape, 1 Plain | — |
| `box` | 0 page, 1 bounding box of the printable layers | both |
| `text` | 0 glyph paths, 1 SVG `<text>` | Inkscape |
| `eps` | 0 vector (converted), 1 raster image | both |
| `eps_dpi` | 300 | both |
| `images` | 0 embed, 1 link linked images | Inkscape |

The saver never writes files other than the SVG.

## Mapping

| Sketch | SVG |
|---|---|
| layer | Plain: `<g>` for printable layers only.  Inkscape: every layer as `<g inkscape:groupmode="layer" inkscape:label>`, `display:none` iff not *visible*, `sodipodi:insensitive` iff locked, `skencil:printable`/`skencil:outlined` |
| guide lines, grid | Inkscape: `sodipodi:guide` (position y up from the lower left corner, `x,y`), `inkscape:grid` in `sodipodi:namedview` |
| Group | `<g>` |
| BlendGroup / BlendInterpolation | `<g>` (+ `skencil:blend`, `skencil:blend-steps`) with the computed objects |
| plugin objects (`is_Plugin`; autoshapes have `is_Compound = 0`) | `<g>` of the children; Inkscape adds `skencil:plugin` and `skencil:params` (the `PC()` arguments, captured through `SaveToFile`) |
| Clone (checked first: it delegates unknown attributes to the original) | Inkscape: `<use>` with `translate(dx,-dy)` (an Inkscape clone); Plain: the original again in a translated `<g>` |
| MaskGroup | clip path from the mask (evenodd for curves, nonzero for text, the parallelogram of an image); the mask's fill below and its outline above the clipped group, as in `MaskGroup.DrawShape` |
| PolyBezier | `<path>`, with the arrow-retracted `apaths` |
| Rectangle | `<rect>` (+`rx`/`ry` = radius × side) if the transformed unit square is a rectangle, else `<path>` |
| Ellipse | full: `<ellipse>`/`<circle>` (axes from the SVD of the matrix); arcs: Inkscape `sodipodi:type="arc"` path (start/end = Sketch angle − SVD rotation; not with arrows), Plain `<path>` |
| Image | `<image>` (`image-rendering:optimizeSpeed`, like PostScript), PNG with alpha; the original file's bytes for PNG/JPEG files |
| EpsImage | see below |
| SimpleText, path text | see below |
| LtxObj | Inkscape: TexText group, see below; Plain: the rendered children |

### Paint

- Fill rule: evenodd for curves (PostScript `eofill`), nonzero for
  text.  Lines: solid color only; dashes × `max(width, 1)`; caps and
  joins; `stroke-miterlimit` 10.433 on the root (`psdevice` sets it
  globally).  Width 0 (a PostScript hairline) becomes
  `HAIRLINE_WIDTH` (0.3 pt).
- Patterns use `obj.bounding_rect` (grown by the line) exactly like
  the device's `pattern_rect`.
- Linear and radial gradients: the formulas of
  `execute_axial_gradient` / `execute_radial`; radial stops reversed.
  Smooth, not the 50-step staircase of the print output.
- Conical gradient: no SVG primitive; `CONICAL_STEPS` wedges clipped
  to the shape (the fallback of `ConicalGradient.Execute`), the
  outline as a separate element on top.
- Hatching: `<pattern>` whose tile is one line period, phase-matched to
  `HatchingPattern.Execute` (a line at the top of the rotated box).
- Image tile: `<pattern>` with the tile mapped like `tileimage2`.
- Arrows: Inkscape uses markers (`markerUnits="strokeWidth"`, one per
  shape/color/end) for a single open path, which Inkscape can edit;
  otherwise (several subpaths, Plain SVG) explicit arrow paths in a
  group with the line, placed as in `CommonDevice.draw_arrow`.  Width 0
  draws no arrows, as in PostScript.

### Text

- Glyph paths (Plain SVG; Inkscape default): one `<g>` per text
  object, one `<path>` per glyph from the Type 1 outlines
  (`Font.GetOutline`) placed like `SimpleText.Paths()`; path text uses
  `CharacterTransformations()`.  Inkscape adds `aria-label` (as its own
  Object to Path does) and `skencil:text/font/size/halign/valign/trafo`
  so that the text can be rebuilt.
- `<text>` (Inkscape `text=1`): the per-glyph `x` positions from
  `TypesetText` pin the layout (Sketch has no kerning); the family
  is mapped from the sfd family to the URW base 35 OpenType families
  (`font_family_map`), weight/style from the sfd attributes, kerning
  and ligatures disabled.  Visually very close if those fonts are
  installed.  Falls back to glyph paths for glyphs without a unicode
  equivalent and for conical fills; path text always uses glyph paths.
- The text is the glyph sequence converted to unicode through the glyph
  names, so a `-` read from a `.sk` file or typed in a font of the
  standard encoding is U+2212: it is the glyph `minus` (the code-45
  quirk, `devdocs/glyph-text.md`), drawn as such in all outputs.

### LaTeX objects (TexText)

Inkscape SVG writes the attributes TexText (≥ 1.x, `textext`
namespace) reads, on the group of the rendered paths: `text`
(`unicode_escape`d, a leading `\noskltx` dropped, a
`\preamble<c>…<c>` prefix kept as a `%` comment line for the user to
sort out), `preamble` (the `sk-ltx.tex` the plugin would use,
`latextext.find_user_preamble`; empty if none), `scale` = size/10,
`alignment="top left"`, `texconverter`, `pdfconverter="inkscape"`,
`stroke-to-path`, `version`.  TexText re-renders at its 10pt base size
and places the result with the old node's `transform` (times new
scale / old scale), so the group's `transform` is Sketch's trafo times
`Scale(size/10)` (y down), `jacobian_sqrt` its √|det|, and the baked
children sit in an inner group with the inverse transform.  Re-rendering in Inkscape is best-effort: the text and the
preamble reference survive, position and size may be somewhat off.

### EPS

`eps=0`: converted to SVG with `dvisvgm -E --no-fonts` (inkscape as
the fallback), the converter's viewBox mapped onto the EPS bounding
box, ids prefixed, clipped to the bounding box like `skeps`.
`eps=1` (or when conversion fails): rendered by ghostscript
(`pngalpha`, `eps_dpi`) and embedded; last resort: the preview image.
Inkscape adds `skencil:eps-file`.

## Known differences from the PostScript output

PostScript drops image alpha (`devdocs/image-transparency.md`); the
SVG agrees with the screen there.

## Tests

`test/formats/test_svg.py` (see `devdocs/testing.md`): the Plain flavour
rasterized by Inkscape against the ghostscript rendering of `sk2ps`
with embedded fonts (4x downsampled, `KNOWN_DIFFERENCES` for the
cases above); Inkscape
vs. Plain rendering in both text modes; structure of the Inkscape
output (layers, guides, plugins, arcs, markers, clones, TexText).  The
feature fixture `svgall.sk` is generated by `test/formats/svgfixture.py`.
