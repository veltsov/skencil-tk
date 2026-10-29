# Sketch.Lib.util.ghostscript_command and the run_gs family (the GS
# environment variable support).


import shutil

import pytest

import testsupport


def test_default(monkeypatch):
    from Sketch.Lib.util import ghostscript_command
    monkeypatch.delenv('GS', raising=False)
    assert ghostscript_command() == 'gs'


def test_env_override(monkeypatch):
    from Sketch.Lib.util import ghostscript_command
    monkeypatch.setenv('GS', '/opt/gs/bin/skgs')
    assert ghostscript_command() == '/opt/gs/bin/skgs'


def test_env_override_path_with_spaces(monkeypatch):
    from Sketch.Lib.util import ghostscript_command
    monkeypatch.setenv('GS', '/opt/my gs/bin/skgs')
    assert ghostscript_command() == '/opt/my gs/bin/skgs'


def test_env_override_empty_means_unset(monkeypatch):
    from Sketch.Lib.util import ghostscript_command
    monkeypatch.setenv('GS', '')
    assert ghostscript_command() == 'gs'


def test_run_gs_output_version():
    # run_gs_output against the real interpreter, when one is available
    from Sketch.Lib.util import ghostscript_command, run_gs_output
    if shutil.which(ghostscript_command()) is None:
        pytest.skip('no ghostscript interpreter available')
    status, output = run_gs_output(['--version'])
    assert status == 0
    assert output.strip()
