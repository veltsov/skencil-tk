# Sketch - A Python-based interactive drawing program
# Copyright (C) 1998, 1999, 2000, 2002 by Bernhard Herzog
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

#
#	A GraphicsObject for Encapsulated Postscript Pictures
#

import os, math

import PIL.Image

from Sketch.Lib import dscparser, util
from Sketch.Graphics.image import RasterImage, image_from_pil
IsEpsFileStart = dscparser.IsEpsFileStart
from Sketch import _, Point, NullUndo, SketchError, RegisterCommands
from Sketch.Base import config
from Sketch.Base.warn import warn, USER
from Sketch.UI.command import AddCmd

from Sketch.Graphics.base import GraphicsObject
from Sketch.Graphics.external import ExternalData, MissingData, get_cached, \
     ExternalGraphics


def render_preview(filename, startx, starty, width, height, resolution = None):
    import tempfile
    temp = tempfile.mktemp()

    try:
        if resolution is None:
            resolution = config.preferences.eps_preview_resolution
        factor = resolution / 72.0
        width = int(math.ceil(width * factor))
        height = int(math.ceil(height * factor))
        offx = -startx
        offy = -starty
        # render the preview without showing the page (the showpage
        # operator is redefined to do nothing); no shell involved, so
        # the file name needs no quoting (util.run_gs)
        util.run_gs(['-sDEVICE=ppmraw', '-r%d' % resolution,
                     '-dNOPAUSE', '-dSAFER', '-q',
                     '-sOutputFile=' + temp,
                     '-g%dx%d' % (width, height),
                     '-c', '%f' % offx, '%f' % offy, 'translate',
                     '/oldshowpage /showpage load def', '/showpage {} def',
                     '-f', filename, '-c', 'oldshowpage quit'])

        image = PIL.Image.open(temp)
        image.load()
        return RasterImage(*image_from_pil(image))
    finally:
        try:
            os.unlink(temp)
        except:
            pass



class EpsData(ExternalData):

    def __init__(self, filename):
        self.info = info = dscparser.parse_eps_file(filename)
        self.filename = filename
        if info.BoundingBox:
            llx, lly, urx, ury = info.BoundingBox
            self.width = Point(urx - llx, 0)
            self.height = Point(0, ury - lly)
            self.start = (llx, lly)
            self.size = (urx - llx, ury - lly)
            self.image = None
            try:
                self.image = render_preview(filename, llx, lly,
                                            urx - llx, ury - lly)
            except IOError:
                pass
        else:
            raise TypeError('%s has no BoundingBox' % filename)

        ExternalData.__init__(self, filename)

    def Start(self):
        return self.start

    def Size(self):
        return self.size

    def WriteLines(self, file):
        write = file.write

        try:
            infile = open(self.filename, 'rb')
        except IOError as val:
            raise IOError(filename, val)
        try:
            readline = infile.readline

            line = readline()
            while line:
                if line[:15] == '%%BeginPreview:':
                    while line[:12] != '%%EndPreview':
                        line = readline()
                    continue
                write(line)
                line = readline()
        finally:
            infile.close()

    def new_from_file(self):
        return load_eps(self.filename)

class _NoDSCInfo:
    DocumentNeededResources = []

class MissingEpsData(MissingData):

    info = _NoDSCInfo()
    image = None

    def Start(self):
        return (0, 0)

    def new_from_file(self):
        return load_eps(self.filename)

def load_eps(filename):
    eps = get_cached(filename)
    if isinstance(eps, EpsData):
        return eps
    return EpsData(filename)

def import_eps_objects(data):
    # Import the EPS file of DATA as vector objects with the PS import
    # filter. Return (group, messages); the group's coordinates are
    # those of an EpsImage with identity transformation (the lower left
    # corner of the BoundingBox at the origin).
    from Sketch.Plugins.Filters.Lib import psimport
    group, messages = psimport.import_ps_group(data.Filename())
    if group is None:
        raise SketchError(_("%s contains no objects")
                          % util.as_display_name(data.Filename()))
    return group, messages

def load_eps_or_missing(filename):
    # Return the data of the linked EPS file FILENAME, or a placeholder
    # MissingEpsData if the file does not exist. Other errors (e.g. no
    # BoundingBox) are raised.
    try:
        return load_eps(filename)
    except FileNotFoundError:
        data = get_cached(filename)
        if not isinstance(data, MissingEpsData):
            data = MissingEpsData(filename)
        return data


class EpsImage(ExternalGraphics):

    has_edit_mode = 0
    is_Eps = 1

    def __init__(self, filename = '', trafo = None, duplicate = None,
                 data = None):
        if duplicate is None:
            if data is None:
                if not filename:
                    raise ValueError('filename must be provided')
                data = load_eps(filename)
        else:
            data = None
        ExternalGraphics.__init__(self, data, trafo,
                                  duplicate = duplicate)

    commands = ExternalGraphics.commands[:]

    def DrawShape(self, device, rect = None):
        if self.data.IsMissing():
            device.DrawMissingLink(self.data, self.trafo)
        else:
            device.DrawEps(self.data, self.trafo)

    def Info(self):
        filename = os.path.basename(self.data.Filename())
        width, height = self.data.Size()
        x, y = self.trafo.offset()
        if self.data.IsMissing():
            return _("Missing EpsFile `%(filename)s' "
                     "at (%(x)d, %(y)d)") % locals()
        return _("EpsFile `%(filename)s' %(width)d x %(height)d "
                 "at (%(x)d, %(y)d)") % locals()

    def SaveToFile(self, file):
        file.EpsFile(self.data, self.trafo)

    def PSNeededResources(self):
        return self.data.info.DocumentNeededResources

    def EmbeddedCopy(self, template):
        # Return the objects of TEMPLATE (see import_eps_objects) placed
        # like self, clipped to the BoundingBox if they extend beyond it
        # (like the EPS when printed).
        from Sketch import Rectangle, MaskGroup, Rect, Trafo
        from Sketch.Plugins.Filters.Lib.svgimport.clip import \
             empty_properties
        width, height = self.data.Size()
        group = template.Duplicate()
        group.Transform(self.trafo)
        if not Rect(-0.5, -0.5, width + 0.5, height + 0.5) \
               .contains_rect(template.coord_rect):
            mask = Rectangle(self.trafo(Trafo(width, 0, 0, height, 0, 0)),
                             properties = empty_properties())
            group = MaskGroup([mask, group])
        return group

    def Embed(self):
        # replaces self in the document by the imported vector objects;
        # the undo information is recorded by the document's transaction
        try:
            self.document.EmbedObjects([self])
        except SketchError as value:
            warn(USER, _("Cannot embed %(filename)s:\n%(message)s")
                 % {'filename': self.data.Filename(), 'message': value})
        return NullUndo
    AddCmd(commands, 'EmbedEps', _("Embed EPS"), Embed,
           sensitive_cb = 'IsLinkedAndPresent')

    # ReplaceEps is a command of the main window (it asks for a file)
    context_commands = ('ReplaceEps', 'EmbedEps')

RegisterCommands(EpsImage)



