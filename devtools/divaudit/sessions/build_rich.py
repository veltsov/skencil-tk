#!/usr/bin/env python2
# Headless division-audit session: build a document with varied object
# types and styles, save it to every export format and raster-render
# it.  Exercises the savers, the pattern/gradient math, the PS device
# and the plugin-object geometry.
#
# Run:  devtools/divaudit/python2-divaudit \
#           devtools/divaudit/sessions/build_rich.py

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import bootstrap, load_document, step, repo_root

Sketch = bootstrap()

OUT = '/tmp/divaudit/out'
if not os.path.isdir(OUT):
    os.makedirs(OUT)

from Sketch import (Point, Rectangle, Ellipse, PolyBezier, SimpleText,
                    SolidPattern, StandardArrows, StandardDashes,
                    StandardColors, CreateSimpleGradient)

doc = load_document(os.path.join(repo_root(), 'test/data/tarr.sk'))
layer = doc.layers[0]


def first(mapping):
    if hasattr(mapping, 'values'):
        return mapping.values()[0]
    return mapping[0]


def add(obj):
    doc.Insert(obj)
    return obj


def build_objects():
    from Sketch.Scripts.create_star import create_star_path
    from Sketch.Scripts.create_spiral import create_spiral_path
    star = add(PolyBezier((create_star_path(5, 2, 100),)))
    # create_spiral_path's radius goes through unit.convert: string
    add(PolyBezier((create_spiral_path(3, '80'),)))

    # Rectangle/Ellipse take a Trafo (or a scale number)
    from Sketch import Trafo
    add(Rectangle(Trafo(1, 0, 0, 1, 300, 300)))
    add(Ellipse(Trafo(1, 0, 0, 1, 550, 300)))

    add(SimpleText(Trafo(1, 0, 0, 1, 50, 700), 'div audit'))

    arrow = first(StandardArrows())
    add(PolyBezier((create_star_path(6, 2, 60),))).SetProperties(
        line_arrow1=arrow, line_arrow2=arrow)
    add(PolyBezier((create_star_path(7, 3, 60),))).SetProperties(
        line_dashes=first(StandardDashes()))
    from Sketch import MultiGradient
    grad = Sketch.LinearGradient(
        MultiGradient([(0, StandardColors.red), (1, StandardColors.blue)]))
    # on-screen gradient fills are fixed (RasterImage writable scratch
    # buffer, see devdocs/divaudit-findings.md #4); keep the gradient
    # rectangle visible so the interactive session exercises the draw
    # path
    add(Rectangle(Trafo(1, 0, 0, 1, 300, 550))).SetProperties(
        fill_pattern=grad)
    add(Ellipse(Trafo(1, 0, 0, 1, 550, 550))).SetProperties(
        fill_pattern=SolidPattern(StandardColors.green))
    return star


def plugin_objects():
    from Sketch.Plugins.Objects.regpoly import RegularPolygon
    from Sketch.Plugins.Objects.arrow import Arrow
    from Sketch.Plugins.Objects.lcdtext import LCDText
    add(RegularPolygon(vertices=6, radius=70))
    add(Arrow())

    def make_lcd():
        try:
            return LCDText()
        except TypeError:
            return LCDText('LCD')
    add(make_lcd())


SHAPES = ['angle', 'measure', 'rim', 'star', 'arc', 'circle3', 'divide',
          'intersection', 'smiley', 'thinturn', 'thinhalfturn',
          'scalebar', 'raster']


def autoshapes():
    from Sketch.Plugins.Objects.Lib.autoshapes.autoshapelib import \
        Autoshape
    made = 0
    for name in SHAPES:
        if step('autoshape ' + name, lambda n=name: add(Autoshape(n))):
            made += 1
    print '       (%d/%d autoshapes constructed)' % (made, len(SHAPES))


def export_all():
    from Sketch.Base import plugins
    for ext in ('.sk', '.eps', '.ps', '.ai', '.svg', '.wmf', '.cgm',
                '.pdf'):
        def save(ext=ext):
            plugin = plugins.find_export_plugin(
                plugins.guess_export_plugin(ext))
            path = os.path.join(OUT, 'rich' + ext)
            plugin(doc, path)
            print '       -> %s' % path
        step('export ' + ext, save)


def render():
    from Sketch.Scripts.export_raster import export_raster
    class Ctx:
        pass
    ctx = Ctx()
    ctx.document = doc
    export_raster(ctx, os.path.join(OUT, 'rich.ppm'), 72, 1)
    print '       -> %s' % os.path.join(OUT, 'rich.ppm')


def draw_ps():
    from Sketch.Graphics.psdevice import PostScriptDevice
    path = os.path.join(OUT, 'direct.ps')
    device = PostScriptDevice(path, as_eps=1, document=doc,
                              bounding_box=doc.BoundingRect())
    doc.Draw(device)
    device.Close()
    print '       -> %s' % path


def guides():
    doc.AddGuideLine(Point(100, 0), 0)
    doc.AddGuideLine(Point(0, 700), 1)


print '== build_rich'
step('build objects', build_objects)
step('plugin objects', plugin_objects)
step('autoshapes', autoshapes)
step('guides', guides)
step('export all formats', export_all)
step('raster render', render)
step('ps device draw', draw_ps)
print '== done (output in %s)' % OUT
