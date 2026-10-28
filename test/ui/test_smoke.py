# Layer 3+4: interactive application tests.  Each test runs the full
# application as a subprocess under Xvfb and drives it with a
# --run-script payload (test/ui/scripts/).  Screenshot tests compare
# against baselines recorded from the master build.


import os

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
    guard; see devdocs/modernize-paxtkinter.md)."""
    run_ui('smoke_dialog.py', args=[testsupport.data_path('tarr.sk')])


def test_open_about_box():
    """File->About must not crash (py3 regression guard: tkinter has no
    __version__ attribute there, so building the version string used to
    raise AttributeError)."""
    run_ui('smoke_about.py')


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
    (slider drag) path.  See devdocs/modernize-paxtkinter.md."""
    run_ui('smoke_scrollbars.py', args=[testsupport.data_path('tarr.sk')])


def test_zorder_moves():
    """Move To Top / Bottom / Up / Down (single and multi selection)
    must reorder the objects and undo must restore the original order
    (py3 regression guard: the permutation was a `range` object, which
    is immutable, so `del permutation[start]` raised TypeError)."""
    run_ui('smoke_zorder.py', args=[testsupport.data_path('tarr.sk')])


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
