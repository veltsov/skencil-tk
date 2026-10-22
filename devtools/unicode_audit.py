#!/usr/bin/env python2
# Static string-origin audit for skencil-tk (see
# devdocs/string-handling.md and devdocs/unicode-runtime-audit.md,
# Layer 3).
#
# AST-based check of the string-handling conventions:
#
#   1. `basestring` is banned: K2 values are `unicode` in the model, so
#      dispatch checks use `unicode`; "any string" checks spell out
#      `(str, unicode)`.
#   2. `isinstance(x, str)` (py2: a bytes check) is allowed only in the
#      whitelisted modules where it is a documented boundary or K5
#      identifier check.
#   3. `repr()` applied to stringish values is allowed only in the
#      whitelisted serialization/debug sinks; K2/K4 display sinks must
#      use `skrepr`/`as_unicode`/`as_display_name`.
#
# Limitations: rules 2/3 are whitelisted per module (not per line), and
# the stringish heuristic for rule 3 matches the source line against a
# name pattern.  Calibration against the pre-fix revisions of the
# historical bugs (unicode-runtime-audit.md, instances 1-4) is a
# follow-up; run with -v to dump the full inventory.
#
# Usage: devtools/unicode_audit.py [-v] [srcdir]

import ast
import os
import re
import sys

STRINGISH = re.compile(r'(name|file|path|txt|text|label|title|msg|message)')

# modules where isinstance(x, str) is a documented boundary/K5 check
STR_CHECK_WHITELIST = set([
    'Sketch/Base/load.py',          # filename vs file object (K4)
    'Sketch/Base/warn.py',          # warn level name (K5)
    'Sketch/Graphics/document.py',  # issue constant (K5)
    'Sketch/Graphics/image.py',     # filename vs file object (K4)
    'Sketch/Graphics/psdevice.py',  # filename vs file object (K4)
    'Sketch/Lib/type1.py',          # fontfile vs file object (K4)
    'Sketch/Lib/util.py',           # the conversion helpers themselves
    'Sketch/UI/command.py',         # key_stroke (K5)
    'Sketch/UI/tkext.py',           # bitmap/label dispatch (K5)
    'Sketch/UI/sketchdlg.py',       # bitmap (K5)
    'Sketch/UI/palette.py',         # color index (K5)
    'Plugins/Filters/ailoader.py',  # AI tokens (K5)
    'Plugins/Filters/skloader.py',  # functions dict names (K5)
])

# modules where repr() of computed values is allowed (debug output over
# file bytes, or the skrepr serialization choke point itself)
REPR_WHITELIST = set([
    'Plugins/Filters/sksaver.py',       # skrepr definition
    'Plugins/Filters/skloader.py',      # warn(INTERNAL, repr(line))
    'Plugins/Filters/xfigloader.py',    # warn paths over file lines
    'Plugins/Filters/ailoader.py',      # debug messages
    'Plugins/Filters/cmxloader.py',     # _print debug dumps
    'Sketch/Lib/type1.py',              # __main__ debug dump
    'Sketch/UI/palette.py',             # repr(int) index in a name
    'Script/export_raster.py',          # warn over gs command line
])


def iter_py_files(srcdir):
    for dirpath, dirnames, filenames in os.walk(srcdir):
        dirnames[:] = [d for d in dirnames
                       if d not in ('build', 'old', 'AppDir', 'tests')]
        for fn in filenames:
            if fn.endswith('.py'):
                yield os.path.join(dirpath, fn)


def relname(srcdir, path):
    return os.path.relpath(path, srcdir)


def audit_file(path, name, violations, inventory):
    with open(path, 'rb') as f:
        source = f.read()
    try:
        tree = ast.parse(source, filename=name)
    except SyntaxError as e:
        violations.append('%s: SYNTAX ERROR: %s' % (name, e))
        return
    lines = source.splitlines()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id == 'basestring':
            violations.append('%s:%d: basestring used'
                              % (name, getattr(node, 'lineno', 0)))
        elif isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name) and func.id == 'isinstance' \
               and len(node.args) == 2:
                typespec = node.args[1]
                names = []
                if isinstance(typespec, ast.Name):
                    names = [typespec.id]
                elif isinstance(typespec, ast.Tuple):
                    names = [e.id for e in typespec.elts
                             if isinstance(e, ast.Name)]
                if 'str' in names:
                    if name not in STR_CHECK_WHITELIST:
                        violations.append(
                            '%s:%d: isinstance(x, str) outside whitelist'
                            % (name, node.lineno))
                    if inventory is not None:
                        inventory.append('%s:%d: isinstance str check: %s'
                                         % (name, node.lineno,
                                            lines[node.lineno - 1].strip()))
            elif isinstance(func, ast.Name) and func.id == 'repr' \
                    and node.args:
                line = lines[node.lineno - 1]
                if STRINGISH.search(line) and name not in REPR_WHITELIST:
                    violations.append(
                        '%s:%d: repr() of stringish value outside whitelist'
                        % (name, node.lineno))
                if inventory is not None:
                    inventory.append('%s:%d: repr(): %s'
                                     % (name, node.lineno, line.strip()))
            elif isinstance(func, ast.Attribute) \
                    and func.attr in ('decode', 'encode'):
                if inventory is not None:
                    inventory.append('%s:%d: %s(): %s'
                                     % (name, node.lineno, func.attr,
                                        lines[node.lineno - 1].strip()))


def main(argv):
    verbose = '-v' in argv
    args = [a for a in argv if not a.startswith('-')]
    srcdir = os.path.abspath(args[0] if args else
                             os.path.join(os.path.dirname(__file__),
                                          '..', 'src'))
    violations = []
    inventory = [] if verbose else None
    for path in iter_py_files(srcdir):
        audit_file(path, relname(srcdir, path), violations, inventory)
    if inventory is not None:
        for entry in inventory:
            print(entry)
        print('--- inventory: %d entries' % len(inventory))
    if violations:
        for v in violations:
            print('VIOLATION:', v)
        print('--- %d violation(s)' % len(violations))
        return 1
    print('no violations')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
