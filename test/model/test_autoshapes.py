# Layer 1: headless tests for the autoshape plugin compound.  The shape
# modules (arrow.py, smiley.py, ...) are loaded dynamically by
# autoshapelib.Loader; under Python 2 that used an implicit relative
# __import__, which py3 removed -- Loader must build the fully
# qualified package path (py3 regression guard).


import pytest

import testsupport


# all shape names the Autoshapes dialog inserts (autoshapeplugin.py);
# every module in the package except the sticky.py helper defines one
SHAPE_NAMES = [
    'angle', 'arc', 'arrow', 'circle1', 'circle2', 'circle3', 'cube',
    'cylinder', 'dconnection', 'divide', 'doublearrow', 'hconnection',
    'intersection', 'measure', 'raster', 'rim', 'scalebar', 'smiley',
    'star', 'tangent', 'thinhalfturn', 'thinturn', 'vconnection',
]


def autoshape_class():
    testsupport.sketch()
    from Sketch.Plugins.Objects.Lib.autoshapes.autoshapelib import Autoshape
    return Autoshape


@pytest.mark.parametrize('name', SHAPE_NAMES)
def test_autoshape_loads(name):
    """Every autoshape must load through Loader: the instance's class
    must be replaced by the shape module's registered class (an
    AutoshapeBase subclass), not the UnknownShape fallback."""
    from Sketch.Plugins.Objects.Lib.autoshapes.autoshapelib import (
        AutoshapeBase, UnknownShape)
    Autoshape = autoshape_class()
    obj = Autoshape(name)
    assert obj.__class__ is not UnknownShape
    assert isinstance(obj, AutoshapeBase)
    assert obj.name == name


def test_autoshape_unknown_shape_fallback(monkeypatch):
    """A bogus name must still produce an object (UnknownShape), i.e.
    Loader must not raise.  (report_error is stubbed out: headless there
    is no application to show the warning box.)"""
    import Sketch.Plugins.Objects.Lib.autoshapes.autoshapelib as lib
    warnings = []
    monkeypatch.setattr(lib, 'report_error',
                        lambda *args, **kw: warnings.append(args))
    Autoshape = autoshape_class()
    obj = Autoshape('no-such-shape')
    assert obj.__class__ is lib.UnknownShape
    assert isinstance(obj, lib.AutoshapeBase)
    assert len(warnings) == 1


# ------------------------------------------------- key dispatch (py3 fix)

def test_autoshape_editor_command_registered():
    """Importing the plugin must register AutoshapeBase and
    AutoshapeEditor in Sketch.command_classes, with the AutoshapeKey
    command bound to the +/- and arrow keys and its object_class set
    (the canvas builds its per-class keymaps from that registry)."""
    import Sketch
    from Sketch.UI import command
    autoshape_class()
    names = [c.__name__ for c in Sketch.command_classes]
    assert 'AutoshapeBase' in names
    assert 'AutoshapeEditor' in names
    editor_cls = [c for c in Sketch.command_classes
                  if c.__name__ == 'AutoshapeEditor'][0]
    keycmd = [c for c in editor_cls.commands if c.name == 'AutoshapeKey'][0]
    assert isinstance(keycmd, command.ObjectCommandClass)
    strokes = keycmd.key_stroke
    if isinstance(strokes, str):
        strokes = (strokes,)
    assert '+' in strokes and '-' in strokes
    assert keycmd.object_class is editor_cls
    # AddCmd stores the method's name (AnyKey), not the command name;
    # ObjectCommand.Invoke dispatches document.CallObjectMethod with it
    assert keycmd.command == 'AnyKey' 


def test_autoshape_plus_minus_key_dispatch():
    """The edit-mode dispatch of the +/- keys at the model level:
    document.CallObjectMethod(AutoshapeEditor, 'AutoshapeKey', key)
    must reach the shape's KeyHandler through the EditSelection's
    editor and change the star's ray count."""
    sk = testsupport.sketch()
    from Sketch import Document
    from Sketch.Plugins.Objects.Lib.autoshapes.autoshapelib import (
        Autoshape, AutoshapeEditor)
    doc = Document(create_layer=1)
    obj = Autoshape('star')
    obj.SetData((20, 20, 5))
    assert obj.GetN() == 5
    doc.Insert(obj)
    doc.SelectAll()
    doc.SetMode(sk.EditMode)
    assert doc.IsEditMode()
    # build the ObjectCommand the same way the canvas keymap does
    # (InstantiateFor(canvas)) and invoke it with the keystroke --
    # ObjectCommand.Invoke -> document.CallObjectMethod(AutoshapeEditor,
    # '', 'AnyKey', key) -> EditorWrapper -> AnyKey -> KeyHandler
    keycmd = [c for c in AutoshapeEditor.commands
              if c.name == 'AutoshapeKey'][0]
    class CanvasStub:
        # the canvas stands in for the ObjectCommand's object; only
        # .document (for Invoke) and Subscribe (for the update wiring
        # in InstantiateFor) are needed
        def __init__(self, doc):
            self.document = doc
        def Subscribe(self, *args):
            pass
    cmd = keycmd.InstantiateFor(CanvasStub(doc))
    cmd.Invoke('+')
    assert obj.GetN() == 6
    cmd.Invoke('-')
    assert obj.GetN() == 5
    # an unrelated class must be refused (the warning path taken
    # before the canvas keymap fix)
    from Sketch.Graphics.text import CommonText
    doc.CallObjectMethod(CommonText, '', 'AnyKey', '+')
    assert obj.GetN() == 5
