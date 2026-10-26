# -*- coding: utf-8 -*-
# Layer 1: headless model tests -- the glyph-index text representation.
#
# Text object content is an array of glyph ids into the global glyph
# registry (see devdocs/glyph-text.md).  These tests pin the registry,
# the coercion of the accepted input forms and the conversion sinks.

from __future__ import print_function

from array import array

import testsupport


def load(name):
    return testsupport.load_document(testsupport.data_path(name))


def first_text(document, cls='SimpleText'):
    for obj in testsupport.iter_objects(document):
        if testsupport.class_name(obj) == cls:
            return obj
    return None


def make_text(text):
    sk = testsupport.sketch()
    from Sketch import SimpleText, Identity
    from Sketch.Graphics.properties import DefaultTextProperties
    return SimpleText(Identity, text, properties=DefaultTextProperties())


def test_registry_reserved_ids():
    sk = testsupport.sketch()
    from Sketch.Graphics import font
    assert font.NOTDEF_GID == 0
    assert font.glyph_registry.name(font.NOTDEF_GID) == '.notdef'
    assert font.glyph_registry.name(font.NEWLINE_GID) == 'newline'
    assert font.glyph_registry.name(font.CARRIAGE_RETURN_GID) \
        == 'carriagereturn'
    # registration is idempotent
    assert font.glyph_registry.index('A') == font.glyph_registry.index('A')


def test_text_coercion_forms():
    text = make_text('AB')
    # byte string input -> gid array
    assert isinstance(text.text, array)
    assert text.text.typecode == 'I'
    font = text.properties.font
    assert [font.GlyphName(g) for g in text.text] == ['A', 'B']
    # gid array input passes through unchanged
    assert text._coerce_text(text.text) is text.text
    # unicode input maps via glyph names
    u = make_text(u'AB')
    assert u.text == text.text
    # SetText accepts all forms and keeps the array form
    text.SetText('CD')
    assert isinstance(text.text, array)
    assert [font.GlyphName(g) for g in text.text] == ['C', 'D']


def test_text_as_unicode():
    text = make_text('A\xe9')      # 'A' + latin-1 eacute
    assert text.TextAsUnicode() == u'A\xe9'
    assert text.Info() is not None


def test_font_encoded_roundtrip():
    # EncodedText is the inverse of byte-string coercion
    text = make_text('AB\xe9')
    font = text.properties.font
    assert font.EncodedText(text.text) == 'AB\xe9'
    # and the byte form coerces back to the same gids
    assert font.TextGids('AB\xe9') == text.text


def test_font_metrics_on_gids():
    text = make_text('AB')
    font = text.properties.font
    gids = text.text
    bbox = font.TextBoundingBox(gids, 24)
    width = font.metric.string_width(gids) * 24 / 1000.0
    assert bbox[2] - bbox[0] > 0
    assert width > 0
    # typesetting: one position per glyph
    assert len(font.TypesetText(gids)) == 2
    # the caret position of the full string equals the string width
    # (up to float rounding: TextCaretData multiplies by size/1000.0)
    pos, up = font.TextCaretData(gids, len(gids), 24)
    assert abs(pos.x - width) < 1e-4


def test_control_glyphs_roundtrip():
    # \n and \r bytes (as they occur in historical .sk files) map to
    # the reserved control glyphs and back
    sk = testsupport.sketch()
    from Sketch.Graphics import font
    text = make_text('A\nB\r')
    font = text.properties.font
    assert [font.GlyphName(g) for g in text.text] == \
        ['A', 'newline', 'B', 'carriagereturn']
    assert font.EncodedText(text.text) == 'A\nB\r'


def test_sk_save_reload_stable():
    # a document with text saves byte-identical txt() lines across a
    # save/reload cycle
    doc = load('alphares.sk')
    text = first_text(doc)
    assert text is not None
    assert isinstance(text.text, array)
    original = text.TextAsUnicode()

    sk = testsupport.sketch()
    from Sketch.Base import plugins
    saver = plugins.find_export_plugin(plugins.guess_export_plugin('.sk'))
    out1 = testsupport.output_path('sk', 'glyph_reload1.sk')
    out2 = testsupport.output_path('sk', 'glyph_reload2.sk')
    saver(doc, out1)
    doc2 = testsupport.load_document(out1)
    text2 = first_text(doc2)
    assert text2.TextAsUnicode() == original
    saver(doc2, out2)
    with open(out1) as f:
        first = testsupport.normalize_sk(f.read())
    with open(out2) as f:
        second = testsupport.normalize_sk(f.read())
    assert first == second, '.sk round trip is not stable'


def test_duplicate_keeps_text():
    # duplication passes no text argument; the duplicated object must
    # keep the original gid text
    text = make_text('AB')
    dup = text.Duplicate()
    assert dup.text == text.text
    assert dup.TextAsUnicode() == u'AB'


def test_typing_via_call_object_method():
    # the real keystroke path: ObjectCommand.Invoke ->
    # CallObjectMethod with the editor in the selection; the
    # transaction name is the command's menu name (unicode now, see
    # devdocs/testing.md -- a byte-string label used to raise
    # UndoTypeError and killed the per-keystroke redraw)
    sk = testsupport.sketch()
    from Sketch import Document, SimpleText, Translation, EditMode
    from Sketch.Graphics.properties import DefaultTextProperties
    from Sketch.Graphics import text as textmod

    doc = Document(create_layer = 1)
    obj = SimpleText(Translation(100, 100), 'A',
                     properties = DefaultTextProperties())
    doc.Insert(obj)
    doc.SelectObject(obj)
    doc.SetMode(EditMode)
    for ch in 'bc':
        doc.CallObjectMethod(textmod.CommonText, u'', 'InsertCharacter', ch)
    assert obj.TextAsUnicode() == u'bcA'
    doc.Undo()
    assert obj.TextAsUnicode() == u'bA'
    doc.Redo()
    assert obj.TextAsUnicode() == u'bcA'
    # a unicode-labelled transaction keeps working as well
    doc.BeginTransaction(u'label test')
    doc.add_undo(obj.SetText('X'))
    doc.EndTransaction()
    assert obj.TextAsUnicode() == u'X'
    doc.Undo()
    assert obj.TextAsUnicode() == u'bcA'


def test_command_menu_names_are_unicode():
    # Undo/transaction labels are K1 display strings: ObjectCommand
    # .Invoke passes the command's menu_name as the transaction name,
    # and undo.check_info enforces unicode labels (see
    # devdocs/testing.md, UndoTypeError finding).  Every registered
    # command must therefore have a unicode menu name.
    sk = testsupport.sketch()
    import inspect
    import sys
    count = 0
    for mod_name, module in sys.modules.items():
        if not mod_name.startswith('Sketch.'):
            continue
        module_dict = getattr(module, '__dict__', None)
        if not module_dict:
            continue
        for value in module_dict.values():
            if not inspect.isclass(value):
                continue
            commands = value.__dict__.get('commands')
            if not commands:
                continue
            for cmd in commands:
                # `commands' lists may also contain non-command items
                # (e.g. CharStringInterpreter's opcode table)
                name = getattr(cmd, 'menu_name', None)
                if name is None:
                    continue
                assert isinstance(name, str), \
                    '%s.%s: command menu name is not unicode: %r' \
                    % (mod_name, value.__name__, name)
                count += 1
    # the walk must actually have seen the registered commands
    assert count > 20


def test_out_of_encoding_glyphs_become_notdef():
    # a glyph the font cannot encode (e.g. the reserved newline name is
    # fine, but an arbitrary unicode name outside the font) is encoded
    # as code 0 (notdef) instead of raising
    sk = testsupport.sketch()
    from Sketch.Graphics import font
    text = make_text('A')
    gid = font.glyph_registry.index('uni0421')   # cyrillic 'С'
    assert text.properties.font.GlyphCodes([gid]) == [0]
    assert text.properties.font.EncodedText([gid]) == '\x00'


def test_insert_hyphen_vs_minus():
    # C-h inserts the glyph named 'hyphen'; ordinary typing of '-'
    # yields 'minus' for standard-encoding fonts (the intentional
    # encoding-table quirk, see devdocs/text-input.md).  Both glyphs
    # must be distinct and both must be encodable in the font.
    sk = testsupport.sketch()
    from Sketch import Document, SimpleText, Translation, EditMode
    from Sketch.Graphics.properties import DefaultTextProperties
    from Sketch.Graphics import text as textmod
    from Sketch.Graphics import font as fontmod

    doc = Document(create_layer = 1)
    obj = SimpleText(Translation(100, 100), 'A',
                     properties = DefaultTextProperties())
    doc.Insert(obj)
    doc.SelectObject(obj)
    doc.SetMode(EditMode)
    font = obj.properties.font
    doc.CallObjectMethod(textmod.CommonText, u'', 'InsertCharacter', '-')
    doc.CallObjectMethod(textmod.CommonText, u'', 'InsertHyphen')
    gids = obj.text
    assert len(gids) == 3
    minus_gid, hyphen_gid = gids[0], gids[1]
    # typing '-' gives the encoding-table glyph, C-h gives 'hyphen'
    assert fontmod.glyph_registry.name(minus_gid) == 'minus'
    assert fontmod.glyph_registry.name(hyphen_gid) == 'hyphen'
    assert minus_gid != hyphen_gid
    # both are printable (encodable) and round-trip through the codes
    assert font.IsPrintableGlyph(minus_gid)
    assert font.IsPrintableGlyph(hyphen_gid)
    assert font.GlyphCodes([minus_gid, hyphen_gid]) == [45, 173]
    assert font.EncodedText([hyphen_gid]) == '\xad'
    # the insertion is undoable as a single transaction
    doc.Undo()
    assert len(obj.text) == 2
    assert fontmod.glyph_registry.name(obj.text[0]) == 'minus'
    doc.Redo()
    assert fontmod.glyph_registry.name(obj.text[1]) == 'hyphen'

