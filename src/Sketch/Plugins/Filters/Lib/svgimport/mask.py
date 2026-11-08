# Sketch - A Python-based interactive drawing program
# Copyright (C) 2026 by Vladimir Eltsov
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Library General Public
# License as published by the Free Software Foundation; either
# version 2 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Library General Public License for more details.
#
# You should have received a copy of the GNU Library General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
# SVG import: masks.
#
# Sketch has no soft masks.  Two cases can be represented:
#
# - the masked element is a single raster image: the mask is computed
#   on the image's pixel grid and multiplied into the image's alpha
#   channel (the mask content is rasterized here: images, and shapes
#   with solid or gradient fills);
# - the mask content is opaque white shapes: it is a clip path.
#
# Otherwise the element is drawn unmasked.
#
# The mask content is rendered by the builder with opacity blended
# toward black: the value of a mask is the luminance of its content
# composited over transparent black, i.e. luminance times alpha.

import math

from Sketch import _, Trafo, Image, ImageData, PolyBezier

from . import values, paint, fillrule
from .values import mul

# supersampling of the rasterized shapes
OVERSAMPLE = 4

# the pixel limit of a rasterized mask
MAX_PIXELS = 16000000


def luminance(rgb):
    r, g, b = rgb[:3]
    return 0.2125 * r + 0.7154 * g + 0.0721 * b


def leaves(objects):
    for obj in objects:
        if obj.is_Group and not obj.is_MaskGroup:
            for leaf in leaves(obj.GetObjects()):
                yield leaf
        else:
            yield obj


def image_matrix(obj):
    """The matrix of an Image object from (column, row) pixel
    coordinates (row 0 at the top) to the document."""
    w, h = obj.data.Size()
    return mul(obj.trafo.coeff(), (1.0, 0.0, 0.0, -1.0, 0.0, h))


class Raster:

    """A mask on the pixel grid MATRIX (pixel -> document) of SIZE."""

    def __init__(self, matrix, size):
        from PIL import Image as PILImage
        self.matrix = matrix
        self.inverse = values.inverse(matrix)
        self.size = size
        self.image = PILImage.new('L', size, 0)
        self.warnings = set()

    def paint(self, objects):
        for obj in leaves(objects):
            if obj.is_Image:
                self.paint_image(obj)
            elif obj.is_MaskGroup:
                self.warnings.add(_("Clipping within masks ignored"))
                self.paint(obj.GetObjects()[1:])
            elif obj.has_fill:
                self.paint_shape(obj)
            if obj.has_line and obj.Properties().HasLine():
                self.warnings.add(_("Lines in masks ignored"))

    def paint_image(self, obj):
        from PIL import Image as PILImage
        source = obj.data.Image()
        inv = values.inverse(image_matrix(obj))
        if inv is None:
            return
        # target pixel -> source pixel
        a, b, c, d, e, f = mul(inv, self.matrix)
        data = (a, c, e, b, d, f)
        if source.mode == 'RGBA':
            alpha = source.getchannel('A')
            source = source.convert('RGB')
        else:
            alpha = None
        lum = source.convert('L')
        lum = lum.transform(self.size, PILImage.AFFINE, data,
                            PILImage.BILINEAR)
        cover = PILImage.new('L', source.size, 255) if alpha is None \
                else alpha
        cover = cover.transform(self.size, PILImage.AFFINE, data,
                                PILImage.BILINEAR)
        self.image = PILImage.composite(lum, self.image, cover)

    def coverage(self, obj):
        """The antialiased even-odd coverage of OBJ's fill as an 'L'
        image (None if empty)."""
        from PIL import Image as PILImage, ImageDraw, ImageChops
        from .clip import subpaths_of
        w, h = self.size
        big = (w * OVERSAMPLE, h * OVERSAMPLE)
        inv = mul(values.scale(OVERSAMPLE), self.inverse)
        result = None
        for sub in subpaths_of(obj):
            pts = [values.apply(inv, x, y) for x, y in fillrule.flatten(sub)]
            if len(pts) < 3:
                continue
            layer = PILImage.new('1', big, 0)
            ImageDraw.Draw(layer).polygon(pts, fill = 1)
            result = layer if result is None \
                     else ImageChops.logical_xor(result, layer)
        if result is None:
            return None
        return result.convert('L').resize(self.size, PILImage.BOX)

    def paint_shape(self, obj):
        from PIL import Image as PILImage
        pattern = obj.Properties().fill_pattern
        if pattern.is_Empty:
            return
        cover = self.coverage(obj)
        if cover is None:
            return
        if pattern.is_Solid:
            c = pattern.Color()
            value = int(round(255 * luminance((c.red, c.green, c.blue))))
            fill = PILImage.new('L', self.size, value)
        elif pattern.is_AxialGradient or pattern.is_RadialGradient:
            fill = self.gradient(obj, pattern)
        else:
            self.warnings.add(_("Patterns in masks drawn in a solid color"))
            fill = PILImage.new('L', self.size, 128)
        self.image = PILImage.composite(fill, self.image, cover)

    def gradient(self, obj, pattern):
        """The luminance of a Sketch gradient over the raster."""
        from PIL import Image as PILImage
        rect = obj.bounding_rect
        gradient = pattern.Gradient()
        lut = []
        for i in range(256):
            c = gradient.ColorAt(i / 255.0)
            lut.append(int(round(255 * luminance((c.red, c.green, c.blue)))))
        w = rect.right - rect.left
        h = rect.top - rect.bottom
        cx = (rect.left + rect.right) / 2
        cy = (rect.bottom + rect.top) / 2
        if pattern.is_AxialGradient:
            # t = 0.5 - ((p - c) . dir) / extent, see gradient.py
            dx, dy = pattern.Direction()
            extent = (w * abs(dx) + h * abs(dy)) * (1 - pattern.Border())
            if extent <= 0:
                return PILImage.new('L', self.size, lut[0])
            # t as a function of the target pixel, scaled to 0..255
            m = self.matrix
            ga = -(dx * m[0] + dy * m[1]) / extent
            gb = -(dx * m[2] + dy * m[3]) / extent
            g0 = 0.5 - (dx * (m[4] - cx) + dy * (m[5] - cy)) / extent
            # a ramp sampled through an affine transform; outside 0..1
            # the gradient is padded (the ramp is padded by 256 pixels
            # on both sides)
            ramp = PILImage.new('L', (256 * 3, 1))
            ramp.putdata([lut[0]] * 256 + lut + [lut[-1]] * 256)
            data = (255 * ga, 255 * gb, 255 * g0 + 256, 0, 0, 0.5)
            return ramp.transform(self.size, PILImage.AFFINE, data,
                                  PILImage.BILINEAR)
        # radial: t = 1 - |p - c| / radius
        px, py = pattern.Center()
        cx = rect.left + px * w
        cy = rect.bottom + py * h
        radius = max(math.hypot(x - cx, y - cy) for x in (rect.left,
                                                          rect.right)
                     for y in (rect.bottom, rect.top)) \
                 * (1 - pattern.Border())
        if radius <= 0:
            return PILImage.new('L', self.size, lut[-1])
        width, height = self.size
        result = PILImage.new('L', self.size)
        pixels = []
        m = self.matrix
        for j in range(height):
            for i in range(width):
                x, y = values.apply(m, i + 0.5, j + 0.5)
                t = 1 - math.hypot(x - cx, y - cy) / radius
                pixels.append(lut[min(max(int(t * 255 + 0.5), 0), 255)])
        result.putdata(pixels)
        return result


class Masker:

    def __init__(self, builder):
        self.builder = builder

    def content(self, mask, ctm, objects, style):
        """Render the content of the mask element MASK for OBJECTS (the
        rendered masked element, for objectBoundingBox units)."""
        b = self.builder
        m = ctm
        if mask.get('maskContentUnits') == 'objectBoundingBox':
            box = b.clips.user_bbox(objects, ctm)
            if box is None:
                return []
            l, bt, r, t = box
            m = mul(ctm, (r - l, 0.0, 0.0, t - bt, l, bt))
        mstyle = b.tree_style(mask)
        saved = b.background
        b.background = paint.BLACK
        b.use_stack.append(mask)
        try:
            return b.children(mask, m, mstyle, b.current_vp)
        finally:
            b.use_stack.pop()
            b.background = saved

    def region(self, mask, ctm, objects, style):
        """The mask region as (matrix, w, h): the unit square mapped by
        MATRIX in the document, or None."""
        b = self.builder
        fs = style['font-size']
        if mask.get('maskUnits') == 'userSpaceOnUse':
            vp = b.current_vp
            x = values.length(mask.get('x', '-10%'), vp[0], fs, 0.0)
            y = values.length(mask.get('y', '-10%'), vp[1], fs, 0.0)
            w = values.length(mask.get('width', '120%'), vp[0], fs, 0.0)
            h = values.length(mask.get('height', '120%'), vp[1], fs, 0.0)
        else:
            box = b.clips.user_bbox(objects, ctm)
            if box is None:
                return None
            l, bt, r, t = box
            def frac(name, default):
                value = mask.get(name, default).strip()
                if value.endswith('%'):
                    return float(value[:-1]) / 100
                return float(values.numbers(value)[0])
            x = l + frac('x', '-10%') * (r - l)
            y = bt + frac('y', '-10%') * (t - bt)
            w = frac('width', '120%') * (r - l)
            h = frac('height', '120%') * (t - bt)
        if w <= 0 or h <= 0:
            return None
        return mul(ctm, (w, 0.0, 0.0, h, x, y))

    def apply(self, node, objects, ctm, style, vp):
        b = self.builder
        mask = b.lookup(values.url_id(style['mask']))
        if mask is None or mask.tag != 'mask':
            b.warn(_("Reference to an unknown mask ignored"))
            return objects
        if mask in b.use_stack:
            b.warn(_("Recursive references ignored"))
            return objects
        content = self.content(mask, ctm, objects, style)
        region = self.region(mask, ctm, objects, style)
        alpha_mask = (b.tree_style(mask).get('mask-type') == 'alpha')
        masked = list(leaves(objects))
        if len(masked) == 1 and masked[0].is_Image and not alpha_mask:
            result = self.flatten(masked[0], content, region)
            if result is not None:
                return self.replace(objects, masked[0], result)
        clip = self.as_clip(content, alpha_mask)
        if clip is not None:
            return b.clips.clip(objects, clip)
        b.warn(_("Masks ignored (drawn unmasked)"))
        return objects

    def replace(self, objects, old, new):
        """OBJECTS with the leaf OLD replaced by NEW."""
        for i, obj in enumerate(objects):
            if obj is old:
                objects[i] = new
                return objects
            if obj.is_Group and not obj.is_MaskGroup:
                children = obj.GetObjects()
                self.replace(children, old, new)
                new.parent = obj
        return objects

    def flatten(self, obj, content, region):
        """OBJ (an Image) with the mask multiplied into its alpha."""
        from PIL import Image as PILImage, ImageChops
        b = self.builder
        w, h = obj.data.Size()
        if w * h > MAX_PIXELS:
            return None
        raster = Raster(image_matrix(obj), (w, h))
        raster.paint(content)
        for warning in raster.warnings:
            b.warn(warning)
        mask = raster.image
        if region is not None:
            # outside the mask region the mask is 0
            from .clip import empty_properties
            from Sketch import Rectangle
            rect = Rectangle(Trafo(*region), properties = empty_properties())
            rect.SetProperties(fill_pattern = paint.solid((1, 1, 1)))
            cover = Raster(image_matrix(obj), (w, h)).coverage(rect)
            if cover is not None:
                mask = ImageChops.multiply(mask, cover)
        image = obj.data.Image()
        if image.mode != 'RGBA':
            image = image.convert('RGBA')
        image.putalpha(ImageChops.multiply(image.getchannel('A'), mask))
        result = Image(ImageData(image), trafo = obj.trafo)
        b.warn(_("Masked images flattened (alpha)"))
        return result

    def as_clip(self, content, alpha_mask):
        """A clip object for mask CONTENT of opaque white (or, for alpha
        masks, opaque) shapes; None if the mask is not of that kind."""
        b = self.builder
        shapes = list(leaves(content))
        if not shapes:
            return None
        groups = []
        from .clip import subpaths_of, empty_properties
        for obj in shapes:
            if obj.is_Image or obj.is_MaskGroup or not obj.has_fill:
                return None
            pattern = obj.Properties().fill_pattern
            if not pattern.is_Solid:
                return None
            c = pattern.Color()
            if not alpha_mask and luminance((c.red, c.green, c.blue)) < 0.99:
                return None
            if alpha_mask and (c.red, c.green, c.blue) == (0, 0, 0):
                # cannot tell transparent from black after blending
                return None
            groups.append((subpaths_of(obj), 'evenodd'))
        subs = fillrule.even_odd_equivalent(None, None, b.warn,
                                            groups = groups)
        from .builder import make_path
        paths = tuple(make_path(sub) for sub in subs
                      if sub.segments and not sub.is_degenerate())
        if not paths:
            return None
        return PolyBezier(paths = paths, properties = empty_properties())
