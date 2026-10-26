#!/usr/bin/env python2
# Static inventory of `/` division sites in the skencil source tree --
# first step of the integer-division audit for the Python 3 port (see
# devdocs/python3-porting.md, "Semantics to audit").
#
# For every .py file under the given roots (default: src/, AppDir/
# and build/ excluded) it records each `a / b` node with its
# position, a source-line snippet, and a classification:
#
#   int-int        both operands are integer literals -- guaranteed
#                  to change value (floor) and type (int -> float)
#                  under py3 unless the division is exact
#   float-literal  at least one operand is a float literal -- true
#                  division on py2 already; safe in almost all cases
#   dynamic        at least one operand is computed at runtime -- the
#                  interesting set; intersect with the runtime
#                  warning log produced by
#                  devtools/divaudit/python2-divaudit
#
# Files that fail to parse under py2 (the 12 known py3-syntax-error
# files) fall back to a regex approximation, flagged as such.
#
# Per file it also records whether `from __future__ import division`
# is already present and the number of `//` (FloorDiv) sites.
#
# Usage: devtools/divaudit/scan_division.py [-o OUT.json] [root ...]

import ast
import json
import optparse
import os
import re
import sys

SKIP_DIRS = set(['AppDir', 'build', '.git', '__pycache__'])

# approximation for files that do not parse under py2: `x / y` with
# operand-looking characters on both sides
DIVISH = re.compile(r"[\w\)\]'\"]\s*/\s*[\w\(\['\"]")


def literal_desc(node):
    """Describe a node for classification; returns (kind, text)."""
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        kind, text = literal_desc(node.operand)
        return (kind, '-' + text)
    if isinstance(node, ast.Num):
        return (type(node.n).__name__, repr(node.n))
    if isinstance(node, ast.Name):
        return ('name', node.id)
    if isinstance(node, ast.Attribute):
        base = getattr(node.value, 'id', '')
        if isinstance(node.value, ast.Attribute):
            base = node.value.attr
        return ('attr', '%s.%s' % (base, node.attr))
    return (type(node).__name__.lower(), '')


def site_category(left, right):
    lkind = left[0]
    rkind = right[0]
    if lkind in ('int', 'long') and rkind in ('int', 'long'):
        return 'int-int'
    if lkind == 'float' or rkind == 'float':
        return 'float-literal'
    return 'dynamic'

def scan_file(path, relpath):
    record = {'path': relpath, 'future_division': False,
              'parse_error': None, 'floordiv': 0, 'sites': []}
    source = open(path, 'r').read()
    sourcelines = source.splitlines()
    try:
        tree = ast.parse(source, path)
    except SyntaxError, e:
        record['parse_error'] = str(e)
        for i, line in enumerate(sourcelines, 1):
            if DIVISH.search(line) and '//' not in line:
                record['sites'].append({
                    'line': i, 'col': None, 'category': 'regex-approx',
                    'left': None, 'right': None,
                    'source': line.strip()})
        return record

    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == '__future__':
            if any(a.name == 'division' for a in node.names):
                record['future_division'] = True
        elif isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
            left = literal_desc(node.left)
            right = literal_desc(node.right)
            line = node.lineno
            record['sites'].append({
                'line': line, 'col': node.col_offset,
                'category': site_category(left, right),
                'left': left, 'right': right,
                'source': (sourcelines[line - 1].strip()
                           if line <= len(sourcelines) else '')})
        elif isinstance(node, ast.BinOp) and isinstance(node.op,
                                                        ast.FloorDiv):
            record['floordiv'] += 1
    return record


def main():
    parser = optparse.OptionParser()
    parser.add_option('-o', '--out', dest='out',
                      default='/tmp/divaudit/static.json',
                      help='JSON output path (default %default)')
    options, args = parser.parse_args()

    # devtools/divaudit/scan_division.py -> repo root is three levels up
    repo = os.path.dirname(os.path.dirname(
        os.path.dirname(os.path.abspath(__file__))))
    roots = [os.path.abspath(r) for r in (args or
                                          [os.path.join(repo, 'src')])]

    files = []
    for root in roots:
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = sorted(d for d in dirnames
                                 if d not in SKIP_DIRS)
            for name in sorted(filenames):
                if not name.endswith('.py'):
                    continue
                path = os.path.join(dirpath, name)
                files.append(scan_file(path, os.path.relpath(path, repo)))

    totals = {
        'files_scanned': len(files),
        'parse_errors': sum(1 for f in files if f['parse_error']),
        'future_division_files':
            sum(1 for f in files if f['future_division']),
        'floordiv_sites': sum(f['floordiv'] for f in files),
        'div_sites': sum(len(f['sites']) for f in files),
    }
    for cat in ('int-int', 'float-literal', 'dynamic', 'regex-approx'):
        totals[cat] = sum(1 for f in files for s in f['sites']
                          if s['category'] == cat)

    outdir = os.path.dirname(os.path.abspath(options.out))
    if outdir and not os.path.isdir(outdir):
        os.makedirs(outdir)
    with open(options.out, 'w') as out:
        json.dump({'roots': roots, 'totals': totals, 'files': files},
                  out, indent=1, sort_keys=True)

    print 'scanned %d files under %s' % (totals['files_scanned'],
                                         ', '.join(roots))
    for key in ('div_sites', 'int-int', 'float-literal', 'dynamic',
                'regex-approx', 'floordiv_sites', 'parse_errors',
                'future_division_files'):
        print '  %-22s %d' % (key, totals[key])

    print ''
    print 'top files by dynamic `/` sites:'
    ranked = sorted(files,
                    key=lambda f: -sum(1 for s in f['sites']
                                       if s['category'] == 'dynamic'))
    for f in ranked:
        dyn = sum(1 for s in f['sites'] if s['category'] == 'dynamic')
        if not dyn:
            break
        print '  %-55s %3d dynamic / %3d total%s' % (
            f['path'], dyn, len(f['sites']),
            '   [future division]' if f['future_division'] else '')
    print ''
    print 'JSON written to %s' % options.out


if __name__ == '__main__':
    main()

