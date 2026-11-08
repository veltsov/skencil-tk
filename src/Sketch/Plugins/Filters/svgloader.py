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

# SVG import filter.  The importer itself is the package
# Plugins/Filters/Lib/svgimport (devdocs/svg-import.md).

###Sketch Config
#type = Import
#class_name = 'SVGLoader'
#rx_magic = '(\xef\xbb\xbf)?\\s*<(\\?xml|svg|!--|!DOCTYPE\\s+svg)'
#tk_file_type = ('Scalable Vector Graphics (SVG)', ('.svg', '.svgz'))
format_name = 'SVG'
#unload = 1
###End

from Sketch.Plugins.Filters.Lib.svgimport import SVGLoader
