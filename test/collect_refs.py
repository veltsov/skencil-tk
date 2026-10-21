#!/usr/bin/python
# Collect the external files referenced by a Skencil save file (.sk).
#
# The .sk format references external files in two directives:
#
#   eps(trafo, 'filename')        -- embedded EPS object
#   bm(id, 'filename')            -- bitmap image (base64 inline if the
#                                    filename argument is missing)
#
# Usage: collect_refs.py FILE.sk [more.sk ...]
#        prints one referenced filename per line (relative to the .sk
#        file's directory), or with --copy DEST copies them.

from __future__ import print_function

import os
import re
import shutil
import sys

# a quoted python string literal (single or double quotes, backslash
# escapes); filenames in .sk files are written with repr()
_quoted = re.compile(r"'((?:[^'\\]|\\.)*)'|\"((?:[^\"\\]|\\.)*)\"")
_directives = ('eps', 'bm')


def unescape(s):
    return s.replace('\\%', '%').replace("\\'", "'").replace('\\"', '"')


def collect_refs(path):
    """Return the list of external filenames referenced by the .sk file
    PATH, relative to the file's directory."""
    refs = []
    with open(path) as f:
        for line in f:
            stripped = line.lstrip()
            if not any(stripped.startswith(d + '(') for d in _directives):
                continue
            quotes = _quoted.findall(line)
            if not quotes:
                continue  # e.g. bm(id) with inline base64 data
            # the filename is the last string literal on the line
            last = quotes[-1]
            filename = unescape(last[0] or last[1])
            if filename:
                refs.append(filename)
    return refs


def copy_with_refs(sk_file, dest_dir):
    """Copy the .sk file SK_FILE into DEST_DIR along with every external
    file it references.  Symlinks are resolved.  Returns the list of
    names copied."""
    sk_file = os.path.abspath(sk_file)
    src_dir = os.path.dirname(sk_file)
    dest_dir = os.path.abspath(dest_dir)
    copied = []
    target = os.path.join(dest_dir, os.path.basename(sk_file))
    shutil.copyfile(sk_file, target)
    copied.append(os.path.basename(sk_file))
    for ref in collect_refs(sk_file):
        src = os.path.normpath(os.path.join(src_dir, ref))
        dest = os.path.normpath(os.path.join(dest_dir, ref))
        if not os.path.exists(src):
            print('WARNING: %s references missing file %s' % (sk_file, ref),
                  file=sys.stderr)
            continue
        if os.path.realpath(src) == os.path.realpath(dest):
            continue
        dest_parent = os.path.dirname(dest)
        if not os.path.isdir(dest_parent):
            os.makedirs(dest_parent)
        shutil.copyfile(os.path.realpath(src), dest)
        copied.append(ref)
    return copied


def main():
    if len(sys.argv) < 2:
        print('usage: collect_refs.py [--copy DEST] FILE.sk ...',
              file=sys.stderr)
        return 2
    args = sys.argv[1:]
    copy_dest = None
    if args[0] == '--copy':
        copy_dest = args[1]
        args = args[2:]
    for path in args:
        refs = collect_refs(path)
        if copy_dest:
            copied = copy_with_refs(path, copy_dest)
            print('%s: %s' % (path, ', '.join(copied) or 'no refs'))
        else:
            for ref in refs:
                print(ref)
    return 0


if __name__ == '__main__':
    sys.exit(main())
