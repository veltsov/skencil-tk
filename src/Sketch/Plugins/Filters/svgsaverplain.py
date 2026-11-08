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

# Plain SVG export: the printable layers, visually identical to the
# PostScript output, without any editing structure (text as paths, no
# Inkscape or Skencil specific attributes, no hidden objects).  The
# saver is shared with the Inkscape SVG export (svgsaver.py).

###Sketch Config
#type = Export
#tk_file_type = ("Plain SVG", '.svg')
#extensions = '.svg'
format_name = 'SVG'
#parameters = (\
#    ('box','choice',0,('Page','Bounding box'),'Export area'), \
#    ('eps','choice',0,('Vector','Image'),'EPS files'), \
#    ('eps_dpi','int',300,(30,2400),'EPS image resolution'))
#unload = 1
###End

from Sketch.Plugins.Filters.svgsaver import save_svg

def save(document, file, filename, options = {}):
    save_svg(document, file, filename, options, 0)
