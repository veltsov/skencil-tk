# Sample SVG files for test_svgimport.py: name -> (source, max_diff).
# MAX_DIFF is the fraction of (4x downsampled) pixels allowed to differ
# from Inkscape's rendering.

import base64
import io
import os


def png_data_uri(size = (8, 4), alpha = False):
    from PIL import Image
    image = Image.new('RGBA' if alpha else 'RGB', size)
    pixels = image.load()
    for x in range(size[0]):
        for y in range(size[1]):
            color = ((x * 255) // size[0], (y * 255) // size[1], 128)
            if alpha:
                color = color + (255 if x < size[0] // 2 else 96,)
            pixels[x, y] = color
    buf = io.BytesIO()
    image.save(buf, 'PNG')
    return 'data:image/png;base64,' + base64.b64encode(buf.getvalue()).decode()


HEAD = ('<?xml version="1.0"?>\n'
        '<svg xmlns="http://www.w3.org/2000/svg" '
        'xmlns:xlink="http://www.w3.org/1999/xlink" %s>\n')

def doc(attrs, body):
    return HEAD % attrs + body + '\n</svg>\n'


SAMPLES = {}

SAMPLES['shapes'] = (doc(
    'width="200mm" height="100mm" viewBox="0 0 200 100"', '''
<style>.r { fill: #c00; stroke: navy; stroke-width: 2 }</style>
<rect class="r" x="10" y="10" width="40" height="30" rx="5"/>
<rect x="55" y="10" width="20" height="30" rx="4" ry="10" fill="teal"/>
<circle cx="90" cy="25" r="12" fill="green"/>
<ellipse cx="125" cy="25" rx="15" ry="8" transform="rotate(30 125 25)"
  style="fill:none;stroke:black;stroke-width:1.5"/>
<line x1="5" y1="95" x2="195" y2="95" stroke="gray" stroke-width="1"/>
<polyline points="100,60 110,90 120,60 130 90" fill="none" stroke="red"
  stroke-width="2" stroke-linejoin="round"/>
<polygon points="140,60 160,90 180,60" fill="gold" stroke="black"/>
<path d="M20 60 q10 -20 20 0 t20 0 c5 10 15 10 20 0 s15 -10 20 0"
  fill="none" stroke="purple" stroke-width="2"/>
<path d="M180 15 a10 10 0 1 1 0.1 0z M150 45 a15 6 30 0 0 30 0"
  fill="cyan" stroke="black"/>
'''), 0.002)

SAMPLES['opacity'] = (doc('width="300" height="200"', '''
<rect x="10" y="10" width="100" height="80" fill="red" fill-opacity="0.5"/>
<g opacity="0.4"><circle cx="200" cy="50" r="40" fill="blue"/></g>
<rect x="10" y="110" width="100" height="80" fill="none" stroke="green"
  stroke-width="10" stroke-opacity="0.3"/>
<rect x="150" y="110" width="100" height="80" style="fill:#000;fill-opacity:.25"/>
'''), 0.002)

SAMPLES['units'] = (doc(
    'width="4in" height="2in" viewBox="0 0 400 100" '
    'preserveAspectRatio="xMinYMax meet"', '''
<rect x="0" y="0" width="400" height="100" fill="#eee"/>
<rect x="1cm" y="10mm" width="72pt" height="2em" style="font-size:10px"
  fill="red"/>
<rect x="50%" y="25%" width="10%" height="50%" fill="blue"/>
<svg x="300" y="10" width="80" height="80" viewBox="0 0 10 20"
  preserveAspectRatio="xMidYMid slice" overflow="visible">
  <circle cx="5" cy="10" r="8" fill="green"/>
</svg>
'''), 0.002)

SAMPLES['use'] = (doc('width="300" height="150"', '''
<defs>
  <path id="tri" d="M0 0 l20 0 l-10 -16z"/>
  <symbol id="sym" viewBox="0 0 10 10"><circle cx="5" cy="5" r="5"/>
    <rect width="5" height="5" fill="white"/></symbol>
  <g id="pair" fill="orange"><use xlink:href="#tri"/>
    <use xlink:href="#tri" x="25"/></g>
</defs>
<g fill="blue" transform="translate(10 40) rotate(10)">
  <use xlink:href="#tri"/><use xlink:href="#tri" x="30" fill="red"/>
</g>
<use xlink:href="#sym" x="100" y="10" width="60" height="60" fill="purple"/>
<use xlink:href="#sym" x="170" y="10" width="40" height="80"/>
<use xlink:href="#pair" x="20" y="120"/>
<use xlink:href="#pair" x="120" y="120" transform="scale(1.5 1)"/>
'''), 0.002)

SAMPLES['fillrule'] = (doc('width="300" height="120"', '''
<path d="M10 10 h80 v80 h-80z M30 30 h40 v40 h-40z" fill="orange"
  stroke="black" stroke-width="2"/>
<path d="M110 10 h80 v80 h-80z M130 30 v40 h40 v-40z" fill="green"/>
<path d="M210 10 h80 v80 h-80z M230 30 h40 v40 h-40z" fill="navy"
  fill-rule="evenodd"/>
<path d="M10 100 h10 v10 h-10z M30 100 h10 v10 h-10z" fill="red"/>
'''), 0.002)

SAMPLES['dashes'] = (doc('width="300" height="120"', '''
<g fill="none" stroke="black" stroke-width="4">
  <path d="M10 10 H290" stroke-dasharray="20 10"/>
  <path d="M10 30 H290" stroke-dasharray="20 10" stroke-dashoffset="5"/>
  <path d="M10 50 H290" stroke-dasharray="20 10" stroke-dashoffset="25"/>
  <path d="M10 70 H290" stroke-dasharray="30 5 10"/>
  <path d="M10 90 H290" stroke-dasharray="8" stroke-linecap="butt"
    transform="translate(0 0)"/>
  <path d="M10 110 H290" stroke-width="1" stroke-dasharray="5,5"/>
</g>
'''), 0.003)

SAMPLES['clip'] = (doc('width="300" height="200"', '''
<defs>
  <clipPath id="circle"><circle cx="60" cy="60" r="40"/></clipPath>
  <clipPath id="bbox" clipPathUnits="objectBoundingBox">
    <rect x="0.25" y="0" width="0.5" height="1"/></clipPath>
  <clipPath id="two"><rect x="160" y="20" width="40" height="80"/>
    <circle cx="230" cy="60" r="30"/></clipPath>
  <clipPath id="nested" clip-path="url(#circle)">
    <rect x="20" y="110" width="200" height="40"/></clipPath>
</defs>
<g clip-path="url(#circle)"><rect x="0" y="0" width="120" height="120"
  fill="purple"/><path d="M0 60 H120" stroke="yellow" stroke-width="8"/></g>
<rect x="20" y="130" width="100" height="60" fill="teal"
  clip-path="url(#bbox)"/>
<rect x="150" y="10" width="140" height="100" fill="red"
  clip-path="url(#two)"/>
<rect x="150" y="120" width="100" height="70" fill="blue"
  clip-path="url(#circle)"/>
'''), 0.012)

# Inkscape interpolates images (unless image-rendering asks it not to)
# and ignores preserveAspectRatio on them; PostScript ignores alpha
SAMPLES['images'] = (doc('width="300" height="200"', '''
<g style="image-rendering:optimizeSpeed">
<image x="10" y="10" width="80" height="40" preserveAspectRatio="none"
  xlink:href="%(rgb)s"/>
<image x="10" y="100" width="120" height="60" preserveAspectRatio="none"
  xlink:href="%(rgb)s" transform="rotate(10 70 130)"/>
<image x="150" y="20" width="100" height="100" preserveAspectRatio="none"
  xlink:href="%(rgb)s" transform="matrix(1 0.2 -0.3 1 0 0)"/>
</g>
''' % {'rgb': png_data_uri()}), 0.006)


def write(name, dir):
    path = os.path.join(dir, name + '.svg')
    with open(path, 'w') as f:
        f.write(SAMPLES[name][0])
    return path
