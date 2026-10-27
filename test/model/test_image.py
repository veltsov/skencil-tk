# Layer 1: headless tests for the internal raster image representation
# (RasterImage/ImageData) and the buffer-protocol image functions of
# the _sketch C module (skimage.c).  No display required.


import os
import tempfile

import PIL.Image
import pytest

import testsupport


def sketch():
    return testsupport.sketch()


def rastmodule():
    sketch()
    from Sketch.Graphics import image
    return image


# ----------------------------------------------------- representation

def test_rasterimage_default_fill():
    im = rastmodule().RasterImage('RGB', (3, 2))
    assert im.mode == 'RGB'
    assert im.size == (3, 2)
    # RGB is 4 bytes per pixel
    assert len(im.data) == 3 * 2 * 4
    assert im.data == b'\x00' * (3 * 2 * 4)

    white = rastmodule().RasterImage('RGB', (3, 2), fill=255)
    assert white.data == b'\xff' * (3 * 2 * 4)

    gray = rastmodule().RasterImage('L', (3, 2))
    # L is one byte per pixel
    assert len(gray.data) == 3 * 2


def test_image_from_to_pil_roundtrip():
    mod = rastmodule()
    for mode in ('L', 'RGB', 'RGBA'):
        # a pattern that differs in every byte position
        if mode == 'L':
            pil = PIL.Image.new(mode, (4, 3))
            pil.putdata(range(12))
        else:
            pil = PIL.Image.new(mode, (4, 3), (1, 2, 3, 4)[:len(mode)])
        data = mod.image_from_pil(pil)
        assert data[0] == mode
        assert data[1] == (4, 3)
        back = mod.image_to_pil(*data)
        assert back.mode == mode
        assert back.size == (4, 3)
        assert back.tobytes() == pil.tobytes()


def test_image_from_pil_keeps_alpha():
    mod = rastmodule()
    pil = PIL.Image.new('RGBA', (2, 2), (10, 20, 30, 40))
    mode, size, data = mod.image_from_pil(pil)
    assert mode == 'RGBA'
    # the alpha channel must not be discarded
    assert data[3] == 40
    assert data[7] == 40


def test_image_from_pil_converts_other_modes():
    mod = rastmodule()
    pil = PIL.Image.new('1', (2, 2), 1)
    mode, size, data = mod.image_from_pil(pil)
    assert mode == 'L'
    assert len(data) == 4

    pil = PIL.Image.new('P', (2, 2))
    mode, size, data = mod.image_from_pil(pil)
    assert mode == 'RGB'
    assert len(data) == 2 * 2 * 4


def test_imagedata_from_pil():
    mod = rastmodule()
    pil = PIL.Image.new('RGBA', (2, 3), (10, 20, 30, 40))
    data = mod.ImageData(pil)
    assert data.mode == 'RGBA'
    assert data.size == (2, 3)
    assert data.Size() == (2, 3)
    assert len(data.data) == 2 * 3 * 4
    assert data.data[3] == 40
    assert data.info == {}
    # the IO-boundary PIL round trip must reproduce the pixels
    pil2 = data.Image()
    assert pil2.mode == 'RGBA'
    assert pil2.tobytes() == pil.tobytes()


def test_imagedata_from_rasterimage_shares_data():
    mod = rastmodule()
    raster = mod.RasterImage('RGB', (2, 2), fill=7)
    data = mod.ImageData(raster)
    assert data.data is raster.data


def test_imagedata_convert_and_invert():
    mod = rastmodule()
    pil = PIL.Image.new('RGB', (2, 2), (10, 20, 30))
    data = mod.ImageData(pil)
    gray = data.Convert('L')
    assert gray.mode == 'L'
    assert gray.size == (2, 2)
    assert data.Convert('RGB') is data
    inv = data.Invert()
    assert inv.mode == 'RGB'
    assert inv.size == (2, 2)
    # inverted pixels: 255 - value (via the PIL round trip)
    assert inv.data[0] == 255 - 10
    assert inv.data[1] == 255 - 20
    assert inv.data[2] == 255 - 30


def gradient_args():
    # gradient_from_list accepts (pos, color) tuples with plain
    # rgb-float tuples as colors
    return [(0.0, (1.0, 0.0, 0.0)), (1.0, (0.0, 0.0, 1.0))]


# --------------------------------------------------- _sketch functions

def test_fill_axial_gradient_horizontal():
    from Sketch.Modules import _sketch
    mod = rastmodule()
    im = mod.RasterImage('RGB', (5, 3))
    buf = bytearray(im.data)
    _sketch.fill_axial_gradient(buf, 'RGB', 5, 3, gradient_args(),
                                0, 0, 4, 0)
    # row 0 is filled and copied to the other rows; t = x / (x1 - x0)
    # (only bytes 0..2 of each pixel are written, the padding byte is
    # left at its fill value 0)
    assert bytes(buf[0:4]) == b'\xff\x00\x00\x00'      # red
    assert buf[4] < 255				# blending
    assert bytes(buf[16:20]) == b'\x00\x00\xff\x00'    # blue
    assert bytes(buf[20:24]) == bytes(buf[0:4])	# row copies


def test_fill_radial_gradient():
    from Sketch.Modules import _sketch
    mod = rastmodule()
    w = h = 5
    im = mod.RasterImage('RGB', (w, h))
    buf = bytearray(im.data)
    _sketch.fill_radial_gradient(buf, 'RGB', w, h, gradient_args(),
                                 2, 2, 0, 3)
    # center pixel is the first gradient color
    center = 4 * (2 + 2 * w)
    assert bytes(buf[center:center + 3]) == b'\xff\x00\x00'


def test_fill_conical_gradient():
    from Sketch.Modules import _sketch
    mod = rastmodule()
    w = h = 7
    im = mod.RasterImage('RGB', (w, h))
    buf = bytearray(im.data)
    _sketch.fill_conical_gradient(buf, 'RGB', w, h, gradient_args(),
                                  3, 3, 0.0)
    # the pixel right of the center has t = 0 (first color), the pixel
    # left of it t = 1 (last color)
    right = 4 * (4 + 3 * w)
    left = 4 * (2 + 3 * w)
    assert bytes(buf[right:right + 3]) == b'\xff\x00\x00'
    assert bytes(buf[left:left + 3]) == b'\x00\x00\xff'


def test_fill_hsv_z():
    from Sketch.Modules import _sketch
    mod = rastmodule()
    w, h = 4, 3
    im = mod.RasterImage('RGB', (w, h))
    buf = bytearray(im.data)
    _sketch.fill_hsv_z(buf, 'RGB', w, h, 2, (0.0, 0.0, 1.0))
    # value ramps from 1.0 in the top row to 0.0 in the bottom row
    top = 0
    bottom = 4 * (w * (h - 1))
    assert bytes(buf[top:top + 3]) == b'\xff\xff\xff'
    assert bytes(buf[bottom:bottom + 3]) == b'\x00\x00\x00'


def test_fill_transformed_tile():
    from Sketch import Trafo
    from Sketch.Modules import _sketch
    mod = rastmodule()
    w, h = 4, 1
    im = mod.RasterImage('RGB', (w, h))
    buf = bytearray(im.data)
    tiledata = (b'\xff\x00\x00\x00' + b'\x00\xff\x00\x00')
    _sketch.fill_transformed_tile(buf, 'RGB', w, h,
                                  tiledata, 'RGB', 2, 1,
                                  Trafo(1, 0, 0, 1, 0, 0))
    # the tile is repeated: A B A B
    assert bytes(buf[0:4]) == b'\xff\x00\x00\x00'
    assert bytes(buf[4:8]) == b'\x00\xff\x00\x00'
    assert bytes(buf[8:12]) == b'\xff\x00\x00\x00'
    assert bytes(buf[12:16]) == b'\x00\xff\x00\x00'


def test_write_ps_hex_rgb():
    from Sketch.Modules import _sketch
    # RGB: 4 bytes per pixel, every 4th byte (padding/alpha) is skipped
    data = (b'\x10\x20\x30\x00' + b'\xaa\xbb\xcc\xff')
    fd, name = tempfile.mkstemp()
    try:
        out = os.fdopen(fd, 'w')
        _sketch.write_ps_hex(data, 'RGB', 2, 1, out)
        out.close()
        with open(name) as f:
            assert f.read() == '102030AABBCC\n'
    finally:
        os.unlink(name)


def test_write_ps_hex_gray():
    from Sketch.Modules import _sketch
    fd, name = tempfile.mkstemp()
    try:
        out = os.fdopen(fd, 'w')
        _sketch.write_ps_hex(b'\x01\x02', 'L', 2, 1, out)
        out.close()
        with open(name) as f:
            assert f.read() == '0102\n'
    finally:
        os.unlink(name)


def test_buffer_errors():
    from Sketch.Modules import _sketch
    # wrong buffer size must raise ValueError, not crash
    with pytest.raises(ValueError):
        _sketch.fill_axial_gradient(bytearray(3), 'RGB', 5, 3,
                                    gradient_args(), 0, 0, 4, 0)
    # unsupported mode
    with pytest.raises(ValueError):
        _sketch.fill_axial_gradient(bytearray(60), 'P', 5, 3,
                                    gradient_args(), 0, 0, 4, 0)
    # read-only buffer for a fill (needs a writable buffer)
    with pytest.raises((TypeError, ValueError, BufferError)):
        _sketch.fill_axial_gradient(b'\x00' * 60, 'RGB', 5, 3,
                                    gradient_args(), 0, 0, 4, 0)


def test_imagedata_embed_save_reload_roundtrip(tmpdir):
    # an embedded image survives an .sk load/save/reload cycle with the
    # same pixels (exercises the PIL PNG codec boundary on both ends)
    import base64
    import io
    sketch()
    mod = rastmodule()
    pil = PIL.Image.new('RGB', (2, 2))
    pil.putpixel((0, 0), (255, 0, 0))
    pil.putpixel((1, 1), (0, 0, 255))
    png = io.BytesIO()
    pil.save(png, 'PNG')
    b64 = base64.encodebytes(png.getvalue()).decode("ascii")
    text = ('##Sketch 1 2\n'
            'document()\n'
            "layout('A4',0)\n"
            "layer('Layer 1',1,1,0,0,(0,0,0))\n"
            'bm(1)\n'
            + b64 +
            '-\n'
            'im((1,0,0,1,10,10),1)\n')
    path = str(tmpdir.join('img.sk'))
    with open(path, 'w') as f:
        f.write(text)
    doc2 = testsupport.load_document(path)
    images = [o for layer in doc2.layers for o in layer.objects
              if o.is_Image]
    assert len(images) == 1
    data = images[0].Data()
    assert data.mode == 'RGB'
    assert data.size == (2, 2)
    assert data.IsEmbedded()
    assert data.data[0:3] == b'\xff\x00\x00'
    assert data.data[12:15] == b'\x00\x00\xff'
    # saving again writes the embedded PNG back out and reloading
    # reproduces the same pixels
    out = str(tmpdir.join('img2.sk'))
    from Sketch.Base import plugins
    saver = plugins.find_export_plugin(plugins.guess_export_plugin('.sk'))
    saver(doc2, out)
    doc3 = testsupport.load_document(out)
    images3 = [o for layer in doc3.layers for o in layer.objects
               if o.is_Image]
    assert len(images3) == 1
    assert images3[0].Data().data == data.data
    assert images3[0].Data().mode == data.mode