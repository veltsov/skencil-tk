# Layer 1: the options of export plugins (declared parameters, kept per
# document for the session; the UI asks for them with
# plugindlg.ExportOptionsDlg).

import testsupport


def setup_module(module):
    testsupport.sketch()


def new_document():
    from Sketch import EditDocument
    return EditDocument(create_layer = 1)


def test_defaults_then_stored():
    from Sketch.Base import plugins
    info = plugins.find_export_plugin('SVG')
    doc = new_document()
    assert info.GetOptions(doc) == {'flavour': 0, 'box': 0, 'text': 0,
                                   'eps': 0, 'eps_dpi': 300, 'images': 0}
    out = testsupport.output_path('export-options', 'box.svg')
    info(doc, out, options = {'box': 1})
    assert info.GetOptions(doc) == {'flavour': 0, 'box': 1, 'text': 0,
                                   'eps': 0, 'eps_dpi': 300, 'images': 0}
    # None reuses the stored options, {} too
    info(doc, out)
    info(doc, out, options = {})
    assert info.GetOptions(doc)['box'] == 1
    # the options are kept per document and per format
    assert plugins.find_export_plugin('PDF').GetOptions(doc)['box'] == 0
    assert info.GetOptions(new_document())['box'] == 0


def test_get_options_is_a_copy():
    from Sketch.Base import plugins
    info = plugins.find_export_plugin('PDF')
    doc = new_document()
    options = info.GetOptions(doc)
    options['box'] = 1
    assert info.GetOptions(doc)['box'] == 0


def test_stored_options_are_completed_by_defaults():
    # options stored before a parameter was added get its default
    from Sketch.Base import plugins
    info = plugins.find_export_plugin('SVG')
    doc = new_document()
    doc.options['Export.SVG'] = {'text': 1}
    options = info.GetOptions(doc)
    assert options['text'] == 1 and options['eps_dpi'] == 300


def test_choices_are_translated():
    from Sketch.Base.plugins import translate_parameters
    params = (('box', 'choice', 0, ('Page', 'Bounding box'), 'Export area'),
              ('dpi', 'int', 300, (30, 2400), 'Resolution'))
    assert translate_parameters(params, str.upper) == (
        ('box', 'choice', 0, ('PAGE', 'BOUNDING BOX'), 'EXPORT AREA'),
        ('dpi', 'int', 300, (30, 2400), 'RESOLUTION'))


def test_parse_export_option():
    # skconvert -o NAME=VALUE
    import pytest
    from Sketch import SketchError
    from Sketch.Base import plugins
    info = plugins.find_export_plugin('SVG')
    parse = plugins.parse_export_option
    assert parse(info, 'box=1') == ('box', 1)
    assert parse(info, 'box=bounding') == ('box', 1)
    assert parse(info, 'box=Bounding box') == ('box', 1)
    assert parse(info, 'box=PAGE') == ('box', 0)
    assert parse(info, 'flavour=plain') == ('flavour', 1)
    assert parse(info, 'eps_dpi=600') == ('eps_dpi', 600)
    for bad in ('box=2', 'box=x', 'box=', 'eps_dpi=5', 'eps_dpi=x',
                'nosuch=1', 'box'):
        with pytest.raises(SketchError):
            parse(info, bad)
    info = plugins.find_export_plugin('PDF')
    assert parse(info, 'images=l') == ('images', 1)


def test_describe_export_options():
    from Sketch.Base import plugins
    text = plugins.describe_export_options(plugins.find_export_plugin('PDF'))
    assert '0 page (default)' in text and '1 bounding_box' in text
