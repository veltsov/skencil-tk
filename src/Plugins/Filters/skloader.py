# Sketch - A Python-based interactive drawing program
# Copyright (C) 1997, 1998, 1999, 2000, 2003 by Bernhard Herzog
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
#type = Import
#class_name = 'SKLoader'
#rx_magic = '^##Sketch 1 *(?P<minor>[0-9]+)'
#tk_file_type = ('Skencil/Sketch Document', '.sk')
format_name = 'SK-1'
#standard_messages = 1
###End

(''"Skencil/Sketch Document")

import os, sys

from Sketch.warn import warn, INTERNAL, pdebug, warn_tb

from Sketch import load, const, plugins, SketchLoadError, SketchError
from Sketch import CreateRGBColor, SolidPattern, HatchingPattern,EmptyPattern,\
     LinearGradient, ConicalGradient, RadialGradient, ImageTilePattern, \
     Style, MultiGradient, Trafo, Translation, Point, \
     GridLayer, GuideLayer, GuideLine, Arrow, CreatePath, StandardColors, \
     GetFont

from Sketch.load import GenericLoader
from Sketch.Lib.util import decode_sk_string

from Sketch.Graphics import pagelayout, plugobj, blendgroup, text, image, eps,\
     properties

base_style = Style()
base_style.fill_pattern = EmptyPattern
base_style.fill_transform = 1
base_style.line_pattern = SolidPattern(StandardColors.black)
base_style.line_width = 0.0
base_style.line_join = const.JoinMiter
base_style.line_cap = const.CapButt
base_style.line_dashes = ()
base_style.line_arrow1 = None
base_style.line_arrow2 = None
base_style.font = None
base_style.font_size = 12.0

# sanity check: does base_style have all properties?
for key in dir(properties.factory_defaults):
    if not hasattr(base_style, key):
        warn(INTERNAL, 'added default for property %s', key)
        setattr(base_style, key,
                getattr(properties.factory_defaults, key))

papersizes = [#    'A0', 'A1', 'A2',
              u'A3', u'A4', u'A5', u'A6', u'A7',
              u'letter', u'legal', u'executive',
              ]


class SKLoader(GenericLoader):

    format_name = format_name

    base_style = base_style

    functions = ['document', 'layer', ('bezier', 'b'), ('rectangle', 'r'),
                 ('ellipse', 'e'),
                 'group', ('group', 'G'), 'endgroup', ('endgroup', 'G_'),
                 'guess_cont']

    def __init__(self, file, filename, match):
        GenericLoader.__init__(self, file, filename, match)
        if int(match.group('minor')) > 2:
            self.add_message(_("The file was created by a newer version of "
                               "Skencil or Sketch, there might be inaccuracies."))
        if self.filename:
            self.directory = os.path.split(filename)[0]
        else:
            self.directory = ''
        self.style_dict = {}
        self.id_dict = {}
        self.page_layout = None
        self.pattern = None
        self.gradient = None
        self.arrow1 = None
        self.arrow2 = None
        self.font = None
        self.font_size = 1.0
        self.color_cache = {}

    def __del__(self):
        pass

    def warn(self, level, *args, **kw):
        message = warn(*(level,) + args, **kw)
        self.add_message(message)

    def get_func_dict(self):
        func_dict = {}
        for name in self.functions:
            if isinstance(name, str):
                func_dict[name] = getattr(self, name)
            else:
                func_dict[name[1]] = getattr(self, name[0])
        return func_dict

    functions.append('layout')
    def layout(self, format, orientation):
        format = decode_sk_string(format)
        if isinstance(format, unicode):
            if format not in papersizes:
                # The format is given by name but it's not one of the
                # standard papersizes. The file may be corrupted.
                self.add_message(_("Unknown paper format '%s', "
                                   "using A4 instead") % format)
                format = u"A4"
            layout = pagelayout.PageLayout(format, orientation=orientation)
        else:
            w, h = format
            layout = pagelayout.PageLayout(width = w, height = h,
                                           orientation = orientation)
        self.page_layout = layout

    functions.append('grid')
    def grid(self, geometry, visible = 0, color = None, name = None):
        if name is None:
            name = _("Grid")
        else:
            name = decode_sk_string(name)
        self.begin_layer_class(GridLayer,
                               (geometry, visible, self.convert_color(color),
                                name))
        self.end_composite()

    def convert_color(self, color_spec):
        try:
            c = self.color_cache.get(color_spec)
            if c:
                return c
            c = CreateRGBColor(*color_spec)
            self.color_cache[color_spec] = c
        except:
            # This should only happen if the color_spec is invalid
            type, value = sys.exc_info()[:2]
            warn(INTERNAL, 'Color allocation failed: %s: %s', type, value)
            c = StandardColors.black
        return c

    functions.append('gl')
    def gl(self, colors):
        c = []
        for pos, color in colors:
            c.append((pos, self.convert_color(color)))
        self.gradient = MultiGradient(c)

    functions.append('pe')
    def pe(self):
        self.pattern = EmptyPattern

    functions.append('ps')
    def ps(self, color):
        self.pattern = SolidPattern(self.convert_color(color))

    functions.append('pgl')
    def pgl(self, dx, dy, border = 0):
        if not self.gradient:
            raise SketchLoadError(_("No gradient for gradient pattern"))
        self.pattern = LinearGradient(self.gradient, Point(dx, dy), border)

    functions.append('pgr')
    def pgr(self, dx, dy, border = 0):
        if not self.gradient:
            raise SketchLoadError(_("No gradient for gradient pattern"))
        self.pattern = RadialGradient(self.gradient, Point(dx, dy), border)

    functions.append('pgc')
    def pgc(self, cx, cy, dx, dy):
        if not self.gradient:
            raise SketchLoadError(_("No gradient for gradient pattern"))
        self.pattern = ConicalGradient(self.gradient,
                                       Point(cx, cy), Point(dx, dy))

    functions.append('phs')
    def phs(self, color, background, dx, dy, dist, width):
        self.pattern = HatchingPattern(self.convert_color(color),
                                       self.convert_color(background),
                                       Point(dx, dy), dist, width)

    functions.append('pit')
    def pit(self, id, trafo):
        trafo = Trafo(*trafo)
        self.pattern = ImageTilePattern(self.id_dict[id], trafo)

    functions.append('fp')
    def fp(self, color = None):
        if color is None:
            self.style.fill_pattern =  self.pattern
        else:
            self.style.fill_pattern = SolidPattern(self.convert_color(color))

    functions.append('fe')
    def fe(self):
        self.style.fill_pattern =  EmptyPattern

    functions.append('ft')
    def ft(self, bool):
        self.style.fill_transform =  bool

    functions.append('lp')
    def lp(self, color = None):
        if color is None:
            self.style.line_pattern = self.pattern
        else:
            self.style.line_pattern = SolidPattern(self.convert_color(color))

    functions.append('le')
    def le(self):
        self.style.line_pattern = EmptyPattern

    functions.append('lw')
    def lw(self, width):
        self.style.line_width = width

    functions.append('lj')
    def lj(self, join):
        self.style.line_join = join

    functions.append('lc')
    def lc(self, cap):
        if not 1 <= cap <= 3:
            self.add_message('line cap corrected from %d to 1' % cap)
            cap = 1
        self.style.line_cap = cap

    functions.append('ld')
    def ld(self, dashes):
        self.style.line_dashes = dashes

    functions.append('la1')
    def la1(self, args = None, head=None):
        #print head
        if args is not None:
            self.style.line_arrow1 = Arrow(*args)
        else:
            self.style.line_arrow1 = None

    functions.append('la2')
    def la2(self, args = None):
        if args is not None:
            self.style.line_arrow2 = Arrow(*args)
        else:
            self.style.line_arrow2 = None

    functions.append('dstyle')
    def dstyle(self, name = ''):
        name = decode_sk_string(name)
        if not name:
            raise SketchLoadError(_("unnamed style"))
        style = self.style.AsDynamicStyle()
        style.SetName(name)
        self.style_dict[name] = style
        self.style = Style()

    functions.append(('use_style', 'style'))
    def use_style(self, name = ''):
        name = decode_sk_string(name)
        if not name:
            raise SketchLoadError(_("unnamed style"))
        if not self.style.IsEmpty():
            self.prop_stack.load_AddStyle(self.style)
            self.style = Style()
        style = self.style_dict[name]
        self.prop_stack.load_AddStyle(style)

    functions.append('Fn')
    def Fn(self, name):
        self.style.font = GetFont(name)

    functions.append('Fs')
    def Fs(self, size):
        self.style.font_size = size

    functions.append('guide')
    def guide(self, pos, horizontal):
        if horizontal:
            p = Point(0, pos)
        else:
            p = Point(pos, 0)
        self.append_object(GuideLine(p, horizontal))

    functions.append('guidelayer')
    def guidelayer(self, *args, **kw):
        if args:
            args = (decode_sk_string(args[0]),) + args[1:]
        self.begin_layer_class(GuideLayer, args, kw)

    def bezier_load(self, line):
        bezier = self.object
        while 1:
            try:
                bezier.paths[-1].append_from_string(line)
                line = bezier.paths[-1].append_from_file(self.file)
            except:
                warn(INTERNAL, _("Error reading line %s"), repr(line))
                line = self.file.readline()
            if line[:2] == 'bC':
                bezier.paths[-1].load_close()
                line = self.file.readline()
            if line[:2] == 'bn':
                bezier.paths = bezier.paths + (CreatePath(),)
                line = self.file.readline()
            else:
                break
            if line[:2] not in ('bs', 'bc'):
                break
        return line

    functions.append('txt')
    def txt(self, thetext, trafo, halign = text.ALIGN_LEFT,
            valign = text.ALIGN_BASE):
        if len(trafo) == 2:
            trafo = Translation(trafo)
        else:
            trafo = Trafo(*trafo)
        object = text.SimpleText(text = thetext, trafo = trafo,
                                 halign = halign, valign = valign,
                                 properties = self.get_prop_stack())
        self.append_object(object)

    functions.append('im')
    def im(self, trafo, id):
        if len(trafo) == 2:
            trafo = Translation(trafo)
        else:
            trafo = Trafo(*trafo)
        self.append_object(image.Image(self.id_dict[id], trafo = trafo))

    functions.append('bm')
    def bm(self, id, filename = None):
        if filename is None:
            from streamfilter import Base64Decode, SubFileDecode
            decoder = Base64Decode(SubFileDecode(self.file, '-'))
            data = image.load_image(decoder)
        else:
            # file names are unicode in the model (K2; see
            # devdocs/string-handling.md)
            filename = decode_sk_string(filename)
            data = image.load_image(os.path.join(self.directory, filename))
        self.id_dict[id] = data

    functions.append('eps')
    def eps(self, trafo, filename):
        # file names are unicode in the model (K2; see
        # devdocs/string-handling.md)
        filename = decode_sk_string(filename)
        if len(trafo) == 2:
            trafo = Translation(trafo)
        else:
            trafo = Trafo(*trafo)
        if not os.path.isabs(filename):
            if self.directory:
                filename = os.path.join(self.directory, filename)
            else:
                filename = os.path.join(os.getcwd(), filename)
        self.append_object(eps.EpsImage(filename = filename, trafo = trafo))

    functions.append('B')
    def B(self, *args, **kw):
        self.begin_composite(blendgroup.BlendGroup, args, kw)

    functions.append('B_')
    def B_(self):
        self.end_composite()

    functions.append('Bi')
    def Bi(self, *args, **kw):
        self.begin_composite(blendgroup.BlendInterpolation, args, kw)
        self.end_composite()

    group = GenericLoader.begin_group
    endgroup = GenericLoader.end_group

    functions.append('M')
    def M(self, *args, **kw):
        from Sketch.Graphics import maskgroup
        self.begin_composite(maskgroup.MaskGroup, args, kw)

    functions.append('M_')
    def M_(self):
        self.end_composite()

    functions.append('PT')
    def PT(self, *args, **kw):
        self.begin_composite(text.PathText, args, kw)

    functions.append('pt')
    def pt(self, thetext, *args):
        matrix = ()
        model = text.PATHTEXT_ROTATE
        start_pos = 0.0
        if args:
            if isinstance(args[0], tuple):
                matrix = args[0]
                args = args[1:]
            if args:
                model = args[0]
                if len(args) > 1:
                    start_pos = args[1]

        if matrix:
            trafo = Trafo(*matrix)
        else:
            trafo = None

        self.append_object(text.InternalPathText(thetext, trafo = trafo,
                                                 model = model,
                                                 start_pos = start_pos,
                                                 properties = self.get_prop_stack()))

    functions.append('PT_')
    def PT_(self):
        self.end_composite()

    functions.append('PC')
    def PC(self, class_name, *args, **kw):
        # class names are internal ascii identifiers (K5); decode for
        # uniformity with the plugin registry keys
        class_name = decode_sk_string(class_name)
        kw['loading'] = 1
        info = plugins.find_object_plugin(class_name)
        if info is not None:
            try:
                theclass = info.Constructor()
                self.begin_composite(theclass, args, kw)
                return
            except SketchError:
                pass
        # constructing the plugin object failed. Use an UnknownPlugin
        # object.
        self.add_message(_("Unknown Plugin: %s") % class_name)
        self.begin_composite(plugobj.UnknownPlugin, (class_name,) + args, kw)

    functions.append('PC_')
    def PC_(self):
        self.end_composite()

    #
    #	The loader driver
    #

    def Load(self):
        file = self.file
        if isinstance(file, (str, unicode)):
            file = open(file, 'r')
        dict = self.get_func_dict()
        from Sketch import skread
        parse = skread.parse_sk_line2
        readline = file.readline
        bezier_load = self.bezier_load
        num = 1
        line = '#'
        if __debug__:
            import time
            start_time = time.clock()
        try:
            line = readline()
            while line:
                num = num + 1
                if line[0] == 'b' and line[1] in 'sc':
                    line = bezier_load(line)
                    continue
                #parse(line, dict)
                funcname, args, kwargs = parse(line)
                if funcname is not None:
                    function = dict.get(funcname)
                    if function is not None:
                        try:
                            function(*args, **kwargs)
                        except TypeError:
                            tb = sys.exc_info()[2]
                            try:
                                if tb.tb_next is None:
                                    # the exception was raised by apply
                                    # and not within the function. Try to
                                    # invoke the function with fewer
                                    # arguments
                                    if call_function(function, args, kwargs):
                                        message = _("Omitted some arguments "
                                                    "for function %s")
                                    else:
                                        message = _("Cannot call function %s")
                                    self.add_message(message
                                                     % function.__name__)

                                else:
                                    raise
                            finally:
                                del tb
                    else:
                        self.add_message(_("Unknown function %s") % funcname)

                line = readline()

        except (SketchLoadError, SyntaxError) as value:
            # a loader specific error occurred
            warn_tb(INTERNAL, 'error in line %d', num)
            if load._dont_handle_exceptions:
                raise
            else:
                raise SketchLoadError('%d:%s' % (num, value))
        except:
            # An exception was not converted to a SketchLoadError.
            # This should be considered a bug.
            warn_tb(INTERNAL, 'error in line %d:\n%s', num, repr(line))
            if load._dont_handle_exceptions:
                raise
            else:
                raise SketchLoadError(_("error %s:%s in line %d:\n%s")
                                      % (sys.exc_info()[:2] +(num, repr(line))))

        self.end_all()
        if self.page_layout:
            self.object.load_SetLayout(self.page_layout)
        for style in self.style_dict.values():
            self.object.load_AddStyle(style)
        self.object.load_Completed()

        self.object.meta.native_format = 1

        if __debug__:
            pdebug('timing', 'time:', time.clock() - start_time)
        return self.object


def call_function(function, args, kwargs):
    if hasattr(function, '__func__'):
        args = (function.__self__,) + args
        function = function.__func__
    code = function.__code__
    if code.co_flags & 0x000C:
        # uses *args or **kwargs
        return 0
    args = args[:code.co_argcount]
    argnames = code.co_varnames[:code.co_argcount]
    for key in kwargs.keys():
        if key not in argnames:
            del kwargs[key]
    try:
        function(*args, **kwargs)
    except:
        warn_tb(INTERNAL, 'Trying to call function %s with reduced arglist',
                function.__name__)
        return 0
    return 1
