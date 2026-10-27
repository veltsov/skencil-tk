# Sketch - A Python-based interactive drawing program
# Copyright (C) 1998, 1999, 2000, 2002, 2003 by Bernhard Herzog
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
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307	USA

from __future__ import print_function
import os, sys, string

_pkgdir = __path__[0]
_parentdir = os.path.join(_pkgdir, '..')

SketchVersion = open(os.path.join(_pkgdir, 'VERSION')).read().strip()

# The C extension modules live in the real subpackage Sketch.Modules;
# no path manipulation is needed (import-restructure.md, batch B2).


message_dir = os.path.join(_parentdir, 'Resources/Messages')

# Localization is done with the standard gettext module; the former
# custom 'intl' C extension (a libintl binding from Pax) is no longer
# needed. Unlike C gettext, Python's gettext finds the .mo files
# without a generated libc locale, and the messages are returned as
# unicode (decoded using the charset of the .mo file), which stock
# _tkinter converts correctly.
import gettext as _gettext
import locale

try:
    locale.setlocale(locale.LC_ALL, "")
except locale.Error:
    # if we can't set the locale we might not be able to get
    # properly translated messages
    print("Can't set locale." \
          " Please check your LANG and LC_* environment variables")

_textdomains = {'skencil': message_dir}
_current_domain = ['skencil']
_translations = {}

def _get_translation(domain):
    translation = _translations.get(domain)
    if translation is None:
        try:
            translation = _gettext.translation(domain,
                                               _textdomains.get(domain))
        except (IOError, OSError):
            # no .mo file for this domain: fall back to the message ids
            translation = _gettext.NullTranslations()
        _translations[domain] = translation
    return translation

def bindtextdomain(domain, dirname=None):
    if dirname is not None:
        _textdomains[domain] = dirname
        _translations.pop(domain, None)	# a domain may be re-bound
    return _textdomains.get(domain)

def textdomain(domain=None):
    if domain is not None:
        _current_domain[0] = domain
    return _current_domain[0]

def gettext(text):
    return _get_translation(_current_domain[0]).gettext(text)

def dgettext(domain, text):
    return _get_translation(domain).gettext(text)

_ = gettext

from Sketch.UI import tkutils
ui_colors = tkutils.ColorScheme()

from Sketch.Modules import _sketch
from Sketch.Modules._sketch import Point, Polar, PointType
NullPoint = Point(0, 0)

from Sketch.Modules._sketch import Rect, PointsToRect, UnionRects, IntersectRects, \
     EmptyRect, InfinityRect, RectType
UnitRect = Rect(0, 0, 1, 1)


from Sketch.Modules._sketch import Trafo, Scale, Translation, Rotation, SingularMatrix, \
     TrafoType
Identity = Trafo(1, 0, 0, 1, 0, 0)
IdentityMatrix = Identity.matrix()


from Sketch.Modules._sketch import CreatePath, RectanglePath, RoundedRectanglePath, \
     approx_arc, CreateFontMetric, SKCache, TransformRectangle

from Sketch.Modules._sketch import ContAngle, ContSmooth, ContSymmetrical, \
     SelNone, SelNodes, SelSegmentFirst, SelSegmentLast, Bezier, Line

from Sketch.Base import config
config.init_directories(_parentdir)

from Sketch.Base.skexceptions import *

from Sketch.Base.undo import Undo, UndoList, CreateListUndo, CreateMultiUndo, UndoAfter, \
     UndoRedo, NullUndo

from Sketch.Base.connector import Connect, Disconnect, Issue, RemovePublisher, Subscribe, \
     Publisher, QueueingPublisher

#

# PIL is only supported as a package (true for every Pillow version
# that runs on this Python; the workarounds for pre-package PIL and
# PIL 1.0 were removed with the rest of the old compatibility code).
try:
    import PIL.Image
    import PIL.ImageChops
except ImportError:
    warn.warn(warn.USER, "Can't import the Python Imaging Library")
    sys.exit(1)



#

command_classes = []

def RegisterCommands(aclass):
    for cmd in aclass.commands:
        cmd.SetClass(aclass)
    command_classes.append(aclass)


# from Graphics.base import GraphicsObject, Primitive

from Sketch.Graphics.arrow import StandardArrows, Arrow
from Sketch.Graphics.properties import Style, FillStyle, EmptyFillStyle, \
     LineStyle, EmptyLineStyle, PropertyStack, EmptyProperties

from Sketch.Graphics.blend import MismatchError, Blend, BlendTrafo
from Sketch.Graphics.blendgroup import BlendGroup, CreateBlendGroup, \
     BlendInterpolation

from Sketch.Graphics.color import CreateRGBColor, XRGBColor, CreateCMYKColor, \
     StandardColors
from Sketch.Graphics.compound import Compound, EditableCompound
from Sketch.Graphics.dashes import StandardDashes

from Sketch.Graphics.document import EditDocument, SelectionMode, EditMode
Document = EditDocument

from Sketch.Graphics.font import GetFont
from Sketch.Graphics.gradient import MultiGradient, CreateSimpleGradient
from Sketch.Graphics.graphics import SimpleGC, GraphicsDevice, InvertingDevice, \
     HitTestDevice

from Sketch.Graphics.group import Group
from Sketch.Graphics.guide import GuideLine
from Sketch.Graphics.image import Image, load_image, ImageData
from Sketch.Graphics.layer import Layer, GuideLayer, GridLayer

from Sketch.Graphics.maskgroup import MaskGroup

from Sketch.Graphics.pattern import EmptyPattern, SolidPattern, HatchingPattern, \
     LinearGradient, RadialGradient, ConicalGradient, ImageTilePattern

from Sketch.Graphics.plugobj import PluginCompound, TrafoPlugin

from Sketch.Graphics.rectangle import Rectangle, RectangleCreator
from Sketch.Graphics.ellipse import Ellipse, EllipseCreator
from Sketch.Graphics.bezier import PolyBezier, PolyBezierCreator, PolyLineCreator, \
    CombineBeziers, CreatePath, ContAngle, ContSmooth, ContSymmetrical

from Sketch.Graphics.psdevice import PostScriptDevice


from Sketch.Graphics.text import SimpleText, SimpleTextCreator, PathText


def init_lib():
    from Sketch.Base import plugins, const
    config.load_user_preferences()
    Issue(None, const.INITIALIZE)

def init_ui():
    # paxtkinter (a copy of _tkinter from Python 1.5.2) used to be
    # substituted for _tkinter here; pax now works with the stock
    # _tkinter (GIL-safe callbacks; see devdocs/modernize-paxtkinter.md).
    # The runtime requires threaded Tcl; this is checked in
    # UI.skapp.TkApplication.init_tk as soon as an interpreter exists.

    init_lib()

    # import the standard scripts
    for name in config.preferences.standard_scripts:
        __import__(name)

def init_modules_from_widget(root):
    from Sketch import UI, Graphics
    from Sketch.Modules import pax
    import Sketch.UI.skpixmaps, Sketch.Graphics.graphics
    import Sketch.UI.tkext, Sketch.Graphics.color
    UI.tkext.InitFromTkapp(root.tk)
    if hasattr(root.tk, 'interpaddr'):
        tkwin = pax.name_to_window('.', root.tk.interpaddr())
    else:
        tkwin = pax.name_to_window('.', root.tk)
    Graphics.color.InitFromWidget(tkwin, root)
    Graphics.graphics.InitFromWidget(tkwin)
    UI.skpixmaps.InitFromWidget(tkwin)
