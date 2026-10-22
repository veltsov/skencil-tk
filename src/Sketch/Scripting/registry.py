# Sketch - A Python-based interactive drawing program
# Copyright (C) 1998, 1999 by Bernhard Herzog
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Library General Public
# License as published by the Free Software Foundation; either
# version 2 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.	See the GNU
# Library General Public License for more details.
#
# You should have received a copy of the GNU Library General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA 02111-1307
# USA

import operator

from Sketch.warn import warn, USER

from script import SafeScript


class ScriptRegistry:

    def __init__(self):
        self.registry = {}
        self.menu = {}

    def Add(self, script, menu = ()):
        if isinstance(menu, unicode):
            menu = (menu,)
        self.registry[script.name] = script
        submenu = self.menu
        for item in menu:
            if item in submenu:
                if not isinstance(submenu[item], dict):
                    warn(USER, 'Replacing menu entry "%s" with a submenu',
                         item)
                    submenu[item] = {}
            else:
                submenu[item] = {}
            submenu = submenu[item]
        submenu[script.Title()] = script

    def AddFunction(self, name, title, function, args = (), menu = (),
                    sensitive = None, script_type = SafeScript):
        self.Add(script_type(name, title, function, args = args,
                             sensitive = sensitive),
                 menu = menu)

    def MenuTree(self):
        return make_menu_tree(self.menu)


def make_menu_tree(menu):
    result = []
    for key, value in menu.items():
        if isinstance(value, dict):
            value = make_menu_tree(value)
        result.append((key, value))
    result.sort()
    return result
