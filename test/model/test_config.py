# Layer 1: user configuration directory determination and the
# --configdir option (no display required).


import getopt

import pytest

import testsupport


def test_user_config_directory_xdg(monkeypatch):
    from Sketch.Base.configutil import user_config_directory
    monkeypatch.setenv('XDG_CONFIG_HOME', '/xdg/cfg')
    assert user_config_directory('/home/u') == '/xdg/cfg/skencil'


def test_user_config_directory_xdg_empty_means_unset(monkeypatch):
    from Sketch.Base.configutil import user_config_directory
    monkeypatch.setenv('XDG_CONFIG_HOME', '')
    assert user_config_directory('/home/u') == '/home/u/.config/skencil'


def test_user_config_directory_default(monkeypatch):
    from Sketch.Base.configutil import user_config_directory
    monkeypatch.delenv('XDG_CONFIG_HOME', raising=False)
    assert user_config_directory('/home/u') == '/home/u/.config/skencil'


def test_process_args_configdir():
    from Sketch.Base.main import process_args
    options = process_args(['--configdir', '/tmp/cfg', 'file.sk'])
    assert options.configdir == '/tmp/cfg'
    assert options.args == ['file.sk']


def test_process_args_without_configdir():
    from Sketch.Base.main import process_args
    options = process_args(['file.sk'])
    assert options.configdir is None


def test_process_args_rejects_unknown_option():
    from Sketch.Base.main import process_args
    with pytest.raises(getopt.error):
        process_args(['--no-such-option'])
