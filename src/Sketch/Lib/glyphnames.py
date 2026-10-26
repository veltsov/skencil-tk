# Sketch - A Python-based drawing program
# Copyright (C) 2026 by the skencil-tk contributors
#
# This library is free software; you can redistribute it and/or modify
# it under the terms of the GNU Library General Public License as
# published by the Free Software Foundation; either version 2 of the
# License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Library General Public License for more details.
#
# You should have received a copy of the GNU Library General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA 02111-1307
# USA

#
# Conversion between unicode characters and Adobe glyph names.
#
# Text object content is a sequence of glyph indices (see
# devdocs/glyph-text.md); this module provides the unicode side of the
# mapping.  The latin-1 range is covered exactly by the
# encoding.iso_latin_1 table (whose entries are Adobe glyph names);
# characters outside it are mapped to AGL `uniXXXX` names, which fonts
# with the corresponding glyphs will resolve.
#
# The complete Adobe Glyph List (beyond the latin-1 names) may be added
# here later for full unicode round-tripping.

from Sketch.Lib import encoding

notdef = encoding.notdef

# reserved glyph names for the control codes that may occur in
# historical .sk files (quoted as \n, \r octal escapes inside txt()/pt()
# strings)
NEWLINE = 'newline'
CARRIAGE_RETURN = 'carriagereturn'

_control_names = {0x0A: NEWLINE, 0x0D: CARRIAGE_RETURN}
_control_codes = dict([(v, k) for k, v in _control_names.items()])

# name -> latin-1 code, first occurrence wins
_name_to_code = {}
for _code in range(256):
    _name = encoding.iso_latin_1[_code]
    if _name != notdef and _name not in _name_to_code:
        _name_to_code[_name] = _code


def unicode_to_glyphname(char):
    """Return the Adobe glyph name for the single unicode character
    CHAR, or None if it has none (notdef names, private use etc.)."""
    code = ord(char)
    if code < 256:
        name = _control_names.get(code)
        if name is not None:
            return name
        name = encoding.iso_latin_1[code]
        if name != notdef:
            return name
        return None
    if 0xE000 <= code <= 0xF8FF:
        # private use area: no meaningful glyph name
        return None
    return 'uni%04X' % code


def glyphname_to_unicode(name):
    """Return the unicode character for the Adobe glyph name NAME, or
    None if the name has no sensible unicode equivalent."""
    code = _control_codes.get(name)
    if code is not None:
        return chr(code)
    code = _name_to_code.get(name)
    if code is not None:
        return chr(code)
    if name.startswith('uni') and len(name) == 7:
        try:
            return chr(int(name[3:], 16))
        except ValueError:
            return None
    if name.startswith('u') and len(name) in (5, 6, 7):
        # AGL names for characters above U+FFFF: uXXXX[X[X]]
        try:
            code = int(name[1:], 16)
        except ValueError:
            return None
        if 0x10000 <= code <= 0x10FFFF:
            return chr(code)
    return None


def glyphnames_to_unicode(names, unknown='?'):
    """Return a unicode string for the sequence of glyph NAMES.
    Names without a unicode equivalent are replaced by UNKNOWN."""
    chars = []
    for name in names:
        char = glyphname_to_unicode(name)
        chars.append(char if char is not None else unknown)
    return u''.join(chars)
