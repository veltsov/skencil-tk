# Sketch - A Python-based interactive drawing program
# Copyright (C) 2002 by Bernhard Herzog
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

###Sketch Config
#type = Export
#tk_file_type = ("Portable Document Format (PDF) - full page", '.pdf')
#extensions = '.pdf'
format_name = 'PDF-full'
#unload = 1
#preopen_output = 0
###End

__version__ = "$Revision: 251 $"
# $Source$
# $Id: epssaver.py 251 2002-11-02 19:04:18Z bherzog $

import os
from Sketch import PostScriptDevice, config
from Sketch.Lib import util

gs_command =  'gs -q -dNOPAUSE -dBATCH -sDEVICE=pdfwrite -dCompatibilityLevel=%(compat)s' \
	' -r%(resolution)d -g%(width)dx%(height)d -sOutputFile=%(filename)s' \
	' -f -'

def save(document, file, filename, options = {}):
    bbox = tuple(document.PageRect())
    llx, lly, urx, ury = bbox
    resolution = config.preferences.pdf_export_resolution
    compat = config.preferences.pdf_compatibility_level
    width = (urx-llx)*resolution/72
    height = (ury-lly)*resolution/72

    filename = util.sh_quote(filename)
    file = os.popen(gs_command % locals(),'w')
    ps = PostScriptDevice(file, document = document, as_eps = 0, embed_fonts = 1,
                          bounding_box = bbox,
                          Title = os.path.basename(filename),
                          For = util.get_real_username(),
                          CreationDate = util.current_date())
    document.Draw(ps)
    ps.Close()
    file.close()
