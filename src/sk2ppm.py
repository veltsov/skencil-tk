#!/usr/bin/python
# Sketch - A Python-based interactive drawing program
# Copyright (C) 1998, 1999, 2001, 2002, 2003 by Bernhard Herzog
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

# Convert a Sketch-file into a PPM file

"""usage: sk2ppm [Options] infile [outfile]

Convert the Skencil/Sketch SK-file infile into a PPM file. Output is
written to outfile or to stdout.

sk2ppm accepts these options:

  -h --help              Print this help message and exit
  -b --bbox              Use the document's bounding box to determine the
                         size of the raster image
  -r --resolution=N      Resolution of the raster image in pixels per inch
                         Default: 72
  -s --gradient-steps=N  Number of interpolated colors used in a gradient
  -A --alpha-bits=N      Alpha bits for anti-aliasing (1, 2, or 4)

"""

import sys, os

for dir in ('Lib', 'Filter', 'Pax'):
    dir = os.path.join(sys.path[0], dir)
    if os.path.isdir(dir):
        sys.path.insert(1, dir)

from Sketch import load
from Script.export_raster import export_raster


def print_usage():
    print __doc__

class Context:
    pass

def main():
    import Sketch, Sketch.config
    Sketch.Issue(None, Sketch.const.INITIALIZE)
    #plugins.load_plugin_configuration(config.plugin_path)

    use_bbox = 0
    resolution = 72.0
    steps = alpha = None

    import getopt
    opts, args = getopt.getopt(sys.argv[1:], 'bhr:s:A:',
                               ['help', 'bbox', 'resolution=',
                                'gradient-steps=', 'alpha-bits='])

    for optchar, value in opts:
        if optchar == '-h' or optchar == '--help':
            print_usage()
            return -1
        elif optchar == '-b' or optchar == '--bbox':
            use_bbox = 1
        elif optchar == '-r' or optchar == '--resolution':
            resolution = float(value)
        elif optchar == '-s' or optchar == '--gradient-steps':
            steps = float(value)
        elif optchar == '-A' or optchar == '--alpha-bits':
            alpha = int(value)
            if alpha not in (1, 2, 4):
                sys.stderr.write("sk2ppm: alpha-bits value must be one of"
                                 " 1, 2 or 4\n")
                return -1

    if len(args) not in (1, 2):
        print_usage()
        return -1

    if steps is not None:
        Sketch.config.preferences.gradient_steps_print = steps

    filename = args[0]
    if len(args) > 1:
        ppmfile = args[1]
    else:
        ppmfile = sys.stdout

    doc = load.load_drawing(filename)

    context = Context()
    context.document = doc

    export_raster(context, ppmfile, resolution, use_bbox, format = "ppm",
                  antialias = alpha)

if __name__ == '__main__':
    result = main()

    if result:
        sys.exit(result)
