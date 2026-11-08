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


SAMPLES['gradients'] = (doc('width="400" height="300"', '''
<defs>
  <linearGradient id="base">
    <stop offset="0" stop-color="red"/>
    <stop offset="0.5" style="stop-color:yellow"/>
    <stop offset="1" stop-color="blue"/>
  </linearGradient>
  <linearGradient id="diag" xlink:href="#base" x1="0" y1="0" x2="1" y2="1"/>
  <linearGradient id="user" xlink:href="#base" gradientUnits="userSpaceOnUse"
    x1="120" y1="0" x2="200" y2="0" gradientTransform="rotate(20 160 50)"/>
  <radialGradient id="radial">
    <stop offset="0.2" stop-color="white"/>
    <stop offset="1" stop-color="green"/>
  </radialGradient>
  <radialGradient id="radial-user" xlink:href="#radial"
    gradientUnits="userSpaceOnUse" cx="330" cy="60" r="70"/>
  <linearGradient id="opaque" x2="0" y2="1">
    <stop offset="0" stop-color="black" stop-opacity="0.2"/>
    <stop offset="1" stop-color="purple"/>
  </linearGradient>
</defs>
<rect x="10" y="10" width="100" height="80" fill="url(#base)"/>
<rect x="120" y="10" width="80" height="80" fill="url(#user)"/>
<ellipse cx="260" cy="50" rx="45" ry="30" fill="url(#diag)"
  stroke="black" stroke-width="3"/>
<rect x="300" y="10" width="90" height="100" fill="url(#radial-user)"/>
<circle cx="260" cy="170" r="50" fill="url(#radial)"/>
<path d="M320 130 l60 0 l-30 60 z" fill="url(#opaque)"
  transform="rotate(15 350 160)"/>
<rect x="10" y="210" width="180" height="40"
  fill="url(#missing) orange"/>
<rect x="210" y="230" width="180" height="60" fill="url(#base)"
  transform="skewX(20) translate(-80 0)"/>
'''), 0.008)

# Sketch's PostScript output samples gradients in 50 steps
# (gradient_steps_print), too coarse for many periods.  (Inkscape
# places the tiles of objectBoundingBox patterns differently from the
# specification: tested in test_svgimport_model.py instead.)
SAMPLES['gradient-spread'] = (doc('width="200" height="110"', '''
<defs>
  <linearGradient id="base">
    <stop offset="0" stop-color="red"/>
    <stop offset="0.5" style="stop-color:yellow"/>
    <stop offset="1" stop-color="blue"/>
  </linearGradient>
  <linearGradient id="reflect" xlink:href="#base" x1="0.3" x2="0.7"
    spreadMethod="reflect"/>
  <linearGradient id="repeat" xlink:href="#base" x1="0.2" x2="0.6"
    spreadMethod="repeat"/>
</defs>
<rect x="10" y="10" width="180" height="40" fill="url(#reflect)"/>
<rect x="10" y="60" width="180" height="40" fill="url(#repeat)"/>
'''), 0.05)

SAMPLES['patterns'] = (doc('width="400" height="200"', '''
<defs>
  <pattern id="checker" width="20" height="20" patternUnits="userSpaceOnUse">
    <rect width="10" height="10" fill="black"/>
    <rect x="10" y="10" width="10" height="10" fill="black"/>
  </pattern>
  <pattern id="dots" x="3" y="5" width="16" height="20"
    patternUnits="userSpaceOnUse">
    <circle cx="8" cy="8" r="4" fill="red"/>
  </pattern>
  <pattern id="tile" width="16" height="8" patternUnits="userSpaceOnUse"
    patternTransform="rotate(30)">
    <image width="16" height="8" preserveAspectRatio="none"
      style="image-rendering:optimizeSpeed" xlink:href="%(png)s"/>
  </pattern>
  <pattern id="lines" xlink:href="#checker" patternTransform="scale(0.5)"/>
</defs>
<rect x="10" y="10" width="120" height="80" fill="url(#checker)"
  stroke="blue" stroke-width="2"/>
<circle cx="210" cy="50" r="40" fill="url(#dots)"/>
<rect x="270" y="10" width="120" height="80" fill="url(#tile)"/>
<rect x="10" y="110" width="120" height="80" fill="url(#lines)"/>
''' % {'png': png_data_uri((16, 8))}), 0.006)


SAMPLES['text'] = (doc('width="400" height="220"', '''
<style>.big { font-size: 28px; font-family: serif }</style>
<text x="10" y="40" class="big">Serif <tspan fill="red"
  font-weight="bold">bold red</tspan> x<tspan dy="-10"
  font-size="16">2</tspan></text>
<text x="390" y="80" style="font-family:sans-serif;font-size:20px;
  text-anchor:end" fill="blue">anchored at the end</text>
<text x="200" y="120" text-anchor="middle" font-family="monospace"
  font-size="18" letter-spacing="3">mono spaced</text>
<text x="20 40 60 80" y="170 160 170 160" font-size="24"
  rotate="0 15 30 45">abcd</text>
<g transform="translate(250 200) rotate(-20)"><text font-size="22"
  stroke="green" stroke-width="0.8" fill="yellow">stroked</text></g>
<defs><path id="arc" d="M120 210 Q200 140 280 210"/></defs>
<text font-size="16"><textPath xlink:href="#arc">text on a path
  </textPath></text>
'''), 0.01)

SAMPLES['markers'] = (doc('width="400" height="200"', '''
<defs>
  <marker id="arrow" viewBox="0 0 10 10" refX="10" refY="5"
    markerWidth="6" markerHeight="6" orient="auto-start-reverse">
    <path d="M0 0 L10 5 L0 10 z" fill="navy"/>
  </marker>
  <marker id="dot" markerWidth="8" markerHeight="8" refX="4" refY="4"
    markerUnits="userSpaceOnUse">
    <circle cx="4" cy="4" r="3" fill="red"/>
  </marker>
  <marker id="clipped" markerWidth="4" markerHeight="4" refX="2" refY="2"
    orient="45">
    <rect width="4" height="4" fill="green"/>
  </marker>
</defs>
<path d="M20 30 L150 30 L180 80" fill="none" stroke="black"
  stroke-width="2" marker-start="url(#arrow)" marker-end="url(#arrow)"/>
<polyline points="220,30 260,80 300,30 340,80 380,30" fill="none"
  stroke="gray" stroke-width="1.5" marker-mid="url(#dot)"
  marker-start="url(#dot)" marker-end="url(#dot)"/>
<path d="M30 120 C80 60 130 180 180 120" fill="none" stroke="purple"
  stroke-width="3" style="marker:url(#clipped)"/>
<polygon points="250,110 330,110 290,180" fill="#fe8" stroke="black"
  marker-mid="url(#dot)"/>
'''), 0.003)


def write(name, dir):
    path = os.path.join(dir, name + '.svg')
    with open(path, 'w') as f:
        f.write(SAMPLES[name][0])
    return path
