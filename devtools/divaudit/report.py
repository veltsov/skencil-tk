#!/usr/bin/env python2
# Merge the static division-site inventory (scan_division.py) and the
# runtime warning log collected by python2-divaudit + hook/sitecustomize
# into a prioritized hot-site table.
#
# Runtime paths are reported against the build tree
# (build/lib.linux-x86_64-2.7/...); they are mapped back to src/ paths
# so they can be joined with the static classification.  Runtime
# entries outside the source tree (pytest, site-packages, test/ code)
# are skipped.
#
# Usage: devtools/divaudit/report.py [-s static.json] [-r log.jsonl]...
# Defaults: -s /tmp/divaudit/static.json
#           -r /tmp/divaudit/warnings.jsonl

import json
import optparse
import os

BUILD_MARKERS = ('build/lib.linux-x86_64-2.7/',)


def to_relpath(path, repo):
    """Map a runtime path back to a src/-relative path, or None."""
    path = os.path.normpath(path)
    for marker in BUILD_MARKERS:
        idx = path.find(marker)
        if idx >= 0:
            return os.path.join('src', path[idx + len(marker):])
    rel = os.path.relpath(path, repo)
    if rel.startswith('..'):
        return None
    return rel


def main():
    parser = optparse.OptionParser()
    parser.add_option('-s', '--static', dest='static',
                      default='/tmp/divaudit/static.json')
    parser.add_option('-r', '--runtime', dest='runtime',
                      action='append',
                      default=['/tmp/divaudit/warnings.jsonl'])
    options, args = parser.parse_args()

    repo = os.path.dirname(os.path.dirname(
        os.path.dirname(os.path.abspath(__file__))))

    static = json.load(open(options.static, 'r'))
    sites = {}
    for f in static['files']:
        for s in f['sites']:
            sites[(f['path'], s['line'])] = s

    runtime = {}   # (relpath, line) -> [count, message]
    skipped = 0
    for log in options.runtime:
        if not os.path.isfile(log):
            continue
        for ln in open(log, 'r'):
            ln = ln.strip()
            if not ln:
                continue
            entry = json.loads(ln)
            rel = to_relpath(entry['file'], repo)
            if rel is None or not rel.startswith('src'):
                skipped += 1
                continue
            key = (rel, entry['line'])
            if key not in runtime:
                runtime[key] = [0, entry['message']]
            runtime[key][0] += entry['count']

    for kind in ('classic int division', 'classic float division'):
        hits = [(k, v) for k, v in runtime.items() if v[1] == kind]
        print '== %s: %d distinct sites, %d hits' % (
            kind, len(hits), sum(v[0] for _, v in hits))
        if kind.endswith('int division'):
            print '   (int/int: changes value AND type under py3)'
        else:
            print '   (int/float: already true division; same under py3)'
        print '   %-42s %6s  %-13s %s' % ('site', 'hits', 'static class',
                                          'source')
        for (rel, line), (count, _) in sorted(hits, key=lambda kv: -kv[1][0]):
            site = sites.get((rel, line), {})
            print '   %-42s %6d  %-13s %s' % (
                '%s:%d' % (rel.replace('src/', '', 1), line), count,
                site.get('category', '?'),
                (site.get('source') or '')[:60])
        print ''

    if skipped:
        print '(%d runtime entries outside the source tree skipped)' \
            % skipped
    print 'runtime coverage: %d of %d static dynamic sites hit' % (
        len(runtime),
        sum(1 for s in sites.values() if s['category'] == 'dynamic'))


if __name__ == '__main__':
    main()
