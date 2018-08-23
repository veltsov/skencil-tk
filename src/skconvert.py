#!/usr/bin/python

# Sketch - A Python-based interactive drawing program
# Copyright (C) 2002, 2003 by Bernhard Herzog
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

"""Usage: skconvert infile outfile

Convert a vector graphics file into another format. This is done by
reading infile into Skencil and saving it as outfile. infile can be in
any format Skencil can read. The format of the output file is determined
by its extension.
"""

import sys, os

from Sketch import load, plugins
import Sketch


def convert(infile, outfile):
    doc = load.load_drawing(infile)
    extension = os.path.splitext(outfile)[1]
    fileformat = plugins.guess_export_plugin(extension)
    if fileformat:
        saver = plugins.find_export_plugin(fileformat)
        saver(doc, outfile)
    else:
        sys.stderr.write("skconvert: unrecognized extension %s\n" % extension)
        sys.exit(1)


def main():
    Sketch.init_lib()
    if len(sys.argv) != 3:
        sys.stderr.write(__doc__)
        sys.exit(1)

    convert(sys.argv[1], sys.argv[2])


main()

