# -*- coding: utf-8 -*-
# Layer 1: headless model tests -- unicode strings at runtime.
#
# The gettext shim returns unicode, so gettext-derived strings (layer
# names) and any other unicode reaching the object model must not leak
# into saved .sk files as u'...' (parse_sk_line2 rejects the u prefix);
# they must be written as utf-8 \x-escaped byte strings, byte-compatible
# with master.  See devdocs/unicode-runtime-audit.md.

from __future__ import print_function

import re

import testsupport

FIXTURE = 'rustext.sk'   # Russian layer name + LtxObj text parameter

# 'Слой 1' ("Layer 1" in the ru locale, as _() would produce it)
U_LAYER_NAME = u'\u0421\u043b\u043e\u0439 1'
# 'Текст' ("Text"), injected as the LtxObj plugin parameter
U_PLUGIN_TEXT = u'\\sf \u0422\u0435\u043a\u0441\u0442'


def load(name=FIXTURE):
    return testsupport.load_document(testsupport.data_path(name))


def save(doc, path):
    sk = testsupport.sketch()
    from Sketch.Base import plugins
    saver = plugins.find_export_plugin(plugins.guess_export_plugin('.sk'))
    saver(doc, path)


def assert_saved_without_u_prefixes(path):
    """Save output must contain no u'...'/u"..." string prefixes."""
    with open(path, 'rb') as f:
        data = f.read()
    leaked = re.search(r"(?<![A-Za-z_])u['\"]", data)
    assert leaked is None, \
        'unicode string leaked into %s: %r...' \
        % (path, data[leaked.start():][:40])
    return data


def first_ltxobj(document):
    for obj in testsupport.iter_objects(document):
        if testsupport.class_name(obj) == 'LtxObj':
            return obj
    return None


def round_trip_stable(out1, out2):
    with open(out1) as f:
        first = testsupport.normalize_sk(f.read())
    with open(out2) as f:
        second = testsupport.normalize_sk(f.read())
    assert first == second, '%s: .sk round trip is not stable' % out1


# ------------------------------------------------- display/compare paths

def test_util_format_mixed_unicode_bytes():
    # the SELECTION status-bar path: unicode template from _(), utf-8
    # byte values from the document (layer name), unicode value from
    # LtxObj.Info().  util.format must normalize and return unicode.
    sk = testsupport.sketch()
    from Sketch.Lib.util import format, as_unicode
    template = u"%(object)s on `%(layer)s'"
    dict = {'layer': U_LAYER_NAME.encode('utf-8'),
            'object': u'LaTeX Text: `\\preamble, size 25'}
    text = format(template, {}, dict)
    assert isinstance(text, unicode)
    assert as_unicode(U_LAYER_NAME) in text


def test_selection_info_text():
    # the full status-bar path as driven by the canvas
    doc = load()
    doc.SelectAll()
    template, dict = doc.SelectionInfoText()
    sk = testsupport.sketch()
    from Sketch.Lib.util import format
    from Sketch.UI import converters
    text = format(template, converters.converters, dict)
    assert isinstance(text, unicode)
    # the utf-8 layer name 'База' must appear decoded, no exception
    assert u'\u0411\u0430\u0437\u0430' in text


def test_ltxobj_info():
    # LtxObj.Info() truncates the text to 20 chars; with utf-8 byte
    # strings it must decode before slicing (also: non-ascii leading
    # text must not crash the unicode template)
    doc = load()
    obj = first_ltxobj(doc)
    assert obj is not None, 'no LtxObj in %s' % FIXTURE
    sk = testsupport.sketch()
    from Sketch.Lib.util import as_unicode
    info = obj.Info()
    assert isinstance(info, unicode)
    assert '\\preamble' in info        # first 20 bytes are ascii preamble
    obj.text = U_PLUGIN_TEXT           # leading non-ascii
    info = obj.Info()
    assert isinstance(info, unicode)
    assert as_unicode(U_PLUGIN_TEXT)[:20] in info


def test_unicode_layer_name_save_reload():
    # inject a unicode layer name (as _()-derived defaults do), save and
    # reread: the file must contain the utf-8 bytes in master's
    # \x-escaped repr() form, and the name must come back unchanged
    doc = load()
    doc.layers[0].SetName(U_LAYER_NAME)
    out1 = testsupport.output_path('sk', 'rustext_unilayer.sk')
    save(doc, out1)
    data = assert_saved_without_u_prefixes(out1)
    expected = 'layer(' + repr(U_LAYER_NAME.encode('utf-8')) \
               + ',1,1,0,0,(0,0,0))'
    assert expected in data, \
        'layer line not in expected form %r' % expected
    doc2 = testsupport.load_document(out1)
    # the reader decodes user-provided strings (K2): the model holds
    # unicode (devdocs/string-handling.md)
    assert doc2.layers[0].name == U_LAYER_NAME
    assert isinstance(doc2.layers[0].name, unicode)
    # the reloaded document must save identically
    out2 = testsupport.output_path('sk', 'rustext_unilayer.rt.sk')
    save(doc2, out2)
    assert_saved_without_u_prefixes(out2)
    round_trip_stable(out1, out2)


def test_unicode_plugin_parameter_save_reload():
    # inject a unicode plugin parameter into the LtxObj object, save and
    # reread: same byte format requirements as for layer names
    doc = load()
    obj = first_ltxobj(doc)
    assert obj is not None, 'no LtxObj in %s' % FIXTURE
    # NOTE: set the attribute directly; SetParameters would trigger a
    # LaTeX recompute, which needs external tools (pdflatex/pstoedit)
    obj.text = U_PLUGIN_TEXT
    out1 = testsupport.output_path('sk', 'rustext_unitext.sk')
    save(doc, out1)
    data = assert_saved_without_u_prefixes(out1)
    expected = "PC('LtxObj'," + repr(U_PLUGIN_TEXT.encode('utf-8'))
    assert expected in data, \
        'PC line not in expected form %r' % expected
    doc2 = testsupport.load_document(out1)
    obj2 = first_ltxobj(doc2)
    assert obj2 is not None, 'LtxObj lost on reload'
    # plugin parameter text is K2: unicode in the model
    assert obj2.text == U_PLUGIN_TEXT
    assert isinstance(obj2.text, unicode)
    out2 = testsupport.output_path('sk', 'rustext_unitext.rt.sk')
    save(doc2, out2)
    assert_saved_without_u_prefixes(out2)
    round_trip_stable(out1, out2)


# --------------------------------------------- reader boundary (K2 -> unicode)

def test_reader_decodes_user_strings():
    # A hand-written minimal .sk with non-ascii utf-8 names in master's
    # \\x-escaped repr() form.  The reader must produce unicode for all
    # user-provided strings (layer/guidelayer/grid names, style names,
    # paper-format names) and must NOT touch text-object content
    # (font-encoded bytes).
    sk = testsupport.sketch()
    layer = u'\u0421\u043b\u043e\u0439'            # 'Слой'
    guidelayer = u'\u041d\u0430\u043f\u0440\u0430\u0432\u043b\u044f\u044e\u0449\u0438\u0435'
    grid = u'\u0421\u0435\u0442\u043a\u0430'       # 'Сетка'
    style = u'\u0421\u0442\u0438\u043b\u044c'      # 'Стиль'
    # text content: bytes that are NOT valid utf-8 (font-encoded data
    # has no reason to be); every byte is one character
    text_bytes = '\\xff\\xfe\\x41'
    content = ('##Sketch 1 2\n'
               'document()\n'
               + 'layout(%r,0)\n' % 'A4'
               + 'layer(%r,1,1,0,0,(0,0,0))\n' % layer.encode('utf-8')
               + 'dstyle(%r)\n' % style.encode('utf-8')
               + 'guidelayer(%r,1,0,0,1,(0,0,1))\n' % guidelayer.encode('utf-8')
               + 'grid((0,0,20,20),0,(0,0,1),%r)\n' % grid.encode('utf-8')
               + 'layer(%r,1,1,0,0,(0,0,0))\n' % layer.encode('utf-8')
               + 'txt(%r,(10,10))\n' % text_bytes)
    path = testsupport.output_path('sk', 'reader_boundary.sk')
    with open(path, 'wb') as f:
        f.write(content)
    doc = testsupport.load_document(path)
    # K2: names are unicode
    assert doc.layers[0].name == layer
    assert isinstance(doc.layers[0].name, unicode)
    assert doc.layers[1].name == guidelayer
    assert isinstance(doc.layers[1].name, unicode)
    assert doc.layers[2].name == grid
    assert isinstance(doc.layers[2].name, unicode)
    assert doc.GetDynamicStyle(style) is not None
    assert style in doc.GetStyleNames()
    assert doc.Layout().FormatName() == 'A4'
    assert isinstance(doc.Layout().FormatName(), unicode)
    # K3: text object content is an array of glyph ids now (see
    # devdocs/glyph-text.md); the font-encoded bytes from the file
    # round-trip through the font's encoding
    texts = [obj for obj in testsupport.iter_objects(doc)
             if testsupport.class_name(obj) == 'SimpleText']
    assert len(texts) == 1, 'expected one SimpleText, got %d' % len(texts)
    from array import array
    assert isinstance(texts[0].text, array)
    assert texts[0].text.typecode == 'I'
    # display: glyph ids map via their names to unicode; the loaded
    # bytes here are the literal `\xff\xfe\x41' characters (the .sk
    # reader does not decode \x escapes), so their names map back to
    # the same literal characters.  Info() must not raise either way.
    assert texts[0].Info() is not None
    assert texts[0].TextAsUnicode() == text_bytes.decode('latin-1')
    font = texts[0].properties.font
    if font is None:
        from Sketch.Base import config
        from Sketch.Graphics import font as font_module
        font = font_module.GetFont(config.preferences.fallback_font)
    assert font.EncodedText(texts[0].text) == text_bytes


# --------------------------------------------- preferences file format

# '/изо' and '/рус/Слой.sk' -- non-ascii preference values
PREFS_U_DIR = u'\u0438\u0437\u043e'
PREFS_U_NAME = u'/\u0440\u0443\u0441/\u0421\u043b\u043e\u0439.sk'


def test_preferences_save_repr_plain_utf8_literals():
    # preferences.py is written via configutil.save_repr as plain
    # string literals containing the utf-8 characters directly -- no
    # u'...' prefixes and no \x byte escapes -- so the file has the
    # same plain syntax under python2 and python3 (where no conversion
    # is needed at all)
    sk = testsupport.sketch()
    from Sketch import Point
    from Sketch.Base import configutil

    text = configutil.save_repr([PREFS_U_NAME, 'plain.sk'])
    assert "u'" not in text and 'u"' not in text
    assert '\\x' not in text                       # no byte escapes
    assert PREFS_U_NAME in text                    # characters as-is

    # only the characters that would break the literal are escaped
    assert configutil.save_repr("a'b\\c\nd\x01e") == \
        "'a\\'b\\\\c\\nd\\x01e'"
    # byte-string stragglers (ascii-only Tk values) are decoded first
    assert configutil.save_repr('plain.sk') == "'plain.sk'"
    assert configutil.save_repr(Point(1, 2)) == 'Point(1, 2)'


def _write_preferences_file(dirpath, lines):
    import os
    if not os.path.isdir(dirpath):
        os.makedirs(dirpath)
    path = os.path.join(dirpath, 'preferences.py')
    with open(path, 'wb') as f:
        f.write(''.join(lines).encode('utf-8'))
    return path


def test_preferences_load_converts_to_unicode():
    # save_user_preferences writes plain utf-8 literals; the loader
    # executes the file into an intermediate attribute bag and
    # converts the values to unicode before they reach the live
    # preferences object (devdocs/string-handling.md).  The load below
    # runs with UnicodeWarning raised as an error: no mixed bytes/
    # unicode comparison may happen anywhere on the path.
    sk = testsupport.sketch()
    import os
    import sys
    import warnings
    from Sketch.Base import config, configutil

    mru = [PREFS_U_NAME, 'plain.sk', '', '']
    prefs_dir = testsupport.output_dir('prefs')
    old_dir = config.user_config_dir
    old_file = config.user_settings_file
    old_mru = config.preferences.mru_files
    old_image_dir = config.preferences.image_dir
    try:
        config.user_config_dir = prefs_dir
        config.user_settings_file = 'preferences.py'
        config.preferences.mru_files = mru
        config.preferences.image_dir = PREFS_U_DIR
        configutil.save_user_preferences()

        path = os.path.join(prefs_dir, 'preferences.py')
        with open(path, 'rb') as f:
            data = f.read()
        assert data.startswith('#### -*- coding: utf-8 -*-\n')
        assert "u'" not in data
        assert PREFS_U_NAME.encode('utf-8') in data

        # simulate a fresh start: defaults, then load
        config.preferences.mru_files = ['', '', '', '']
        config.preferences.image_dir = ''
        with warnings.catch_warnings():
            warnings.simplefilter('error', UnicodeWarning)
            configutil.load_user_preferences()

        assert config.preferences.mru_files == mru
        assert config.preferences.image_dir == PREFS_U_DIR
        assert isinstance(config.preferences.mru_files[0], unicode)
        # the runtime mru lookups work with non-ascii names
        configutil.add_mru_file(u'\u0444')
        assert config.preferences.mru_files[0] == u'\u0444'
    finally:
        config.user_config_dir = old_dir
        config.user_settings_file = old_file
        config.preferences.mru_files = old_mru
        config.preferences.image_dir = old_image_dir
        if prefs_dir in sys.path:
            sys.path.remove(prefs_dir)


def test_preferences_undecodable_values_dropped():
    # a hand-written (or old-format) preferences file may contain byte
    # strings that are not valid utf-8: the loader warns on the
    # console, skips the undecodable mru_files entries and resets
    # image_dir to the current directory
    sk = testsupport.sketch()
    import os
    import sys
    from StringIO import StringIO
    from Sketch.Base import config, configutil

    prefs_dir = testsupport.output_dir('prefs')
    old_dir = config.user_config_dir
    old_file = config.user_settings_file
    old_mru = config.preferences.mru_files
    old_image_dir = config.preferences.image_dir
    had_sample = hasattr(config.preferences, 'sample_text')
    old_sample = getattr(config.preferences, 'sample_text', None)
    try:
        config.user_config_dir = prefs_dir
        config.user_settings_file = 'preferences.py'
        _write_preferences_file(prefs_dir, [
            '#### -*- coding: utf-8 -*-\n',
            "preferences.mru_files = ['good.sk', "
            "'\\xff\\xfebad', 'also good.sk']\n",
            "preferences.image_dir = '\\xff\\xfe'\n",
            "preferences.sample_text = 'plain text'\n",
        ])

        buf = StringIO()
        old_stderr = sys.stderr
        sys.stderr = buf
        try:
            configutil.load_user_preferences()
        finally:
            sys.stderr = old_stderr

        assert config.preferences.mru_files == ['good.sk', 'also good.sk',
                                                '', '']
        assert config.preferences.image_dir == os.getcwdu()
        assert config.preferences.sample_text == 'plain text'
        assert isinstance(config.preferences.sample_text, unicode)
        assert buf.getvalue().count('not valid utf-8') == 2
    finally:
        config.user_config_dir = old_dir
        config.user_settings_file = old_file
        config.preferences.mru_files = old_mru
        config.preferences.image_dir = old_image_dir
        if had_sample:
            config.preferences.sample_text = old_sample
        else:
            config.preferences.__dict__.pop('sample_text', None)
        if prefs_dir in sys.path:
            sys.path.remove(prefs_dir)


def test_preferences_short_mru_list_padded():
    # a hand-edited preferences file may contain fewer mru entries
    # than the four slots that the LoadMRU0..3 commands access
    # unconditionally in mainwindow.py (name_cb and LoadFromFile);
    # the loader pads the list to four entries (regression:
    # IndexError in the name_cb crashed the startup)
    sk = testsupport.sketch()
    import os
    import sys
    from Sketch.Base import config, configutil

    prefs_dir = testsupport.output_dir('prefs')
    old_dir = config.user_config_dir
    old_file = config.user_settings_file
    old_mru = config.preferences.mru_files
    try:
        config.user_config_dir = prefs_dir
        config.user_settings_file = 'preferences.py'
        _write_preferences_file(prefs_dir, [
            '#### -*- coding: utf-8 -*-\n',
            "preferences.mru_files = ['only.sk', 'two.sk']\n",
        ])
        configutil.load_user_preferences()
        mru = config.preferences.mru_files
        assert mru == ['only.sk', 'two.sk', '', '']
        assert isinstance(mru[0], unicode)
        # the unconditional accesses of the LoadMRU commands work
        assert mru[3] == ''
        assert os.path.split(mru[3])[1] == ''
    finally:
        config.user_config_dir = old_dir
        config.user_settings_file = old_file
        config.preferences.mru_files = old_mru
        if prefs_dir in sys.path:
            sys.path.remove(prefs_dir)


def test_reader_decodes_style_names_for_use_style():
    # style names are used as dict keys in the loader and compared in
    # the styledlg; both file and dialog side are unicode now
    sk = testsupport.sketch()
    style = u'\u0421\u0442\u0438\u043b\u044c 2'    # 'Стиль 2'
    content = ('##Sketch 1 2\n'
               'document()\n'
               'layer(%r,1,1,0,0,(0,0,0))\n' % u'\u0421\u043b\u043e\u0439'.encode('utf-8')
               + 'dstyle(%r)\n' % style.encode('utf-8')
               + 'use_style(%r)\n' % style.encode('utf-8')
               + 'r(1,0,0,1,10,10)\n')
    path = testsupport.output_path('sk', 'reader_style.sk')
    with open(path, 'wb') as f:
        f.write(content)
    doc = testsupport.load_document(path)
    assert style in doc.GetStyleNames()
    assert doc.GetDynamicStyle(style) is not None


def test_document_filename_unicode_round_trip():
    # save/load with a non-ascii document name: py2 open/os accept
    # unicode names directly (fs encoding = utf-8, the assumption of
    # devdocs/string-handling.md); meta.filename must stay unicode
    import os
    doc = load()
    name = u'\u0440\u0443\u0441doc.sk'
    out = os.path.join(testsupport.output_dir('sk'), name)
    save(doc, out)
    assert os.path.isfile(out)
    doc2 = testsupport.load_document(out)
    assert doc2.meta.filename == name
    assert isinstance(doc2.meta.filename, unicode)


# --------------------------------------------- filename boundary (K2)

def test_tk_filename_boundary_returns_unicode():
    # stock _tkinter returns unicode for results containing non-ascii
    # characters and byte strings for ascii-only ones (verified under
    # Xvfb); the filename boundary normalizes both to unicode -- file
    # names are unicode in the model (devdocs/string-handling.md)
    sk = testsupport.sketch()
    from Sketch.Lib.util import as_unicode
    name = u'\u0440\u0443\u0441text\u00e4.sk'
    assert as_unicode(name) == name
    assert as_unicode('plain.sk') == 'plain.sk'
    assert isinstance(as_unicode('plain.sk'), unicode)


def test_eps_with_unicode_filename_info():
    # regression: EpsImage.Info() crashed with a byte-string file name
    # (UnicodeDecodeError inside the unicode _() template).  File names
    # are unicode in the model now (decoded at the .sk reader), so the
    # whole display path needs no per-site normalization.
    sk = testsupport.sketch()
    import os
    import shutil
    from Sketch.Lib.util import format
    from Sketch.UI import converters
    eps_name = u'oms\u0448\u0442\u0443\u043a\u0430.eps'
    layer = u'\u0421\u043b\u043e\u0439'
    outdir = testsupport.output_dir('sk')
    shutil.copy(testsupport.data_path('oms.eps'),
                os.path.join(outdir, eps_name.encode('utf-8')))
    content = ('##Sketch 1 2\n'
               'document()\n'
               + 'layer(%r,1,1,0,0,(0,0,0))\n' % layer.encode('utf-8')
               + 'eps((1,0,0,1,10,10),%r)\n' % eps_name.encode('utf-8'))
    path = os.path.join(outdir, 'reader_eps.sk')
    with open(path, 'wb') as f:
        f.write(content)
    doc = testsupport.load_document(path)
    doc.SelectAll()
    eps_objs = [o for o in testsupport.iter_objects(doc)
                if testsupport.class_name(o) == 'EpsImage']
    assert len(eps_objs) == 1, 'expected one EpsImage'
    assert eps_objs[0].data.Filename().endswith(eps_name)
    assert isinstance(eps_objs[0].data.Filename(), unicode)
    # the full status-bar path (which crashed before) must work
    template, dict = doc.SelectionInfoText()
    text = format(template, converters.converters, dict)
    assert isinstance(text, unicode)
    assert eps_name in text


def test_as_display_name_assumes_utf8():
    # K4 display conversion assumes utf-8 names and is lenient: valid
    # utf-8 decodes exactly, invalid bytes are replaced, never raised
    sk = testsupport.sketch()
    from Sketch.Lib.util import as_display_name
    name = u'\u0440\u0443\u0441text\u00e4.sk'
    assert as_display_name(name.encode('utf-8')) == name
    assert as_display_name(name) == name            # unicode passes through
    assert u'\ufffd' in as_display_name('\xff\xfe')  # invalid utf-8 -> U+FFFD
    assert isinstance(as_display_name('\xff\xfe'), unicode)


def test_utf8_to_latin1_accepts_bytes_and_unicode():
    # the K3 input path (canvas key events, multilinetext dialog) gets
    # the same ascii/unicode coin-flip from _tkinter; both must map to
    # the same latin-1 bytes
    sk = testsupport.sketch()
    from Sketch.UI import tkext
    assert tkext.utf8_to_latin1(u'\xe9xy') == '\xe9xy'
    assert tkext.utf8_to_latin1('\xc3\xa9xy') == '\xe9xy'
    assert isinstance(tkext.utf8_to_latin1('\xc3\xa9xy'), str)
