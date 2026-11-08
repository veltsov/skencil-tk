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
# SVG import: images.
#
# Raster images (data: URIs or files) are embedded.  Sketch's image
# space has the origin at the lower left with the first pixel row at
# the top (y = height), so the SVG image space (y down) is flipped.

import base64
import io
import os
import urllib.parse

from Sketch import _, Trafo, Image, ImageData

from . import values
from .values import mul


def open_href(href, base_dir):
    """The bytes and the media type (or None) of the image HREF."""
    href = href.strip()
    if href.startswith('data:'):
        header, _sep, data = href[5:].partition(',')
        parts = header.split(';')
        mime = parts[0].strip().lower() or None
        if 'base64' in [p.strip().lower() for p in parts[1:]]:
            data = base64.b64decode(''.join(data.split()) + '===')
        else:
            data = urllib.parse.unquote_to_bytes(data)
        return data, mime
    url = urllib.parse.urlparse(href)
    if url.scheme == 'file':
        path = urllib.parse.unquote(url.path)
    elif url.scheme and len(url.scheme) > 1:
        return None, None       # http: etc. are not fetched
    else:
        path = urllib.parse.unquote(href)
        if not os.path.isabs(path):
            path = os.path.join(base_dir or '', path)
    with open(path, 'rb') as f:
        data = f.read()
    mime = 'image/svg+xml' if path.lower().endswith(('.svg', '.svgz')) \
           else None
    return data, mime


def pil_image(data):
    from PIL import Image as PILImage
    image = PILImage.open(io.BytesIO(data))
    image.load()
    if image.mode in ('RGBA', 'LA', 'PA') or (image.mode in ('P', 'L', 'RGB')
                                             and 'transparency'
                                             in image.info):
        image = image.convert('RGBA')
    elif image.mode not in ('L', 'RGB'):
        image = image.convert('RGB')
    return image


def with_opacity(image, alpha):
    """IMAGE with its alpha multiplied by ALPHA."""
    if alpha >= 1.0:
        return image
    image = image.convert('RGBA')
    a = image.getchannel('A').point(lambda v: int(round(v * alpha)))
    image.putalpha(a)
    return image


def image_trafo(ctm, x, y, w, h, iw, ih, par):
    """The trafo of a Sketch image of IW x IH pixels shown in the box
    (X, Y, W, H) of user space."""
    from .builder import viewbox_transform
    m = mul(ctm, values.translate(x, y))
    m = mul(m, viewbox_transform((0, 0, iw, ih), par, w, h))
    return mul(m, (1.0, 0.0, 0.0, -1.0, 0.0, ih))


def image(builder, node, ctm, style, vp):
    if style['visibility'] in ('hidden', 'collapse'):
        return []
    href = node.href()
    if not href:
        return []
    try:
        data, mime = open_href(href, builder.base_dir)
    except (OSError, ValueError) as exc:
        builder.warn(_("Image %s not found") % href[:60])
        return []
    if data is None:
        builder.warn(_("Remote images ignored"))
        return []
    fs = style['font-size']
    x = values.length(node.get('x'), vp[0], fs, 0.0)
    y = values.length(node.get('y'), vp[1], fs, 0.0)
    if mime == 'image/svg+xml' or data[:5] in (b'<?xml', b'<svg ') \
       or data[:2] == b'\x1f\x8b':
        return svg_image(builder, node, data, ctm, style, vp, x, y)
    try:
        img = pil_image(data)
    except Exception:
        builder.warn(_("Images in an unknown format ignored"))
        return []
    iw, ih = img.size
    w = values.length(node.get('width'), vp[0], fs)
    h = values.length(node.get('height'), vp[1], fs)
    if w is None and h is None:
        w, h = float(iw), float(ih)
    elif w is None:
        w = h * iw / float(ih)
    elif h is None:
        h = w * ih / float(iw)
    if w <= 0 or h <= 0:
        return []
    img = with_opacity(img, style['_opacity'])
    if style['_opacity'] < 1:
        builder.note_opacity()
    par = node.get('preserveAspectRatio')
    m = image_trafo(ctm, x, y, w, h, iw, ih, par)
    obj = Image(ImageData(img), trafo = Trafo(*m))
    objects = [obj]
    from .builder import preserve_aspect_ratio
    align, slice = preserve_aspect_ratio(par)
    if align is not None and slice:
        objects = builder.clips.clip_rect(objects, ctm, x, y, w, h)
    return objects


def svg_image(builder, node, data, ctm, style, vp, x, y):
    """An SVG file referenced by an image: imported as a group."""
    from . import tree
    from .builder import Builder, viewbox_transform, parse_viewbox
    if data[:2] == b'\x1f\x8b':
        import gzip
        data = gzip.decompress(data)
    try:
        root = tree.parse(data)
    except Exception:
        builder.warn(_("Images in an unknown format ignored"))
        return []
    sub = Builder(root, builder.base_dir, builder.warn, builder.options)
    fs = style['font-size']
    viewbox = parse_viewbox(root.get('viewBox'))
    iw = values.length(root.get('width')) or (viewbox and viewbox[2]) or 100.0
    ih = values.length(root.get('height')) or (viewbox and viewbox[3]) \
         or 100.0
    w = values.length(node.get('width'), vp[0], fs) or iw
    h = values.length(node.get('height'), vp[1], fs) or ih
    m = mul(ctm, values.translate(x, y))
    m = mul(m, viewbox_transform((0, 0, iw, ih),
                                 node.get('preserveAspectRatio'), w, h))
    objects = sub.render_root(m, (iw, ih), style)
    if style['_opacity'] < 1:
        builder.warn(_("Opacity of SVG images ignored"))
    if len(objects) > 1:
        from Sketch import Group
        objects = [Group(objects)]
    return builder.clips.clip_rect(objects, ctm, x, y, w, h)
