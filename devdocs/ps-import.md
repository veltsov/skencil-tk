# EPS, PostScript and PDF Import

Status: intermediate implementation (stage C2 below).  The import
filter `Plugins/Filters/psloader.py` (`format_name` `PostScript/PDF`;
`.eps .ps .pdf .epsf .epsi`; magic `%!`, `%PDF-` or the binary header
of an EPS with a TIFF/WMF preview) only declares the package
`Plugins/Filters/Lib/psimport/`.  Placing an EPS as an opaque object
(`EpsImage`, File → Load Raster/EPS Image) is unchanged.

## Pipeline

1. **Probe** (`psimport.Source`): PDF is used as it is.  PostScript is
   converted to PDF by ghostscript (`pdfwrite`, `-dSAFER`, through
   `util.ghostscript_command()`).  EPS likewise:
   - the page is the bounding box from `dscparser` (also a trailing
     `(atend)` one, which `-dEPSCrop` ignores);
   - translated by an `/Install` procedure;
   - an EPS with a binary header is cut to its PostScript section first.

   `pdfinfo` gives the page sizes.
2. **Pages**: the import option `pages` (a text: `1`, `2-4`, `1,3,5-`,
   `all`; `parse_pages`).  A file of one page ignores it and asks
   nothing.
3. **Convert** each selected page with `pdftocairo -svg -f N -l N`
   (poppler/cairo), which crops to the CropBox.
4. **Import** the SVG with svgimport (`devdocs/svg-import.md`), so
   these come from there:
   - glyphs come out as curves (cairo's `<symbol>`/`<use>`);
   - gradients, clips (cairo nests them as groups) and images with
     alpha are mapped;
   - opacity is blended with white;
   - nonzero fills are made even-odd;
   - soft masks are flattened on images.
   Then a repair (`drop_snapped_image_clips`):
   - poppler aligns the bounds of an image to whole device pixels by a
     rectangular clip (rounded image bounds ∩ the PDF's clip);
   - in SVG output a device pixel is one point, so images tiled with
     overlapping clips (a figure split into several images) get white
     gaps of up to half a point between the tiles;
   - a rectangular clip around a single image (through nested clips)
     whose edges are all within 1 pt of the image's own bounds is
     therefore dropped.  It only aligns, or trims a fraction of a
     point.
5. **Assemble**: one selected page gives an ordinary document with the
   page's size.  With several pages:
   - each page is one layer `Page N` in the document of the first one
     (its size is the document's);
   - the layers lie on top of each other, their top left corners
     aligned (pages of different sizes are reported);
   - Insert Document places a group of page groups.

API (UI-free):

```python
from Sketch.Plugins.Filters.Lib import psimport
doc = psimport.import_ps(source, pages = '1')   # file name, bytes or file
group, messages = psimport.import_ps_group(source, pages = '1')
```

Errors raise `SketchLoadError`:
- a missing tool is named together with its package (ghostscript,
  poppler-utils);
- a failed tool contributes the tail of its error output;
- every call has a 120 s timeout;
- the temporary files are removed even when the import is abandoned.

Requirements: ghostscript for PostScript/EPS, `pdftocairo` and
`pdfinfo` (poppler-utils) always.  The AppImage bundles ghostscript
but not poppler; there the filter works only with a system poppler.

## Import options

The filter declares `#parameters = (('pages', 'text', '1', (20, 1),
'Pages'),)`.  The generic machinery, for any import plugin:
- `ImportInfo` parameters, `GetOptions`, and `last_options` for the
  session;
- `GenericLoader.options` and `OptionInfo()`;
- `load_drawing(filename, options, ask_options)`, with
  `SketchLoadCancelled` when cancelled;
- `plugindlg.ImportOptionsDlg`;
- `skconvert -i NAME=VALUE` and `--input-options`.

`devdocs/architecture.md` (Plugins) has the details.

## Why this pipeline: the approaches compared

Measured before the implementation (ghostscript 9.55).  Each test file
was imported, rendered through `sk2ps` and ghostscript, and compared
with ghostscript's rendering of the original (fraction of differing
pixels).  The test files:
- a feature EPS with axial and radial `shfill`, text, a dash, CMYK and
  an inline `colorimage`;
- a cairo EPS with nested clips;
- MATLAB and Grace EPS.

| Approach | Result |
|---|---|
| A. Instrumenting ghostscript (redefining the painting operators, as pstoedit does) | Works for `fill`/`clip`/`show`/`shfill` under `-dSAFER`, but operators such as `rectfill`, `rectclip` and `colorimage` bypass redefinitions; complete coverage means re-implementing pstoedit's flattener.  PDF fails with gs ≥ 9.56: its C PDF interpreter (pdfi) never calls the PostScript operators. |
| B. pstoedit `-f sk` | No clipping at all (cairo, MATLAB output wrong), shadings flattened; failed on the inline image; PDF only with gs ≤ 9.55 (see `latextext.pstoedit_can_pdf`). |
| C1. dvisvgm `-E` / `--pdf`, then svgimport | Shadings silently dropped (25 % of the feature EPS differ); images JPEG unless `--bitmap-format=png`; EPS only; `--pdf` of 2.x depends on gs's old PDF interpreter. |
| **C2. gs pdfwrite → pdftocairo → svgimport** (implemented) | ≤ 0.17 % on every file; any gs version (pdfwrite is an output device); about 300 lines.  Costs: poppler/cairo as a dependency (not in the AppImage); font names lost; mesh shadings rasterized by cairo; output depends on the cairo version. |
| D. gs pdfwrite `-dNoOutputFonts` → own PDF reader | The planned replacement, see below. |
| Inkscape's EPS/PDF import | Loses clipped lines (see `devdocs/svg-export.md`, EPS). |

## Stage D (planned): a reader of ghostscript-normalized PDF

The resulting PDF is very simple:
- text becomes outline paths;
- shadings stay exact dictionaries with their functions;
- only a few content operators remain.

That holds for any ghostscript version.  The plan is to replace the
pdftocairo stage inside `psimport`, keeping the API and the options:
- `pdfwrite -dNoOutputFonts -dCompressPages=false
  -sColorConversionStrategy=RGB`, with lossless image filters;
- a reader for:
  - objects and xref, including xref and object streams;
  - Flate/DCT;
  - content operators and the graphics state;
  - functions of types 0, 2, 3 and 4;
  - Form XObjects, tiling patterns, inline images;
  - ExtGState opacity and `SMask`;
- the helpers shared with svgimport factored out (blend, fill rule,
  gradient mapping, clips, tile copies).

Gains:
- only the bundled ghostscript is needed;
- shadings map exactly onto Sketch's gradients;
- Optional Content Groups can become layers;
- later, base-35 fonts can become real text.

## Tests

`test/formats/test_psimport.py` (skipped without ghostscript or
poppler-utils):
- the generated feature EPS and its binary-header variant;
- `oms.eps` (trailing bounding box) and the MATLAB EPS when present;
- a generated 3-page PS with two page sizes: each page, pages as
  layers, alignment;
- pdflatex output;
- the plugin options through `load_drawing`, a gzipped file, a missing
  pdftocairo, and `skconvert -i`.

`test/model/test_import_options.py` covers the generic options with a
stub plugin.  `test/ui/test_smoke.py::test_import_options_dialog`
covers the dialog in File → Open and Insert Document: OK, Cancel and
the page layers.
