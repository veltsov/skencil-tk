# --run-script payload: the document (argument) has missing linked
# files (SKENCIL_TEST_LINKS_EPS, SKENCIL_TEST_LINKS_PNG point to where
# they are now); the image file is also used as the fill pattern of a
# rectangle. Open the Links panel, check the rows and their popup
# menu, relink, select, embed and toggle the automatic update through
# the panel, replace files with the canvas commands, then quit.

import os
import sys
import tempfile

import PIL.Image

import Sketch

app = Sketch.Base.main.application
win = app.main_window
root = app.root


def indicator(row):
    bitmap = str(row.indicator['bitmap'])
    if bitmap.endswith('MiniArrowRight.xbm'):
        return 'arrow'
    return bitmap


def kinds(row):
    # the kind icons and counts of a row, e.g. [('MiniImage', '1')]
    labels = row.kind_labels
    return [(os.path.basename(str(labels[i]['bitmap']))[:-4],
             labels[i + 1]['text']) for i in range(0, len(labels), 2)]


def kind_colors(row):
    return set(str(label['foreground']) for label in row.kind_labels)


def menu_labels(panel, idx):
    panel.context_idx = idx
    entries = panel.build_context_menu()
    return [entry.rest.get('label') if entry is not None else None
            for entry in entries], entries


def check():
    doc = win.document
    win.CreateDialog('Sketch.UI.linksdlg', 'LinksPanel')
    panel = win.dialogs['LinksPanel']
    assert len(panel.rows) == 2, panel.rows
    assert kinds(panel.rows[0]) == [('MiniEps', '1')], kinds(panel.rows[0])
    assert kinds(panel.rows[1]) == [('MiniImage', '1'),
                                    ('MiniPattern', '1')], \
                                    kinds(panel.rows[1])
    for row in panel.rows:
        assert indicator(row) == 'warning', indicator(row)
        assert kind_colors(row) == {'red'}
        assert str(row.update['bitmap']).endswith('MiniReload.xbm')
        assert not hasattr(row, 'embed') and not hasattr(row, 'browse')
    labels, entries = menu_labels(panel, 0)
    assert labels == ['Replace...', 'Embed', 'Select Objects', None,
                      'Update'], labels
    # missing file: Embed is not possible
    assert not entries[1].sensitivecb()

    # the file name fields take the width of the panel
    root.update()
    top = panel.top
    entry = panel.rows[0].entry
    w0, h0 = top.winfo_width(), top.winfo_height()
    e0 = entry.winfo_width()
    top.geometry('%dx%d' % (w0 + 200, h0))
    root.update()
    e1 = entry.winfo_width()
    assert abs(e1 - (e0 + 200)) <= 4, (e0, e1)
    top.geometry('%dx%d' % (w0 - 100, h0))
    root.update()
    e2 = entry.winfo_width()
    assert abs(e2 - (e0 - 100)) <= 4, (e0, e2)
    assert panel.rows[0].update.winfo_ismapped()
    top.geometry('%dx%d' % (w0, h0))
    root.update()

    # the canvas commands Replace Image/EPS: in the context menu of the
    # respective objects only, also of placeholders
    eps_obj, png_obj = doc.LinkedObjects()
    replace_image = win.commands.ReplaceImage
    replace_eps = win.commands.ReplaceEps
    canvas_cmds = win.canvas
    canvas_cmds.build_context_commands()
    assert replace_image in canvas_cmds.context_commands
    assert replace_eps in canvas_cmds.context_commands
    doc.SelectObject(eps_obj)
    root.update()
    assert replace_eps.InContext() and not replace_image.InContext()
    # selection marker on the row of the selected object
    assert indicator(panel.rows[0]) == 'arrow'
    assert indicator(panel.rows[1]) == 'warning'
    doc.SelectNone()
    root.update()
    assert indicator(panel.rows[0]) == 'warning'

    # Select Objects in the row popup: the image and the rectangle
    # filled with it
    rect = panel.groups[1].pattern_owners[0]
    labels, entries = menu_labels(panel, 1)
    assert entries[2].sensitivecb()
    panel.select_objects(1)
    root.update()
    assert set(map(id, doc.SelectedObjects())) == {id(png_obj), id(rect)}
    assert indicator(panel.rows[1]) == 'arrow'
    # the arrow also for the selected pattern owner alone
    doc.SelectObject(rect)
    root.update()
    assert indicator(panel.rows[1]) == 'arrow'
    assert indicator(panel.rows[0]) == 'warning'
    doc.SelectObject(png_obj)
    root.update()
    assert replace_image.InContext() and not replace_eps.InContext()

    # relink both through the panel (as if typed in the entry)
    for idx, var in enumerate(('SKENCIL_TEST_LINKS_EPS',
                               'SKENCIL_TEST_LINKS_PNG')):
        entry = panel.rows[idx].entry
        entry.delete(0, 'end')
        entry.insert(0, os.environ[var])
        panel.relink(idx)
    root.update()
    assert [obj.IsMissing() for obj in doc.LinkedObjects()] == [0, 0]
    # the pattern is relinked with the image
    pattern = rect.Properties().fill_pattern
    assert pattern.Data() is png_obj.Data()
    assert indicator(panel.rows[0]) == ''
    assert 'red' not in kind_colors(panel.rows[1])
    labels, entries = menu_labels(panel, 0)
    assert entries[1].sensitivecb()

    # undo restores the missing state and the panel follows
    doc.Undo()
    doc.Undo()
    root.update()
    assert len(panel.rows) == 2
    assert indicator(panel.rows[0]) == 'warning'
    doc.Redo()
    doc.Redo()
    root.update()

    # Replace Image on the canvas: the dialog is replaced by a prepared
    # file; only the selected object changes
    from Sketch.UI import linksdlg
    tmp = tempfile.mkdtemp()
    new_png = os.path.join(tmp, 'new.png')
    PIL.Image.new('RGB', (5, 4), (0, 255, 0)).save(new_png)
    asked = []
    def ask(main_window, filename, is_eps):
        asked.append((filename, is_eps))
        return new_png
    linksdlg.ask_link_filename = ask
    doc.SelectObject(png_obj)
    win.ReplaceObjectFile(0)
    assert asked == [(os.environ['SKENCIL_TEST_LINKS_PNG'], 0)], asked
    assert png_obj.Data().Filename() == new_png
    assert png_obj.IsLinked() and png_obj.Data().Size() == (5, 4)
    # the pattern keeps its file: two rows now
    assert pattern.Data().Filename() == os.environ['SKENCIL_TEST_LINKS_PNG']
    root.update()
    assert [kinds(row) for row in panel.rows[1:]] == [
        [('MiniImage', '1')], [('MiniPattern', '1')]] or \
        [kinds(row) for row in panel.rows[1:]] == [
        [('MiniPattern', '1')], [('MiniImage', '1')]], \
        [kinds(row) for row in panel.rows]
    doc.Undo()
    root.update()
    assert png_obj.Data().Filename() == os.environ['SKENCIL_TEST_LINKS_PNG']
    assert len(panel.rows) == 2

    # embed the image through the panel (also the pattern) ...
    panel.embed(1)
    root.update()
    assert len(panel.rows) == 1
    assert png_obj.IsEmbedded() and pattern.Data().IsEmbedded()
    # ... Replace Image keeps an embedded image embedded
    doc.SelectObject(png_obj)
    assert replace_image.InContext()
    del asked[:]
    win.ReplaceObjectFile(0)
    assert asked == [('', 0)], asked
    assert png_obj.IsEmbedded() and png_obj.Data().Size() == (5, 4)

    # the check button and the menu command stay in sync
    cmd = win.commands.ToggleAutoReload
    assert not panel.var_auto.get()
    panel.toggle_auto()
    assert cmd.GetValue() and panel.var_auto.get()
    win.ToggleAutoReload()
    assert not panel.var_auto.get()

    panel.close_dlg()
    sys.stdout.write('LINKS-OK\n')
    sys.stdout.flush()


def _run():
    try:
        check()
    except Exception:
        import traceback
        traceback.print_exc()
    root.destroy()
    os._exit(0)


root.after(1000, _run)
