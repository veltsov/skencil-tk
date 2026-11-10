# Layer 1: the "Extract Image" and "Replace Image" scripts
# (Sketch.Scripts.image_tools): finding the image of the selection in
# groups and mask groups, extracting it to a file and replacing it.


import os

import PIL.Image
import pytest

import testsupport


def write_png(path, size=(8, 6), color=(255, 0, 0), mode='RGB'):
    PIL.Image.new(mode, size, color).save(path)
    return str(path)


@pytest.fixture(autouse=True)
def clear_cache():
    # the external data cache is global: start every test afresh
    testsupport.sketch()
    from Sketch.Graphics import external
    external.instance_cache.clear()
    yield
    external.instance_cache.clear()


def embedded(size=(8, 6), color=(255, 0, 0), mode='RGB'):
    from Sketch.Graphics.image import ImageData
    return ImageData(PIL.Image.new(mode, size, color))


def image(data, x=0):
    from Sketch import Trafo
    from Sketch.Graphics.image import Image
    return Image(data, trafo=Trafo(1, 0, 0, 1, x, 0))


def rectangle(x=0, data=None):
    from Sketch import Rectangle, Trafo, ImageTilePattern
    rect = Rectangle(Trafo(50, 0, 0, 40, x, 0))
    if data is not None:
        rect.SetProperties(fill_pattern=ImageTilePattern(data))
    return rect


def document(obj):
    from Sketch import EditDocument
    doc = EditDocument(create_layer=1)
    doc.Insert(obj)
    doc.SelectObject(obj)
    return doc


def masked(obj):
    # OBJ clipped by a small rectangle, in a group with another shape
    from Sketch import Rectangle, Trafo, Group
    from Sketch.Graphics.maskgroup import MaskGroup
    mask = Rectangle(Trafo(3, 0, 0, 2, 1, 1))
    return Group([rectangle(100), MaskGroup([mask, obj])])


# ------------------------------------------------------------ selection

def test_target_single_image():
    from Sketch.Scripts.image_tools import target_image
    img = image(embedded())
    assert target_image(document(img)) == (img, None)


def test_target_image_fill():
    from Sketch.Scripts.image_tools import target_image
    rect = rectangle(data=embedded())
    user, owner = target_image(document(rect))
    assert owner is rect and user is rect.Properties().fill_pattern


@pytest.mark.parametrize('pattern', [0, 1])
def test_target_in_groups(pattern):
    from Sketch.Scripts.image_tools import target_image
    obj = rectangle(data=embedded()) if pattern else image(embedded())
    user, owner = target_image(document(masked(obj)))
    if pattern:
        assert owner is obj
    else:
        assert user is obj and owner is None


@pytest.mark.parametrize('objects', ['two images', 'image and fill',
                                     'no image'])
def test_target_ambiguous(objects):
    from Sketch import Group
    from Sketch.Scripts.image_tools import target_image
    objects = {'two images': [image(embedded()), image(embedded(), 20)],
               'image and fill': [image(embedded()),
                                  rectangle(data=embedded())],
               'no image': [rectangle(), rectangle(60)]}[objects]
    assert target_image(document(masked(Group(objects)))) is None


def test_target_multiple_selection():
    from Sketch.Base.const import SelectSet
    from Sketch.Scripts.image_tools import target_image
    img1, img2 = image(embedded()), image(embedded(), 20)
    doc = document(img1)
    doc.Insert(img2)
    doc.SelectObject([img1, img2], SelectSet)
    assert target_image(doc) is None


# ------------------------------------------------------------- extract

def test_extract_embedded_unclipped(tmp_path):
    from Sketch.Scripts.image_tools import target_image, extract_image
    doc = document(masked(image(embedded((30, 20), (1, 2, 3)))))
    user, owner = target_image(doc)
    out = str(tmp_path / 'out.png')
    extract_image(user.Data(), out)
    with PIL.Image.open(out) as result:
        assert result.size == (30, 20)
        assert result.convert('RGB').getpixel((29, 19)) == (1, 2, 3)


def test_extract_rgba_as_jpeg(tmp_path):
    from Sketch.Scripts.image_tools import extract_image
    out = str(tmp_path / 'out.jpg')
    extract_image(embedded(mode='RGBA', color=(0, 0, 255, 128)), out)
    with PIL.Image.open(out) as result:
        assert result.format == 'JPEG' and result.mode == 'RGB'


def test_extract_linked_copies_file(tmp_path):
    from Sketch.Graphics.image import load_image
    from Sketch.Scripts.image_tools import extract_image
    src = write_png(tmp_path / 'src.png')
    out = str(tmp_path / 'out.png')
    extract_image(load_image(src), out)
    assert open(out, 'rb').read() == open(src, 'rb').read()
    # another format is converted
    out = str(tmp_path / 'out.bmp')
    extract_image(load_image(src), out)
    with PIL.Image.open(out) as result:
        assert result.format == 'BMP' and result.size == (8, 6)


def test_extract_errors(tmp_path):
    from Sketch import SketchError
    from Sketch.Graphics.image import MissingImageData
    from Sketch.Scripts.image_tools import extract_image
    with pytest.raises(SketchError):
        extract_image(embedded(), str(tmp_path / 'out.unknown'))
    with pytest.raises(SketchError):
        extract_image(MissingImageData(str(tmp_path / 'gone.png')),
                      str(tmp_path / 'out.png'))


def test_save_filetypes():
    from Sketch.Scripts.image_tools import save_filetypes
    types = save_filetypes()
    assert types[0][0] == 'PNG' and '.png' in types[0][1]
    assert 'JPEG' in [name for name, ext in types]


# ------------------------------------------------------------- replace

@pytest.mark.parametrize('linked', [0, 1])
def test_replace_image_in_mask_group(tmp_path, linked):
    from Sketch.Graphics.image import load_image
    from Sketch.Scripts.image_tools import target_image, replace_image
    if linked:
        data = load_image(write_png(tmp_path / 'old.png'))
    else:
        data = embedded()
    img = image(data, 7)
    doc = document(masked(img))
    parent, index = img.parent, img.parent.GetObjects().index(img)
    trafo = img.trafo
    new = write_png(tmp_path / 'new.png', size=(11, 13), color=(0, 255, 0))
    replace_image(doc, target_image(doc), new)
    assert img.parent is parent and parent.GetObjects()[index] is img
    assert img.trafo == trafo
    assert img.Data().Size() == (11, 13)
    assert img.Data().IsLinked() == bool(linked)
    if linked:
        assert img.Data().Filename() == new
    doc.Undo()
    assert img.Data() is data


def test_replace_image_fill(tmp_path):
    from Sketch.Scripts.image_tools import target_image, replace_image
    data = embedded()
    rect = rectangle(data=data)
    doc = document(masked(rect))
    new = write_png(tmp_path / 'new.png', size=(11, 13))
    replace_image(doc, target_image(doc), new)
    new_data = rect.Properties().fill_pattern.Data()
    assert new_data.Size() == (11, 13) and new_data.IsEmbedded()
    doc.Undo()
    assert rect.Properties().fill_pattern.Data() is data
