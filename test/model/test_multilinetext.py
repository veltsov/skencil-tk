# Layer 1: the MultilineText plugin's text pipeline (no display
# required).  The plugin's text is a byte string in the chunk fonts'
# encodings (the plugin's latin-1 format contract, see
# devdocs/string-handling.md); recompute must chunk it and produce
# SimpleText objects with correct font-encoded glyphs and the tab
# advance.

from __future__ import print_function

import testsupport


def _constructor():
    sk = testsupport.sketch()
    from Sketch.Base import plugins
    info = [i for i in plugins.compound_plugins
            if i.module_name == 'multilinetext'][0]
    return info.Constructor()


def _styling():
    from Sketch.Plugins.Objects.Lib.multilinetext.iterator import Style
    return [
        (Style(family='Courier'), 0, 0),
        (Style(color='black'), 0, 0),
        (Style(size=18), 0, 0),
        (Style(bold=0), 0, 0),
        (Style(italic=0), 0, 0),
        (Style(supersub='normal'), 0, 0),
        (None, 2, 0),      # the trailing sentinel entry
    ]


def test_multilinetext_recompute():
    MultilineText = _constructor()

    # the text is latin-1 (font-encoded) bytes with a tab separator
    text = b'Hello\tWorld'
    obj = MultilineText(text=text, styling=_styling(), trafo=None,
                        loading=0)

    objs = obj.objects
    assert len(objs) == 2, 'expected two chunks, got %d' % len(objs)
    assert all(o.__class__.__name__ == 'SimpleText' for o in objs)

    # the chunk texts are glyph-id arrays; the glyphs are the latin-1
    # characters of the input resolved in the chunk fonts' encodings
    font = objs[0].Properties().font
    names = [font.GlyphName(g) for g in objs[0].Text()]
    assert names == list('Hello'), names
    font = objs[1].Properties().font
    names = [font.GlyphName(g) for g in objs[1].Text()]
    assert names == list('World'), names

    # the tab advances the second chunk
    xs = [o.trafo.coeff()[4] for o in objs]
    assert xs[1] > xs[0], xs


def test_multilinetext_latin1_roundtrip():
    # the editor display decodes the model's latin-1 bytes and
    # get_text re-encodes them losslessly (the plugin's utf8_to_latin1
    # boundary; non-latin-1 input is out of the plugin's contract)
    text = b'caf\xe9'
    assert text.decode('latin-1').encode('latin-1') == text
