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

# EPS, PostScript and PDF import filter.  The importer itself is the
# package Plugins/Filters/Lib/psimport (devdocs/ps-import.md).

###Sketch Config
#type = Import
#class_name = 'PSLoader'
#rx_magic = '(%!|%PDF-|\xc5\xd0\xd3\xc6)'
#tk_file_type = ('PostScript, EPS, PDF', ('.eps', '.ps', '.pdf', '.epsf', '.epsi'))
#format_name = 'PostScript/PDF'
#parameters = (('pages', 'text', '1', (20, 1), 'Pages'),)
#standard_messages = 1
#unload = 1
###End

(''"PostScript, EPS, PDF")
(''"Pages")

from Sketch.Plugins.Filters.Lib.psimport import PSLoader
