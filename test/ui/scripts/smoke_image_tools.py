# --run-script payload: run the Extract Image and Replace Image scripts
# from the script registry on an image inside a mask group (the file
# dialogs are stubbed), check the results, then quit.

import os

import PIL.Image

import Sketch
import Sketch.Scripting
from Sketch import Trafo, Rectangle, Group
from Sketch.Graphics.image import Image, ImageData
from Sketch.Graphics.maskgroup import MaskGroup

app = Sketch.Base.main.application
win = app.main_window
doc = win.document
out_dir = os.environ['SKENCIL_TEST_OUT']
extracted = os.path.join(out_dir, 'extracted.png')
replacement = os.path.join(out_dir, 'replacement.png')
PIL.Image.new('RGB', (11, 13), (0, 255, 0)).save(replacement)

image = Image(ImageData(PIL.Image.new('RGB', (30, 20), (1, 2, 3))),
              trafo = Trafo(1, 0, 0, 1, 10, 10))
mask = MaskGroup([Rectangle(Trafo(5, 0, 0, 5, 12, 12)), image])
group = Group([Rectangle(Trafo(20, 0, 0, 20, 100, 100)), mask])
doc.Insert(group)
doc.SelectObject(group)

app.GetSaveFilename = lambda **kw: extracted
app.GetOpenFilename = lambda **kw: replacement

# Script.execute reports errors instead of raising: check the results
Sketch.Scripting.Registry.registry['extract_image'].Execute()
with PIL.Image.open(extracted) as result:
    assert result.size == (30, 20), result.size

Sketch.Scripting.Registry.registry['replace_image'].Execute()
assert image.parent is mask and image.Data().Size() == (11, 13)
assert image.IsEmbedded()

root = app.root

def _quit_app():
    root.destroy()
    os._exit(0)

root.after(500, _quit_app)
