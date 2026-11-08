# Sketch - A Python-based interactive drawing program
# Copyright (C) 2026 by Vladimir Eltsov
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Library General Public
# License as published by the Free Software Foundation; either
# version 2 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Library General Public License for more details.
#
# You should have received a copy of the GNU Library General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA

# SVG import: CSS -- style attributes and <style> sheets.
#
# A small parser for what SVG files use: rules with simple and compound
# selectors (type, `*', `.class', `#id', `[attr]', `[attr=value]'),
# descendant and child combinators, selector lists, specificity and
# `!important'.  Rules with other selectors (pseudo-classes, sibling
# combinators) never match; at-rules are skipped, except that the
# @font-face rules are kept as text (see text.py).

import re

rx_comment = re.compile(r'/\*.*?\*/', re.S)

def strip_comments(text):
    return rx_comment.sub(' ', text)

def declarations(text):
    """Parse a declaration block.  Returns a list of (name, value,
    important) in source order; names are lowercased."""
    result = []
    for part in strip_comments(text or '').split(';'):
        if ':' not in part:
            continue
        name, value = part.split(':', 1)
        name = name.strip().lower()
        value = value.strip()
        important = False
        match = re.search(r'!\s*important\s*$', value, re.I)
        if match:
            value = value[:match.start()].strip()
            important = True
        if name and value:
            result.append((name, value, important))
    return result


rx_simple = re.compile(r'''
      (?P<type>\*|[-\w]+(?:\|[-\w]+)?)
    | \#(?P<id>[-\w]+)
    | \.(?P<class>[-\w]+)
    | \[\s*(?P<attr>[-\w:|]+)\s*(?:(?P<op>[~|^$*]?=)\s*
          (?P<value>"[^"]*"|'[^']*'|[^\]\s]+)\s*)?\]
    | (?P<other>:+[-\w]+(?:\([^)]*\))?)
''', re.X)

class Compound:

    """One compound selector: an optional type and a list of
    conditions."""

    def __init__(self, text):
        self.type = None
        self.conditions = []
        self.valid = True
        pos = 0
        text = text.strip()
        while pos < len(text):
            match = rx_simple.match(text, pos)
            if not match or match.end() == pos:
                self.valid = False
                return
            pos = match.end()
            if match.group('type'):
                type = match.group('type').split('|')[-1]
                if type != '*':
                    self.type = type
            elif match.group('id'):
                self.conditions.append(('id', match.group('id')))
            elif match.group('class'):
                self.conditions.append(('class', match.group('class')))
            elif match.group('attr'):
                value = match.group('value')
                if value and value[0] in '"\'':
                    value = value[1:-1]
                self.conditions.append(('attr', match.group('attr'),
                                        match.group('op'), value))
            else:
                # pseudo-classes and -elements are not supported
                self.valid = False

    def specificity(self):
        ids = len([c for c in self.conditions if c[0] == 'id'])
        others = len(self.conditions) - ids
        return (ids, others, self.type is not None and 1 or 0)

    def matches(self, node):
        if self.type is not None and node.tag != self.type:
            return False
        for cond in self.conditions:
            kind = cond[0]
            if kind == 'id':
                if node.get('id') != cond[1]:
                    return False
            elif kind == 'class':
                if cond[1] not in (node.get('class') or '').split():
                    return False
            else:
                actual = node.get(cond[1])
                op, value = cond[2], cond[3]
                if actual is None:
                    return False
                if op is None:
                    continue
                if op == '=' and actual != value:
                    return False
                if op == '~=' and value not in actual.split():
                    return False
                if op == '|=' and not (actual == value
                                        or actual.startswith(value + '-')):
                    return False
                if op == '^=' and not actual.startswith(value):
                    return False
                if op == '$=' and not actual.endswith(value):
                    return False
                if op == '*=' and value not in actual:
                    return False
        return True


class Selector:

    def __init__(self, text):
        # split into compounds and combinators
        tokens = re.split(r'\s*(>)\s*|\s+', text.strip())
        self.parts = []         # list of (combinator, Compound), right last
        combinator = None
        self.valid = True
        for token in tokens:
            if token is None or token == '':
                continue
            if token == '>':
                combinator = '>'
                continue
            if token in ('+', '~'):
                self.valid = False
                return
            compound = Compound(token)
            if not compound.valid:
                self.valid = False
                return
            self.parts.append((combinator or ' ', compound))
            combinator = None
        if not self.parts:
            self.valid = False
            return
        ids = others = types = 0
        for c, compound in self.parts:
            i, o, t = compound.specificity()
            ids += i; others += o; types += t
        self.specificity = (ids, others, types)

    def matches(self, node):
        return self._match(node, len(self.parts) - 1)

    def _match(self, node, index):
        combinator, compound = self.parts[index]
        if not compound.matches(node):
            return False
        if index == 0:
            return True
        parent = node.parent
        if self.parts[index][0] == '>':
            return parent is not None and self._match(parent, index - 1)
        while parent is not None:
            if self._match(parent, index - 1):
                return True
            parent = parent.parent
        return False


class StyleSheet:

    def __init__(self):
        self.rules = []         # (specificity, order, selector, decls)
        self.font_faces = []    # the text of the @font-face rules

    def add(self, text):
        text = strip_comments(text)
        pos = 0
        n = len(text)
        while pos < n:
            brace = text.find('{', pos)
            if brace < 0:
                break
            prelude = text[pos:brace].strip()
            # find the matching closing brace
            depth = 1
            i = brace + 1
            while i < n and depth:
                if text[i] == '{':
                    depth += 1
                elif text[i] == '}':
                    depth -= 1
                i += 1
            body = text[brace + 1:i - 1]
            pos = i
            if prelude.startswith('@'):
                # an at-rule ending in `;' before the block (@import,
                # @charset) is skipped up to that semicolon
                semi = prelude.find(';')
                while semi >= 0 and prelude.startswith('@'):
                    prelude = prelude[semi + 1:].strip()
                    semi = prelude.find(';')
                if prelude.startswith('@'):
                    if prelude.lower().startswith('@font-face'):
                        self.font_faces.append(body)
                    elif prelude.lower().startswith('@media'):
                        media = prelude[6:].strip().lower()
                        if not media or 'all' in media or 'screen' in media:
                            self.add(body)
                    continue
            decls = declarations(body)
            for part in prelude.split(','):
                selector = Selector(part)
                if selector.valid:
                    self.rules.append((selector.specificity,
                                       len(self.rules), selector, decls))

    def finish(self):
        self.rules.sort(key = lambda rule: rule[:2])

    def match(self, node):
        """The declarations of the matching rules, in cascade order
        (lowest priority first)."""
        result = []
        for specificity, order, selector, decls in self.rules:
            if selector.matches(node):
                result.extend(decls)
        return result
