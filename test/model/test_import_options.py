# Layer 1: the options of import plugins (declared parameters, asked
# for by load.load_drawing through a callback -- in the UI
# plugindlg.ImportOptionsDlg -- and remembered for the session), with a
# stub plugin, so that no external tool is needed.

import types

import pytest

import testsupport


def setup_module(module):
    testsupport.sketch()


@pytest.fixture
def stub_plugin():
    """An import plugin for files starting with `SKTESTOPT', with the
    parameters `pages' (text) and `mode' (choice).  Its loader asks for
    the options (OptionInfo) unless the file contains `quiet'; the
    document gets one layer per option, named NAME=VALUE."""
    from Sketch.Base import plugins
    from Sketch.Base.load import GenericLoader

    class StubLoader(GenericLoader):
        def OptionInfo(self):
            self.file.seek(0)
            if b'quiet' in self.file.read():
                return None
            return 'a stub file'

        def Load(self):
            self.document()
            for name in sorted(self.options):
                self.layer('%s=%s' % (name, self.options[name]))
                self.end_layer()
            self.end_all()
            self.object.load_Completed()
            return self.object

    count = len(plugins.import_plugins)
    info = plugins.ImportInfo(
        'stub_options', '.', '^SKTESTOPT', 'StubLoader', 'StubFormat',
        tk_file_type = ('Stub', '.stub'), standard_messages = 1,
        parameters = (('pages', 'text', '1', (10, 1), 'Pages'),
                      ('mode', 'choice', 0, ('Fast', 'Exact'), 'Mode')))
    module = types.ModuleType('stub_options')
    module.StubLoader = StubLoader
    info.module = module
    # ImportInfo appends itself; match it before the real plugins
    plugins.import_plugins.remove(info)
    plugins.import_plugins.insert(0, info)
    try:
        yield info
    finally:
        plugins.import_plugins.remove(info)
        assert len(plugins.import_plugins) == count


def stub_file(name, text = ''):
    path = testsupport.output_path('import-options', name)
    with open(path, 'wb') as f:
        f.write(b'SKTESTOPT\n' + text.encode())
    return path


def layer_names(doc):
    return [layer.Name() for layer in doc.layers if not layer.is_SpecialLayer]


def test_defaults_and_explicit_options(stub_plugin):
    from Sketch.Base import load
    assert stub_plugin.get_default_options() == {'pages': '1', 'mode': 0}
    path = stub_file('a.stub')
    assert load.find_import_plugin(path) is stub_plugin
    assert layer_names(load.load_drawing(path)) == ['mode=0', 'pages=1']
    doc = load.load_drawing(path, options = {'mode': 1})
    assert layer_names(doc) == ['mode=1', 'pages=1']
    # remembered for the next import in the format
    assert stub_plugin.GetOptions() == {'pages': '1', 'mode': 1}
    assert layer_names(load.load_drawing(path)) == ['mode=1', 'pages=1']


def test_ask_options(stub_plugin):
    from Sketch.Base import load
    from Sketch import SketchLoadCancelled
    asked = []
    def ask(info, description, options):
        asked.append((info, description, dict(options)))
        return dict(options, pages = '2-3')
    doc = load.load_drawing(stub_file('b.stub'), ask_options = ask)
    assert asked == [(stub_plugin, 'a stub file',
                      {'pages': '1', 'mode': 0})]
    assert layer_names(doc) == ['mode=0', 'pages=2-3']
    assert stub_plugin.GetOptions()['pages'] == '2-3'
    # no question if the loader needs none
    asked[:] = []
    load.load_drawing(stub_file('c.stub', 'quiet'), ask_options = ask)
    assert not asked
    with pytest.raises(SketchLoadCancelled):
        load.load_drawing(stub_file('d.stub'),
                          ask_options = lambda *args: None)


def test_gzipped_file_passes_options(stub_plugin):
    import gzip
    from Sketch.Base import load
    path = testsupport.output_path('import-options', 'e.stub.gz')
    with gzip.open(path, 'wb') as f:
        f.write(b'SKTESTOPT\n')
    doc = load.load_drawing(path, options = {'pages': '4'})
    assert layer_names(doc) == ['mode=0', 'pages=4']


def test_parse_plugin_option(stub_plugin):
    from Sketch.Base import plugins
    from Sketch import SketchError
    assert plugins.parse_plugin_option(stub_plugin, 'pages=1,3') \
        == ('pages', '1,3')
    assert plugins.parse_plugin_option(stub_plugin, 'mode=exact') \
        == ('mode', 1)
    with pytest.raises(SketchError):
        plugins.parse_plugin_option(stub_plugin, 'pagez=1')
    assert plugins.parse_export_option is plugins.parse_plugin_option


def test_plugins_without_parameters_are_unchanged():
    # e.g. the native format: no options, no question
    from Sketch.Base import load, plugins
    path = testsupport.output_path('import-options', 'plain.sk')
    from Sketch import EditDocument
    plugins.find_export_plugin('SK-1')(EditDocument(create_layer = 1), path)
    def ask(*args):
        raise AssertionError('asked')
    load.load_drawing(path, ask_options = ask)
    assert load.find_import_plugin(path).parameters == ()
