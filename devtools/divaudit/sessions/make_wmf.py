#!/usr/bin/env python2
# Generate a minimal placeable WMF (binary) for the loader session.
# Run with python2; writes samples/minimal.wmf next to this script.

import os
import struct

out = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                   'samples', 'minimal.wmf')

records = []


def record(function, params=()):
    # params: tuple/list of 16-bit words
    body = struct.pack('<%dH' % len(params), *params)
    size = len(body) / 2 + 3          # words incl. size + function fields
    records.append(struct.pack('<IH', size, function) + body)

META_SETMAPMODE = 0x0103
META_SETWINDOWORG = 0x020B
META_SETWINDOWEXT = 0x020C
META_CREATEPENINDIRECT = 0x02FA
META_CREATEBRUSHINDIRECT = 0x02FC
META_SELECTOBJECT = 0x012D
META_POLYGON = 0x0324
META_POLYLINE = 0x0325
META_RECTANGLE = 0x030B
META_DELETEOBJECT = 0x010F

record(META_SETMAPMODE, [1])
record(META_SETWINDOWORG, [0, 0])
record(META_SETWINDOWEXT, [200, 150])
# BS_SOLID brush, color white (0x00FFFFFF COLORREF), hatch 0
record(META_CREATEBRUSHINDIRECT, [0, 0xFFFF, 0x00FF, 0, 0])
# PS_SOLID pen, width 1, color black
record(META_CREATEPENINDIRECT, [0, 1, 0, 0, 0x0000, 0, 0])
record(META_SELECTOBJECT, [1])
record(META_SELECTOBJECT, [0])
record(META_RECTANGLE, [10, 10, 180, 130])
pts = [20, 100, 60, 20, 100, 100, 140, 20, 180, 100]
record(META_POLYGON, [len(pts) / 2] + pts)
record(META_POLYLINE, [4, 10, 140, 190, 140, 190, 10, 100, 10])
record(META_DELETEOBJECT, [1])
record(META_DELETEOBJECT, [0])

placeable = struct.pack('<IH', 0x9AC6CDD7, 0)
placeable += struct.pack('<4h', 0, 0, 200 * 22, 150 * 22)   # bbox (22/in)
placeable += struct.pack('<H', 22)                          # units/inch
placeable += struct.pack('<I', 0)                           # reserved
words = struct.unpack('<10H', placeable[:20])
placeable += struct.pack('<H', reduce(lambda a, b: a ^ b, words))

max_record = max(struct.unpack('<I', r[:4])[0] for r in records)
filesize = (22 + 18) / 2 + sum(struct.unpack('<I', r[:4])[0]
                               for r in records)
wmf_header = struct.pack('<HHIIHHH', 1, 9, 0x0300, filesize, 2,
                         max_record, 0)

data = placeable + wmf_header + ''.join(records)

f = open(out, 'wb')
try:
    f.write(data)
finally:
    f.close()
print 'wrote %s (%d bytes)' % (out, len(data))
