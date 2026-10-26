#!/usr/bin/env python2
# Extract C-boundary type information from the skencil extension
# sources for the division audit (see devdocs/divaudit-findings.md).
#
# Parses, with regexes tuned to this codebase's declaration style:
#
# - `static struct PyMethodDef <table>[] = {...}` blocks: each
#   {"pyname", cfunc, ...} entry maps a Python-visible name to a C
#   function; the C function's PyArg_ParseTuple format (searched in the
#   function body) gives the expected argument types per position.
# - `static struct memberlist <table>[] = {...}` blocks: each
#   {"attr", T_XXX, ...} entry maps an attribute name to int/float
#   (T_DOUBLE/T_FLOAT/T_SKCOORD -> float, T_INT/T_LONG/T_CHAR -> int).
#
# Output JSON (default: devtools/divaudit/ctypes_catalog.json):
#
#   methods: {pyname: [ [position kinds...], ...]}   (multiple entries
#            when the same name is registered by several C functions)
#   attrs:   {attrname: [kinds...]}                  (ditto)
#
# A position kind is 'int', 'float' or 'other' ('O', 's', groups like
# '(idd)' are 'other' unless homogeneous).

import glob
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
# devtools/divaudit/ -> the repo root is two levels up
EXTENSIONS = os.path.join(os.path.dirname(os.path.dirname(HERE)),
                          'src', 'extensions')


def method_tables(src):
    for m in re.finditer(r'PyMethodDef\s+(\w+)\s*\[\]\s*=\s*\{(.*?)\n\};',
                         src, re.S):
        for e in re.finditer(r'\{\s*"([^"]+)"\s*,\s*'
                             r'(?:\(PyCFunction\))?(\w+)', m.group(2)):
            yield e.group(1), e.group(2)


def member_tables(src):
    for m in re.finditer(r'struct memberlist\s+(\w+)\s*\[\]\s*=\s*\{'
                         r'(.*?)\n\};', src, re.S):
        for e in re.finditer(r'\{\s*"([^"]+)"\s*,\s*(\w+)', m.group(2)):
            yield e.group(1), e.group(2)


def parse_format(fmt):
    """Translate a ParseTuple format into per-argument kinds."""
    kinds = []
    i = 0
    while i < len(fmt):
        ch = fmt[i]
        if ch in '|;:':
            if ch in ';:':
                break
            i += 1
            continue
        if ch == '(':
            j = fmt.index(')', i)
            inner = fmt[i + 1:j]
            if 'd' in inner or 'f' in inner:
                kinds.append('float')
            elif 'i' in inner or 'l' in inner:
                kinds.append('int')
            else:
                kinds.append('other')
            i = j + 1
            continue
        if ch in 'idf':
            if ch == 'i' and fmt[i:i + 2] == 'if':   # not a real combo
                kinds.append('int')
                i += 1
                continue
            kinds.append('int' if ch == 'i' else
                         ('float' if ch in 'df' else 'other'))
        elif ch in 'l':
            kinds.append('int')
        elif ch in 'OsSzbUw':
            kinds.append('other')
        # '#', '!', '*' etc. attach to the previous unit: no new arg
        i += 1
    return kinds


def function_format(src, cfunc):
    """The ParseTuple format of the C function CFUNC, or None."""
    m = re.search(r'(?:static\s+)?PyObject\s*\*\s*\n?%s\s*\(' % cfunc, src)
    if not m:
        return None
    body = src[m.start():m.start() + 4000]
    p = re.search(r'PyArg_ParseTuple\(\s*args\s*,\s*"([^"]*)"', body)
    if p:
        return p.group(1).split(';')[0].split(':')[0]
    return None


def main():
    # pass 1: C function identifier -> ParseTuple format (all files)
    cfunc_formats = {}
    for path in sorted(glob.glob(os.path.join(EXTENSIONS, '*', '*.c'))):
        if 'paxtkinter' in path or 'intl' in path or 'gcmethods' in path:
            continue                                # dead sources
        src = open(path).read()
        for m in re.finditer(r'(?:static\s+)?PyObject\s*\*\s*\n?(\w+)\s*\(',
                             src):
            fmt = function_format(src, m.group(1))
            if fmt is not None and m.group(1) not in cfunc_formats:
                cfunc_formats[m.group(1)] = fmt

    # pass 2: method tables -> python name -> C function -> format
    methods = {}
    attrs = {}
    nfuncs = 0
    for path in sorted(glob.glob(os.path.join(EXTENSIONS, '*', '*.c'))):
        if 'paxtkinter' in path or 'intl' in path or 'gcmethods' in path:
            continue                                # dead sources
        src = open(path).read()
        for pyname, cfunc in method_tables(src):
            fmt = cfunc_formats.get(cfunc)
            if fmt is None:
                continue
            nfuncs += 1
            kinds = parse_format(fmt)
            methods.setdefault(pyname, []).append(kinds)
        for attr, type_macro in member_tables(src):
            if type_macro in ('T_DOUBLE', 'T_FLOAT', 'T_SKCOORD'):
                kind = 'float'
            elif type_macro in ('T_INT', 'T_LONG', 'T_CHAR'):
                kind = 'int'
            else:
                kind = 'other'
            attrs.setdefault(attr, []).append(kind)

    out = os.path.join(HERE, 'ctypes_catalog.json')
    with open(out, 'w') as f:
        json.dump({'methods': methods, 'attrs': attrs}, f, indent=1,
                  sort_keys=True)
    print 'methods:', len(methods), ' (%d with formats)' % nfuncs
    print 'attrs:', len(attrs)
    print 'written to', out


if __name__ == '__main__':
    main()
