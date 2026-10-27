# Layer 1: Scripting registry menu-path handling (no display required).
#
# The menu path components are user-visible strings (K1): the scripts
# pass unicode literals, and ScriptRegistry.Add must reject byte strings
# loudly instead of iterating them character by character (which used to
# produce single-letter nested submenus in the Script menu; see
# devdocs/unicode-runtime-audit.md, instance 6).

from __future__ import print_function

import pytest

import testsupport


class _FakeScript:

    def __init__(self, name):
        self.name = name

    def Title(self):
        return self.name


def _registry():
    testsupport.sketch()
    from Sketch.Scripting.registry import ScriptRegistry
    return ScriptRegistry()


def _tree_keys(tree):
    return [key for key, value in tree]


def test_menu_tree_unicode_path_single_level():
    reg = _registry()
    reg.Add(_FakeScript(u'script1'), u'TeX')
    tree = reg.MenuTree()
    assert _tree_keys(tree) == [u'TeX']
    assert _tree_keys(tree[0][1]) == [u'script1']


def test_menu_tree_unicode_path_tuple_nested():
    reg = _registry()
    reg.Add(_FakeScript(u'script1'), (u'Arrange', u'Horizontally'))
    tree = reg.MenuTree()
    assert _tree_keys(tree) == [u'Arrange']
    assert _tree_keys(tree[0][1]) == [u'Horizontally']


def test_menu_tree_byte_string_path_rejected():
    # A byte string used to be iterated character by character
    # (Script -> T -> e -> X); the strict unicode policy rejects it.
    # (the byte string is spelled b'TeX': under python2 the plain
    # literal was a byte string already)
    reg = _registry()
    with pytest.raises(TypeError):
        reg.Add(_FakeScript(u'script1'), b'TeX')


def test_menu_tree_byte_component_in_sequence_rejected():
    reg = _registry()
    with pytest.raises(TypeError):
        reg.Add(_FakeScript(u'script1'), (u'Arrange', b'x'))
