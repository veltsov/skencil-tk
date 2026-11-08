# Builds svgall.sk, the feature fixture of the SVG export tests
# (test_svg.py), with the files it refers to.  The fixture data under
# test/data is not tracked, so the drawing is generated: one object of
# every kind the SVG export maps (see devdocs/svg-export.md).

import os

import testsupport


EPS = b'''%!PS-Adobe-3.0 EPSF-3.0
%%BoundingBox: 10 20 210 140
%%EndComments
0.9 0.95 1 setrgbcolor 10 20 200 120 rectfill
0 0 0.6 setrgbcolor 3 setlinewidth
20 30 moveto 60 130 lineto 120 40 lineto 200 120 lineto stroke
1 0 0 setrgbcolor 150 80 25 0 360 arc fill
/Helvetica findfont 18 scalefont setfont 0 setgray
30 110 moveto (EPS) show
showpage
%%EOF
'''


def write_images(dirname):
    from PIL import Image
    im = Image.new('RGBA', (64, 48))
    for x in range(64):
        for y in range(48):
            im.putpixel((x, y), (x * 4, y * 5, 200, min(255, x * 4 + 20)))
    im.save(os.path.join(dirname, 'svgalpha.png'))
    im = Image.new('RGB', (8, 8), (255, 255, 255))
    for x in range(8):
        for y in range(8):
            if (x // 4 + y // 4) % 2:
                im.putpixel((x, y), (30, 120, 30))
    im.putpixel((0, 0), (255, 0, 0))
    im.save(os.path.join(dirname, 'svgtile.png'))
    with open(os.path.join(dirname, 'svgeps.eps'), 'wb') as f:
        f.write(EPS)


def build(dirname):
    """Write svgall.sk and its files into DIRNAME; return its name."""
    testsupport.sketch()
    from Sketch import Trafo, Translation, Rotation, Point, CreatePath, \
         PolyBezier, Rectangle, Ellipse, SimpleText, Group, MaskGroup, \
         Image, EditDocument, MultiGradient, SolidPattern, \
         HatchingPattern, CreateRGBColor, GetFont, StandardArrows, \
         StandardDashes, load_image
    from Sketch.Base import plugins, const
    from Sketch.Graphics.pattern import LinearGradient, RadialGradient, \
         ConicalGradient, ImageTilePattern
    from Sketch.Graphics.eps import EpsImage
    from Sketch.Graphics.text import PathText
    from Sketch.Graphics.blendgroup import CreateBlendGroup

    write_images(dirname)
    filename = os.path.join(dirname, 'svgall.sk')
    cwd = os.getcwd()
    os.chdir(dirname)
    try:
        doc = EditDocument(create_layer = 1)
        rgb = CreateRGBColor
        red, green, blue = rgb(1, 0, 0), rgb(0, .6, 0), rgb(0, 0, 1)
        grad = MultiGradient([(0, rgb(1, 1, 0)), (0.3, rgb(1, 0, 0)),
                              (1, rgb(0, 0, 1))])

        def props(obj, **kw):
            obj.SetProperties(**kw)
            return obj

        def add(obj):
            doc.Insert(obj)
            return obj

        def bez(points):
            path = CreatePath()
            for p in points:
                if len(p) == 2:
                    path.AppendLine(*p)
                else:
                    path.AppendBezier(*p)
            return PolyBezier((path,))

        def text(s, x, y, font = 'Times-Roman', size = 18, trafo = None,
                 **kw):
            t = SimpleText(trafo or Translation(x, y), s, **kw)
            t.SetProperties(font = GetFont(font), font_size = size)
            return t

        # rectangles and ellipses
        add(props(Rectangle(Trafo(80, 0, 0, 50, 30, 760)),
                  fill_pattern = SolidPattern(red), line_width = 3))
        add(props(Rectangle(Translation(170, 740)(
            Rotation(0.4)(Trafo(80, 0, 0, 50, 0, 0))), 0.2, 0.3),
                  fill_pattern = SolidPattern(green), line_width = 4,
                  line_join = const.JoinRound))
        add(props(Rectangle(Trafo(30, 40, -60, 20, 260, 750)),
                  fill_pattern = SolidPattern(blue)))
        add(props(Ellipse(Trafo(40, 0, 0, 25, 360, 785)),
                  fill_pattern = SolidPattern(red), line_width = 2))
        add(props(Ellipse(Trafo(30, 20, -10, 15, 450, 785)),
                  fill_pattern = SolidPattern(green), line_width = 2))
        add(props(Ellipse(Trafo(30, 0, 0, 30, 530, 785), 0.3, 4.0,
                          const.ArcPieSlice),
                  fill_pattern = SolidPattern(blue), line_width = 1.5))
        # arcs, arrows, dashes, caps, hairline
        add(props(Ellipse(Trafo(30, 0, 0, 20, 60, 680), 0.5, 3.5,
                          const.ArcArc), line_width = 3))
        add(props(Ellipse(Trafo(30, 10, 0, 20, 140, 680), 1.0, 5.0,
                          const.ArcChord), line_width = 2,
                  fill_pattern = SolidPattern(rgb(.8, .8, 1))))
        add(props(Ellipse(Trafo(30, 0, 0, 20, 220, 680), 0.5, 3.5,
                          const.ArcArc), line_width = 3,
                  line_arrow1 = StandardArrows()[1],
                  line_arrow2 = StandardArrows()[3]))
        add(props(bez([(280, 660), (320, 700), (360, 660), (400, 700)]),
                  line_width = 3, line_dashes = StandardDashes()[3]))
        add(props(bez([(420, 660), (460, 700), (500, 660)]), line_width = 6,
                  line_cap = const.CapRound, line_join = const.JoinBevel,
                  line_dashes = (1, 2)))
        add(props(bez([(520, 660), (560, 700), (570, 650)]), line_width = 0))
        add(props(bez([(30, 620), (90, 640, 150, 600, 200, 625)]),
                  line_width = 2, line_arrow1 = StandardArrows()[2],
                  line_arrow2 = StandardArrows()[4]))
        # gradients and patterns
        add(props(Rectangle(Trafo(90, 0, 0, 60, 20, 540)),
                  fill_pattern = LinearGradient(
                      grad, Point(1, 0.5).normalized(), 0.1)))
        add(props(Rectangle(Trafo(90, 0, 0, 60, 130, 540)),
                  fill_pattern = RadialGradient(grad, Point(0.3, 0.7), 0.0)))
        add(props(Ellipse(Trafo(45, 0, 0, 30, 285, 570)),
                  fill_pattern = ConicalGradient(
                      grad, Point(0.5, 0.5), Point(1, 1).normalized()),
                  line_width = 2))
        add(props(Rectangle(Trafo(90, 0, 0, 60, 350, 540)),
                  fill_pattern = HatchingPattern(
                      blue, rgb(1, 1, .8), Point(1, 2).normalized(), 7, 2)))
        add(props(Ellipse(Trafo(45, 0, 0, 30, 515, 570)),
                  fill_pattern = ImageTilePattern(load_image('svgtile.png'),
                                                  Trafo(3, 1, 1, -3, 0, 0))))
        # a gradient in the local system of a rotated rectangle
        add(props(Rectangle(Translation(40, 440)(
            Rotation(0.3)(Trafo(70, 0, 0, 40, 0, 0)))),
                  fill_pattern = LinearGradient(grad, Point(0, -1), 0)))
        # text
        add(text('Plain Times fi AV', 150, 470))
        add(text('Helvetica-Bold', 150, 445, 'Helvetica-Bold', 16))
        add(props(text('Gradient', 330, 450, 'Helvetica-Bold', 30),
                  fill_pattern = LinearGradient(grad, Point(1, 0), 0)))
        add(text('rotated', 0, 0, 'Courier', 14,
                 trafo = Trafo(0.8, 0.6, -0.6, 0.8, 500, 430),
                 halign = 2, valign = 1))
        add(text('centered', 300, 410, 'Times-Italic', 14,
                 halign = 1, valign = 2))
        path = props(bez([(30, 330), (60, 400, 140, 400, 170, 330)]),
                     line_width = 0.5)
        add(PathText(text('Text on a path', 0, 0, 'Times-Roman', 14), path))
        # mask groups: a filled and stroked mask, a text mask
        mask = props(Ellipse(Trafo(70, 0, 0, 50, 280, 340)),
                     fill_pattern = SolidPattern(rgb(1, .9, .9)),
                     line_width = 3, line_pattern = SolidPattern(blue))
        inner = [props(Rectangle(Trafo(40, 0, 0, 150, 220 + 50 * i, 270)),
                       fill_pattern = SolidPattern((red, green, blue)[i]))
                 for i in range(3)]
        add(MaskGroup([mask] + inner))
        add(MaskGroup([text('MASK', 390, 310, 'Helvetica-Bold', 50),
                       props(Rectangle(Trafo(170, 0, 0, 60, 385, 300)),
                             fill_pattern = LinearGradient(
                                 grad, Point(1, 0), 0))]))
        # images
        add(Image(load_image('svgalpha.png'),
                  trafo = Trafo(1.5, 0.3, -0.3, 1.5, 30, 160)))
        add(EpsImage('svgeps.eps', Trafo(0.6, 0, 0, 0.6, 150, 150)))
        # blend group, nested groups
        b1 = props(Rectangle(Trafo(20, 0, 0, 20, 330, 200)),
                   fill_pattern = SolidPattern(red))
        b2 = props(Ellipse(Trafo(15, 0, 0, 15, 540, 260)),
                   fill_pattern = SolidPattern(blue))
        add(CreateBlendGroup(b1, b2, 5)[0])
        add(Group([props(Rectangle(Trafo(20, 0, 0, 20, 330, 100)),
                         fill_pattern = SolidPattern(green)),
                   Group([props(Ellipse(Trafo(10, 0, 0, 10, 380, 110)),
                                fill_pattern = SolidPattern(red))])]))
        # plugin objects
        for name, args in (('RegularPolygon', (6, 25.0,
                                               Translation(460, 110))),
                           ('LCDText', ('12:34', 14.0,
                                        Translation(500, 100)))):
            obj = plugins.find_object_plugin(name).CallFactory(*args)
            add(props(obj, fill_pattern = SolidPattern(rgb(.5, .2, .7)),
                      line_width = 1))
        # a hidden printable layer and a visible, locked, non-printable
        # one
        doc.AppendLayer('Hidden printable', visible = 0, printable = 1)
        doc.SetActiveLayer(len(doc.layers) - 1)
        add(props(Rectangle(Trafo(100, 0, 0, 20, 400, 30)),
                  fill_pattern = SolidPattern(rgb(1, .5, 0))))
        doc.AppendLayer('Notes (non-printable)', visible = 1, printable = 0)
        doc.SetActiveLayer(len(doc.layers) - 1)
        add(text('not printed', 30, 30))
        doc.layers[-1].SetState(1, 0, 1, 0)
        doc.AddGuideLine(Point(0, 500), 1)
        doc.AddGuideLine(Point(300, 0), 0)
        plugins.find_export_plugin(plugins.NativeFormat)(doc, filename)
    finally:
        os.chdir(cwd)
    return filename
