# Layer 3+4: interactive application tests.  Each test runs the full
# application as a subprocess under Xvfb and drives it with a
# --run-script payload (test/ui/scripts/).  Screenshot tests compare
# against baselines recorded from the master build.


import os
import re

import pytest

import testsupport

SCRIPTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'scripts')


def script(name):
    return os.path.join(SCRIPTS, name)


def run_ui(script_name, args=(), script_env=None, timeout=90):
    env = dict(script_env or {})
    env.setdefault('SKENCIL_TEST_HEADLESS', '1')
    return testsupport.assert_clean_exit(list(args), script=script(script_name),
                                         script_env=env, timeout=timeout)


# ------------------------------------------------------------ smoke tests

def test_bare_launch():
    """The application must start and exit cleanly without a file."""
    run_ui('smoke_quit.py')


@pytest.mark.parametrize('name', testsupport.fixtures())
def test_open_fixture(name):
    """Every fixture must open in the full application; a few document
    operations are applied and the app must exit cleanly."""
    run_ui('smoke_open.py', args=[testsupport.data_path(name)])


def test_open_layer_dialog():
    """Opening the Layers dialog must not crash (pax/GIL regression
    guard)."""
    run_ui('smoke_dialog.py', args=[testsupport.data_path('tarr.sk')])


def test_links_panel(tmp_path):
    """A document with missing linked files opens (with a warning);
    the Links panel lists them (also the image used as a fill pattern)
    and relinks, embeds and toggles the automatic update."""
    import shutil
    sys_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            '..', 'model')
    import sys
    sys.path.insert(0, sys_path)
    import test_links
    test_links.clear_cache()
    sk_file, eps_file, png_file = test_links.make_document(tmp_path,
                                                           pattern=1)
    shutil.move(eps_file, eps_file + '.new')
    shutil.move(png_file, png_file + '.new')
    out, err = run_ui('smoke_links.py', args=[sk_file],
                          script_env={
                              'SKENCIL_TEST_LINKS_EPS': eps_file + '.new',
                              'SKENCIL_TEST_LINKS_PNG': png_file + '.new'})
    assert b'LINKS-OK' in out, (out, err)


def test_open_about_box():
    """File->About must not crash (py3 regression guard: tkinter has no
    __version__ attribute there, so building the version string used to
    raise AttributeError)."""
    run_ui('smoke_about.py')


def test_image_tools_scripts(tmp_path):
    """The Extract Image and Replace Image scripts run from the script
    registry on an image inside a mask group."""
    run_ui('smoke_image_tools.py',
           script_env={'SKENCIL_TEST_OUT': str(tmp_path)})


def test_open_plugin_dialog():
    """Opening the Autoshapes plugin dialog must not crash (py3
    regression guard: the icon palettes go through PIL putpalette,
    which requires bytes under Pillow 9)."""
    run_ui('smoke_plugin_dialog.py')


def test_scrollbar_wheel():
    """Wheel events on the scrollbars must scroll and must not crash:
    Tk's scrollbar bindings invoke the pax widget command directly from
    the Tcl event dispatch (unlike tk.call), which used to abort with
    `Fatal Python error: PyEval_RestoreThread: NULL tstate'.  Also
    covers horizontal wheel scrolling over the hbar and the MOVETO
    (slider drag) path."""
    run_ui('smoke_scrollbars.py', args=[testsupport.data_path('tarr.sk')])


def test_zorder_moves():
    """Move To Top / Bottom / Up / Down (single and multi selection)
    must reorder the objects and undo must restore the original order
    (py3 regression guard: the permutation was a `range` object, which
    is immutable, so `del permutation[start]` raised TypeError)."""
    run_ui('smoke_zorder.py', args=[testsupport.data_path('tarr.sk')])


EXPORT_MAGIC = {'SK-1': b'##Sketch', 'EPS': b'%!PS-Adobe', 'PS': b'%!PS-Adobe',
                'PDF': b'%PDF',
                'SVG': b'<?xml',
                'WMF': b'\xd7\xcd\xc6\x9a'}


def test_export_all_formats():
    """Every export plugin, Export Again and the compressed save must
    work through the main window's SaveToFile (py3 regression guard:
    the PDF filters, WMF, the compressed save and Export Again all
    failed, and no test went through them; File->Export did not enable
    Export Again).  The options dialog of File->Export is answered by a
    stub (see test_export_options_dialog)."""
    import gzip
    outdir = testsupport.output_dir('export')
    for name in os.listdir(outdir):
        os.remove(os.path.join(outdir, name))
    out, err = run_ui('smoke_export.py',
                      args=[testsupport.data_path('tarr.sk')],
                      script_env={'SKENCIL_EXPORT_DIR': outdir})
    # SaveToFile reports failures in a message box
    assert b'MessageBox' not in out, out.decode('utf-8', 'replace')
    testsupport.sketch()
    from Sketch.Base import plugins
    formats = [info.format_name for info in plugins.export_plugins]
    assert set(formats) == set(EXPORT_MAGIC)
    for fmt in formats:
        with open(os.path.join(outdir, 'export.' + fmt), 'rb') as f:
            assert f.read().startswith(EXPORT_MAGIC[fmt]), fmt
    # written by Export Again after File->Export with the export area
    # set to the bounding box
    with open(os.path.join(outdir, 'interactive.pdf'), 'rb') as f:
        data = f.read()
    assert data.startswith(b'%PDF')
    with open(os.path.join(outdir, 'export.PDF'), 'rb') as f:
        page = f.read()
    mediabox = re.compile(br'/MediaBox\s*\[([^\]]*)\]')
    assert mediabox.search(data).group(1) != mediabox.search(page).group(1)
    with gzip.open(os.path.join(outdir, 'compressed.sk.gz')) as f:
        assert f.read().startswith(b'##Sketch')


def test_import_options_dialog():
    """File -> Open and Insert Document of a multi-page PostScript file
    ask for the pages (plugindlg.ImportOptionsDlg); Cancel does
    nothing."""
    import shutil
    if not (shutil.which('pdftocairo') and shutil.which('pdfinfo')):
        pytest.skip('poppler-utils not installed')
    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(
        os.path.abspath(__file__)), '..', 'formats'))
    import test_psimport
    run_ui('smoke_import_options.py',
           args=[testsupport.data_path('tarr.sk')],
           script_env={'SKENCIL_TEST_PS': test_psimport.multi_page()})


def test_export_options_dialog():
    """The export options dialog must offer the parameters of every
    export plugin that has them and return the chosen options."""
    run_ui('smoke_export_options.py', args=[testsupport.data_path('tarr.sk')])


# ------------------------------------------------------- screenshot tests

SHOT_FIXTURE = 'tarr.sk'


def _shot(script_name, baseline_name, tol=10, max_frac=0.002):
    out = testsupport.output_path('shots', baseline_name)
    run_ui(script_name, args=[testsupport.data_path(SHOT_FIXTURE)],
           script_env={'SKENCIL_SHOT_FILE': out})
    assert os.path.exists(out), 'screenshot was not captured'
    testsupport.compare_image('shots', baseline_name, out,
                              tol=tol, max_frac=max_frac)


def test_screenshot_basic():
    _shot('shot_basic.py', 'tarr-basic.png')


def test_screenshot_mutated():
    _shot('shot_mutated.py', 'tarr-mutated.png', max_frac=0.004)


def test_screenshot_xdotool_move():
    _shot('shot_xdotool.py', 'tarr-xdotool-move.png', max_frac=0.004)
