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

# The legacy afiiNNNNN glyph names (the naming scheme of classic
# Cyrillic, Hebrew and Arabic Type 1 fonts) are not part of AGLFN
# (AGLFN 1.7 dropped them in favor of uniXXXX names), but they are the
# names used by classic Cyrillic Type 1 fonts (pscyr, URW Cyrillic,
# cm-super).  The alias table below is the afii subset of the Adobe
# Glyph List 2.0 (as shipped e.g. in ghostscript's gs_agl.ps); see
# devdocs/text-input.md.
_afii_to_unicode = {
    'afii00208': 0x2015,
    'afii08941': 0x20A4,
    'afii10017': 0x0410,
    'afii10018': 0x0411,
    'afii10019': 0x0412,
    'afii10020': 0x0413,
    'afii10021': 0x0414,
    'afii10022': 0x0415,
    'afii10023': 0x0401,
    'afii10024': 0x0416,
    'afii10025': 0x0417,
    'afii10026': 0x0418,
    'afii10027': 0x0419,
    'afii10028': 0x041A,
    'afii10029': 0x041B,
    'afii10030': 0x041C,
    'afii10031': 0x041D,
    'afii10032': 0x041E,
    'afii10033': 0x041F,
    'afii10034': 0x0420,
    'afii10035': 0x0421,
    'afii10036': 0x0422,
    'afii10037': 0x0423,
    'afii10038': 0x0424,
    'afii10039': 0x0425,
    'afii10040': 0x0426,
    'afii10041': 0x0427,
    'afii10042': 0x0428,
    'afii10043': 0x0429,
    'afii10044': 0x042A,
    'afii10045': 0x042B,
    'afii10046': 0x042C,
    'afii10047': 0x042D,
    'afii10048': 0x042E,
    'afii10049': 0x042F,
    'afii10050': 0x0490,
    'afii10051': 0x0402,
    'afii10052': 0x0403,
    'afii10053': 0x0404,
    'afii10054': 0x0405,
    'afii10055': 0x0406,
    'afii10056': 0x0407,
    'afii10057': 0x0408,
    'afii10058': 0x0409,
    'afii10059': 0x040A,
    'afii10060': 0x040B,
    'afii10061': 0x040C,
    'afii10062': 0x040E,
    'afii10063': 0xF6C4,
    'afii10064': 0xF6C5,
    'afii10065': 0x0430,
    'afii10066': 0x0431,
    'afii10067': 0x0432,
    'afii10068': 0x0433,
    'afii10069': 0x0434,
    'afii10070': 0x0435,
    'afii10071': 0x0451,
    'afii10072': 0x0436,
    'afii10073': 0x0437,
    'afii10074': 0x0438,
    'afii10075': 0x0439,
    'afii10076': 0x043A,
    'afii10077': 0x043B,
    'afii10078': 0x043C,
    'afii10079': 0x043D,
    'afii10080': 0x043E,
    'afii10081': 0x043F,
    'afii10082': 0x0440,
    'afii10083': 0x0441,
    'afii10084': 0x0442,
    'afii10085': 0x0443,
    'afii10086': 0x0444,
    'afii10087': 0x0445,
    'afii10088': 0x0446,
    'afii10089': 0x0447,
    'afii10090': 0x0448,
    'afii10091': 0x0449,
    'afii10092': 0x044A,
    'afii10093': 0x044B,
    'afii10094': 0x044C,
    'afii10095': 0x044D,
    'afii10096': 0x044E,
    'afii10097': 0x044F,
    'afii10098': 0x0491,
    'afii10099': 0x0452,
    'afii10100': 0x0453,
    'afii10101': 0x0454,
    'afii10102': 0x0455,
    'afii10103': 0x0456,
    'afii10104': 0x0457,
    'afii10105': 0x0458,
    'afii10106': 0x0459,
    'afii10107': 0x045A,
    'afii10108': 0x045B,
    'afii10109': 0x045C,
    'afii10110': 0x045E,
    'afii10145': 0x040F,
    'afii10146': 0x0462,
    'afii10147': 0x0472,
    'afii10148': 0x0474,
    'afii10192': 0xF6C6,
    'afii10193': 0x045F,
    'afii10194': 0x0463,
    'afii10195': 0x0473,
    'afii10196': 0x0475,
    'afii10831': 0xF6C7,
    'afii10832': 0xF6C8,
    'afii10846': 0x04D9,
    'afii299': 0x200E,
    'afii300': 0x200F,
    'afii301': 0x200D,
    'afii57381': 0x066A,
    'afii57388': 0x060C,
    'afii57392': 0x0660,
    'afii57393': 0x0661,
    'afii57394': 0x0662,
    'afii57395': 0x0663,
    'afii57396': 0x0664,
    'afii57397': 0x0665,
    'afii57398': 0x0666,
    'afii57399': 0x0667,
    'afii57400': 0x0668,
    'afii57401': 0x0669,
    'afii57403': 0x061B,
    'afii57407': 0x061F,
    'afii57409': 0x0621,
    'afii57410': 0x0622,
    'afii57411': 0x0623,
    'afii57412': 0x0624,
    'afii57413': 0x0625,
    'afii57414': 0x0626,
    'afii57415': 0x0627,
    'afii57416': 0x0628,
    'afii57417': 0x0629,
    'afii57418': 0x062A,
    'afii57419': 0x062B,
    'afii57420': 0x062C,
    'afii57421': 0x062D,
    'afii57422': 0x062E,
    'afii57423': 0x062F,
    'afii57424': 0x0630,
    'afii57425': 0x0631,
    'afii57426': 0x0632,
    'afii57427': 0x0633,
    'afii57428': 0x0634,
    'afii57429': 0x0635,
    'afii57430': 0x0636,
    'afii57431': 0x0637,
    'afii57432': 0x0638,
    'afii57433': 0x0639,
    'afii57434': 0x063A,
    'afii57440': 0x0640,
    'afii57441': 0x0641,
    'afii57442': 0x0642,
    'afii57443': 0x0643,
    'afii57444': 0x0644,
    'afii57445': 0x0645,
    'afii57446': 0x0646,
    'afii57448': 0x0648,
    'afii57449': 0x0649,
    'afii57450': 0x064A,
    'afii57451': 0x064B,
    'afii57452': 0x064C,
    'afii57453': 0x064D,
    'afii57454': 0x064E,
    'afii57455': 0x064F,
    'afii57456': 0x0650,
    'afii57457': 0x0651,
    'afii57458': 0x0652,
    'afii57470': 0x0647,
    'afii57505': 0x06A4,
    'afii57506': 0x067E,
    'afii57507': 0x0686,
    'afii57508': 0x0698,
    'afii57509': 0x06AF,
    'afii57511': 0x0679,
    'afii57512': 0x0688,
    'afii57513': 0x0691,
    'afii57514': 0x06BA,
    'afii57519': 0x06D2,
    'afii57534': 0x06D5,
    'afii57636': 0x20AA,
    'afii57645': 0x05BE,
    'afii57658': 0x05C3,
    'afii57664': 0x05D0,
    'afii57665': 0x05D1,
    'afii57666': 0x05D2,
    'afii57667': 0x05D3,
    'afii57668': 0x05D4,
    'afii57669': 0x05D5,
    'afii57670': 0x05D6,
    'afii57671': 0x05D7,
    'afii57672': 0x05D8,
    'afii57673': 0x05D9,
    'afii57674': 0x05DA,
    'afii57675': 0x05DB,
    'afii57676': 0x05DC,
    'afii57677': 0x05DD,
    'afii57678': 0x05DE,
    'afii57679': 0x05DF,
    'afii57680': 0x05E0,
    'afii57681': 0x05E1,
    'afii57682': 0x05E2,
    'afii57683': 0x05E3,
    'afii57684': 0x05E4,
    'afii57685': 0x05E5,
    'afii57686': 0x05E6,
    'afii57687': 0x05E7,
    'afii57688': 0x05E8,
    'afii57689': 0x05E9,
    'afii57690': 0x05EA,
    'afii57694': 0xFB2A,
    'afii57695': 0xFB2B,
    'afii57700': 0xFB4B,
    'afii57705': 0xFB1F,
    'afii57716': 0x05F0,
    'afii57717': 0x05F1,
    'afii57718': 0x05F2,
    'afii57723': 0xFB35,
    'afii57793': 0x05B4,
    'afii57794': 0x05B5,
    'afii57795': 0x05B6,
    'afii57796': 0x05BB,
    'afii57797': 0x05B8,
    'afii57798': 0x05B7,
    'afii57799': 0x05B0,
    'afii57800': 0x05B2,
    'afii57801': 0x05B1,
    'afii57802': 0x05B3,
    'afii57803': 0x05C2,
    'afii57804': 0x05C1,
    'afii57806': 0x05B9,
    'afii57807': 0x05BC,
    'afii57839': 0x05BD,
    'afii57841': 0x05BF,
    'afii57842': 0x05C0,
    'afii57929': 0x02BC,
    'afii61248': 0x2105,
    'afii61289': 0x2113,
    'afii61352': 0x2116,
    'afii61573': 0x202C,
    'afii61574': 0x202D,
    'afii61575': 0x202E,
    'afii61664': 0x200C,
    'afii63167': 0x066D,
    'afii64937': 0x02BD,
}
_unicode_to_afii = {}
for _name, _code in _afii_to_unicode.items():
    _unicode_to_afii.setdefault(_code, []).append(_name)
_unicode_to_afii = dict([(k, tuple(v))
                         for k, v in _unicode_to_afii.items()])


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


def unicode_to_glyphnames(char):
    """Return a tuple of candidate Adobe glyph names for the single
    unicode character CHAR, most canonical first, or the empty tuple
    if it has none (notdef names, private use etc.).  The canonical
    name (the encoding-table name for latin-1, uniXXXX otherwise) is
    first; for characters outside latin-1 the legacy afii names of
    the Adobe Glyph List follow (see devdocs/text-input.md)."""
    code = ord(char)
    if code < 256:
        name = unicode_to_glyphname(char)
        if name is None:
            return ()
        if code == 0x2D:
            # the encoding-table quirk: byte 45 is named 'minus' for
            # standard-encoding fonts, but the glyph is named
            # 'hyphen' in virtually every AFM; try both (see
            # devdocs/text-input.md, "Known quirk")
            return ('minus', 'hyphen')
        return (name,)
    if 0xE000 <= code <= 0xF8FF:
        # private use area: no meaningful glyph name
        return ()
    return ('uni%04X' % code,) + _unicode_to_afii.get(code, ())


def glyphname_to_unicode(name):
    """Return the unicode character for the Adobe glyph name NAME, or
    None if the name has no sensible unicode equivalent."""
    code = _control_codes.get(name)
    if code is not None:
        return chr(code)
    code = _name_to_code.get(name)
    if code is not None:
        return chr(code)
    code = _afii_to_unicode.get(name)
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
