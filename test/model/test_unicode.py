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
    from Sketch import plugins
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
    assert doc2.layers[0].name == U_LAYER_NAME.encode('utf-8')
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
    assert obj2.text == U_PLUGIN_TEXT.encode('utf-8')
    out2 = testsupport.output_path('sk', 'rustext_unitext.rt.sk')
    save(doc2, out2)
    assert_saved_without_u_prefixes(out2)
    round_trip_stable(out1, out2)
