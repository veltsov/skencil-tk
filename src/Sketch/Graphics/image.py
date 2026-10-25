# Sketch - A Python-based interactive drawing program
# Copyright (C) 1997, 1998, 1999, 2000 by Bernhard Herzog
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Library General Public
# License as published by the Free Software Foundation; either
# version 2 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.	See the GNU
# Library General Public License for more details.
#
# You should have received a copy of the GNU Library General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307	USA

# A simple graphics object that represents a pixel image.  The pixels
# are kept in an internal packed buffer (RasterImage/ImageData); PIL is
# used only to decode and encode image file formats at the IO
# boundaries (import filters, .sk embedded PNGs, EPS previews, and
# image operations off the display path).  The ExternalData baseclass
# maintains a cache of images to avoid having multiple copies of data
# in memory.
#

import os

import PIL.Image, PIL.ImageChops

from Sketch import _, RegisterCommands
from Sketch.UI.command import AddCmd

from Sketch.Graphics.external import ExternalData, get_cached, ExternalGraphics


# PIL 'raw' encoder/decoder names for the internal representation:
# RGB/RGBA are stored as four bytes per pixel (R, G, B and alpha or
# padding, in that byte order -- like PIL's internal layout and what
# the C display code in skimage.c expects), L as one byte per pixel.
# The alpha channel is always preserved; the current display treats
# RGBA like opaque RGB, but the data is kept for future transparency
# support.
_RAWMODE = {'L': 'L', 'RGB': 'RGBX', 'RGBA': 'RGBA'}


def image_from_pil(image):
    """Convert a PIL image into the internal representation,
    (mode, size, data).  Images of other modes are converted to L or
    RGB; an alpha channel, when present, is kept."""
    if image.mode not in _RAWMODE:
        mode = 'L' if image.mode == '1' else 'RGB'
        image = image.convert(mode)
    else:
        image.load()
    return image.mode, image.size, image.tobytes('raw', _RAWMODE[image.mode])


def image_to_pil(mode, size, data):
    """Convert the internal representation back into a PIL image (IO
    boundary: file encoding and PIL-based image operations off the
    display path)."""
    pil = PIL.Image.frombuffer(mode, size, data, 'raw', _RAWMODE[mode], 0, 1)
    if pil.mode != mode:
        # PIL's memory-mapping fast path returns the decoder's mode;
        # for RGB that is 'RGBX' (4 bytes per pixel with padding)
        pil = pil.convert(mode)
    return pil


class RasterImage(object):

    """A minimal internal raster image: a mode ('L', 'RGB' or 'RGBA'),
    a size (width, height) and the packed raw pixel data (see above).
    This is the internal payload of ImageData and is also used for the
    scratch images filled by the C display code (gradient fills, color
    dialog ramps, etc.)."""

    def __init__(self, mode, size, data = None, fill = 0):
        self.mode = mode
        self.size = size
        if data is None:
            bytes_per_pixel = 1 if mode == 'L' else 4
            # py2: str is bytes, so chr(fill) repeated is the raw data
            data = chr(fill) * (size[0] * size[1] * bytes_per_pixel)
        self.data = data

    def AsPILImage(self):
        """Return a PIL image for IO operations (boundary)."""
        return image_to_pil(self.mode, self.size, self.data)


class ImageData(ExternalData):

    attributes = {'mode':0, 'size':0, 'data':0, 'info':0}

    def __init__(self, image, filename = '', cache = 1):
        # IMAGE is either a RasterImage (the internal representation)
        # or a PIL image (the IO boundary, e.g. from the file loaders).
        if isinstance(image, RasterImage):
            self.mode = image.mode
            self.size = image.size
            self.data = image.data
            self.info = {}
        else:
            self.mode, self.size, self.data = image_from_pil(image)
            self.info = dict(getattr(image, 'info', None) or {})
        ExternalData.__init__(self, filename, cache)

    def AsEmbedded(self):
        if self.filename:
            return ImageData(RasterImage(self.mode, self.size, self.data))
        else:
            return self

    def Size(self):
        return self.size

    def Image(self):
        """Return a PIL image for IO operations (boundary)."""
        return image_to_pil(self.mode, self.size, self.data)

    def Resize(self, size):
        """Return a resized copy (PIL-based; used off the display path,
        e.g. for the PostScript image tile export)."""
        return RasterImage(*image_from_pil(self.Image().resize(size)))

    def Convert(self, mode):
        if mode != self.mode:
            return ImageData(self.Image().convert(mode))
        else:
            return self

    def Invert(self):
        return ImageData(PIL.ImageChops.invert(self.Image()))

    def new_from_file(self):
        return load_image(self.filename)



def load_image(filename, cache = 1):
    if isinstance(filename, (str, unicode)):
        image = get_cached(filename)
        if image:
            return image
    image = PIL.Image.open(filename)
    if not isinstance(filename, (str, unicode)):
        filename = ''
    return ImageData(image, filename = filename, cache = cache)

class Image(ExternalGraphics):

    is_Image = 1
    is_clip = 1

    commands = ExternalGraphics.commands[:]

    def __init__(self, image = None, imagefile = '', trafo = None,
                 duplicate = None):
        if duplicate is None:
            if not image:
                if not imagefile:
                    raise ValueError('Image must be instantiated with'\
                          ' either image or imagefile')
                image = load_image(imagefile)
        ExternalGraphics.__init__(self, image, trafo,
                                  duplicate = duplicate)

    def DrawShape(self, device, rect = None, clip = 0):
        device.DrawImage(self.data, self.trafo, clip)

    def Info(self):
        width, height = self.data.Size()
        x, y = self.trafo.offset()
        if self.IsEmbedded():
            return _("Embedded Image %(width)d x %(height)d "
                     "at (%(x)d, %(y)d)") % locals()
        else:
            filename = os.path.basename(self.data.Filename())
            return _("Linked Image `%(filename)s' %(width)d x %(height)d "
                     "at (%(x)d, %(y)d)") % locals()

    def SaveToFile(self, file):
        file.Image(self.data, self.trafo)

    def Embed(self):
        return self.SetData(self.data.AsEmbedded())
    AddCmd(commands, 'EmbedImage', _("Embed Image"), Embed,
           sensitive_cb = 'IsLinked')

    def CallImageFunction(self, function, args = ()):
        if type(args) != type(()):
            args = (args,)
        data = getattr(self.data, function)(*args)
        return self.SetData(data)
    AddCmd(commands, 'GrayscaleImage', _("Grayscale Image"),
           CallImageFunction, args = ('Convert', 'L'))
    AddCmd(commands, 'InvertImage', _("Invert Image"), CallImageFunction,
           args = 'Invert')

    context_commands = ('EmbedImage', 'GrayscaleImage', 'InvertImage')

RegisterCommands(Image)

