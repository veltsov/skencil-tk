# --run-script payload: exercise Move To Top / Bottom / Up / Down on the
# opened document (regression test for the py3 `range` permutation bug
# in compound.move_objects_to_top et al.), then a clean quit.

import os

import Sketch

app = Sketch.Base.main.application
win = app.main_window
doc = win.document
assert doc is not None, 'no document open'

layer = doc.active_layer
layer_idx = [i for i, l in enumerate(doc.layers) if l is layer][0]
objs = layer.objects

n = len(objs)
assert n >= 2, 'test document must have at least 2 objects in a layer'
orig_ids = [id(o) for o in objs]


def ids():
    return [id(o) for o in layer.objects]


def select(*idxs):
    info = [((layer_idx, i), layer.objects[i]) for i in idxs]
    doc.selection.SetSelection(info)
    doc.queue_selection()


# Move To Top: object 0 must end up last
select(0)
doc.MoveSelectedToTop()
assert ids() == orig_ids[1:] + orig_ids[:1], \
    'MoveSelectedToTop: wrong order: %r' % (ids(),)
assert doc.selection.GetObjects() == [layer.objects[-1]], \
    'MoveSelectedToTop: wrong selection after move'

# Move To Bottom: the (now) last object must end up first again
select(n - 1)
doc.MoveSelectedToBottom()
assert ids() == orig_ids, 'MoveSelectedToBottom: wrong order: %r' % (ids(),)
assert doc.selection.GetObjects() == [layer.objects[0]], \
    'MoveSelectedToBottom: wrong selection after move'

# Undo both moves
doc.Undo()
doc.Undo()
assert ids() == orig_ids, 'undo of move to top/bottom: wrong order'

# Move Up / Down (same range-permutation code path)
select(0)
doc.MoveSelectionUp()
assert ids() == orig_ids[1:2] + orig_ids[:1] + orig_ids[2:], \
    'MoveSelectionUp: wrong order: %r' % (ids(),)
doc.Undo()
assert ids() == orig_ids, 'undo of move up: wrong order'

select(n - 1)
doc.MoveSelectionDown()
assert ids() == orig_ids[:-2] + orig_ids[-1:] + orig_ids[-2:-1], \
    'MoveSelectionDown: wrong order: %r' % (ids(),)
doc.Undo()
assert ids() == orig_ids, 'undo of move down: wrong order'

# multi-selection: move two objects to the top at once
select(0, 1)
doc.MoveSelectedToTop()
assert ids() == orig_ids[2:] + orig_ids[:2], \
    'MoveSelectedToTop (2 objects): wrong order: %r' % (ids(),)
doc.Undo()
assert ids() == orig_ids, 'undo of multi move to top: wrong order'

print('SMOKE_ZORDER_OK')

root = app.root


# NOTE: the process is terminated explicitly with os._exit(0) after the
# Tk is destroyed; see smoke_open.py for the rationale.

def _quit_app():
    root.destroy()
    os._exit(0)


root.after(1000, _quit_app)
