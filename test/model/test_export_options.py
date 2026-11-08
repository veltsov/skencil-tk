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
    assert info.GetOptions(doc) == {'box': 0, 'eps': 0, 'eps_dpi': 300}
    out = testsupport.output_path('export-options', 'box.svg')
    info(doc, out, options = {'box': 1})
    assert info.GetOptions(doc) == {'box': 1, 'eps': 0, 'eps_dpi': 300}
    # None reuses the stored options, {} too
    info(doc, out)
    info(doc, out, options = {})
    assert info.GetOptions(doc)['box'] == 1
    # the options are kept per document and per format
    assert plugins.find_export_plugin('SVG-Inkscape').GetOptions(doc)['box'] \
           == 0
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
    info = plugins.find_export_plugin('SVG-Inkscape')
    doc = new_document()
    doc.options['Export.SVG-Inkscape'] = {'text': 1}
    options = info.GetOptions(doc)
    assert options['text'] == 1 and options['eps_dpi'] == 300


def test_choices_are_translated():
    from Sketch.Base.plugins import translate_parameters
    params = (('box', 'choice', 0, ('Page', 'Bounding box'), 'Export area'),
              ('dpi', 'int', 300, (30, 2400), 'Resolution'))
    assert translate_parameters(params, str.upper) == (
        ('box', 'choice', 0, ('PAGE', 'BOUNDING BOX'), 'EXPORT AREA'),
        ('dpi', 'int', 300, (30, 2400), 'RESOLUTION'))
