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

#
# Extract Image / Replace Image: save the (unclipped) raster image of the
# selection to a file, or replace it by another file. The selection is an
# image, an object with an image fill, or a group (also a mask group)
# containing exactly one of them somewhere in its hierarchy. Embedded and
# linked images are handled alike.
#

import os
import shutil

import PIL.Image

import Sketch.Scripting
from Sketch import _, SketchError
from Sketch.Graphics.compound import EditableCompound
from Sketch.Lib import util


def image_fill(obj):
    # the image tile fill pattern of OBJ or None
    if obj.has_properties:
        pattern = getattr(obj.Properties(), 'fill_pattern', None)
        if pattern is not None and pattern.is_Tiled and pattern.is_Image:
            return pattern
    return None

def find_images(obj):
    # The images reachable from OBJ as a list of (user, owner): an Image
    # object is its own user (owner None), an image fill pattern is used
    # by the object OWNER. Groups and mask groups are searched
    # recursively.
    if obj.is_Image:
        return [(obj, None)]
    if isinstance(obj, EditableCompound):
        result = []
        for child in obj.GetObjects():
            result.extend(find_images(child))
        return result
    pattern = image_fill(obj)
    if pattern is not None:
        return [(pattern, obj)]
    return []

def target_image(doc):
    # The (user, owner) pair of the image the scripts operate on, None if
    # the selection is not a single object with exactly one image.
    obj = doc.CurrentObject()
    if obj is None:
        return None
    images = find_images(obj)
    if len(images) == 1:
        return images[0]
    return None

def report_no_image(context, title):
    context.application.MessageBox(
        title = title,
        message = _("Select an image, an object with an image fill, or a "
                    "group containing exactly one image."))


#
#   Extract Image
#

def save_formats():
    # {format: [extensions]} of the formats PIL can write
    PIL.Image.init()
    formats = {}
    for ext, format in PIL.Image.registered_extensions().items():
        if format in PIL.Image.SAVE:
            formats.setdefault(format, []).append(ext)
    return formats

def save_filetypes():
    # the Tk filetypes of the formats PIL can write: PNG first
    formats = save_formats()
    names = sorted(formats, key = lambda name: (name != 'PNG', name))
    return tuple((name, tuple(sorted(formats[name]))) for name in names) \
           + ((_("All Files"), '*'),)

def format_of_filename(filename):
    # the PIL format to write FILENAME in, from its extension, or None
    PIL.Image.init()
    return PIL.Image.registered_extensions().get(
        os.path.splitext(filename)[1].lower())

def extract_image(data, filename):
    # Write the full image of the image data DATA to FILENAME in the
    # format given by its extension. A linked file of the same format is
    # copied unchanged. Raise SketchError on failure.
    if data.IsMissing():
        raise SketchError(_("The linked file %s is missing.")
                          % util.as_display_name(data.Filename()))
    format = format_of_filename(filename)
    if format is None or format not in PIL.Image.SAVE:
        raise SketchError(_("Unknown image format of %s")
                          % util.as_display_name(filename))
    try:
        if data.IsLinked():
            source = data.Filename()
            with PIL.Image.open(source) as image:
                source_format = image.format
            if source_format == format:
                if os.path.abspath(source) != os.path.abspath(filename):
                    shutil.copyfile(source, filename)
                return
        image = data.Image()
        try:
            image.save(filename, format)
        except (OSError, KeyError, ValueError):
            # the format cannot store the mode (e.g. RGBA as JPEG)
            image.convert('RGB' if image.mode != 'L' else 'L') \
                 .save(filename, format)
    except SketchError:
        raise
    except Exception as value:
        raise SketchError(str(value))

def extract_image_interactive(context):
    title = _("Extract Image")
    target = target_image(context.document)
    if target is None:
        report_no_image(context, title)
        return
    data = target[0].Data()
    doc = context.document
    if data.IsLinked():
        directory, initialfile = os.path.split(data.Filename())
    else:
        directory = ''
        initialfile = os.path.splitext(doc.meta.filename)[0] + '-image.png'
    if not directory or not os.path.isdir(directory):
        directory = doc.meta.directory or os.getcwd()
    filename = context.application.GetSaveFilename(
        title = title, filetypes = save_filetypes(),
        initialdir = directory, initialfile = initialfile)
    if not filename:
        return
    try:
        extract_image(data, filename)
    except SketchError as value:
        context.application.MessageBox(
            title = title,
            message = _("Cannot write %(filename)s:\n%(message)s")
            % {'filename': util.as_display_name(filename), 'message': value})


#
#   Replace Image
#

def relink_arguments(target):
    # the arguments of RelinkObjects (without the filename) replacing the
    # image data of TARGET (a (user, owner) pair from target_image),
    # keeping it embedded or linked
    user, owner = target
    kw = {'embed': user.Data().IsEmbedded()}
    if owner is None:
        return [user], kw
    kw['patterns'] = [user]
    kw['owners'] = [owner]
    return [], kw

def replace_image(doc, target, filename):
    # Replace the image data of TARGET by the image of FILENAME. Only the
    # data changes, so the objects stay in place. Undoable. Raise
    # SketchError if FILENAME cannot be loaded.
    objects, kw = relink_arguments(target)
    doc.RelinkObjects(objects, filename, **kw)

def replace_image_interactive(context):
    from Sketch.UI import linksdlg
    target = target_image(context.document)
    if target is None:
        report_no_image(context, _("Replace Image"))
        return
    filename = linksdlg.ask_link_filename(context.main_window,
                                          target[0].Data().Filename(), 0)
    if filename:
        objects, kw = relink_arguments(target)
        linksdlg.relink_objects(context.main_window, objects, filename, **kw)


Sketch.Scripting.AddFunction('extract_image', _("Extract Image..."),
                             extract_image_interactive,
                             script_type = Sketch.Scripting.AdvancedScript)
Sketch.Scripting.AddFunction('replace_image', _("Replace Image..."),
                             replace_image_interactive,
                             script_type = Sketch.Scripting.AdvancedScript)
