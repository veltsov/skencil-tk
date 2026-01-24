import Sketch.Scripting

from Sketch import Trafo, Scripting, Translation, Rotation,\
     Identity, Scale, _
from Sketch.UI.sketchdlg import SKModal
from Sketch.Graphics.selection import SizeSelection, \
     TrafoSelection

from Tkinter import StringVar, DoubleVar, Entry, Label, \
     Button, Frame, Checkbutton, IntVar, BOTH, TOP, LEFT
from math import pi


angular_units = {
    'deg' : 1.,
    'rad' : 180./pi
}

#
#  unit.py - a module for unit conversion
#            Tamito KAJIYAMA <26 March 2000>
# Copyright (C) 2000 by Tamito KAJIYAMA
# Copyright (C) 2000 by Bernhard Herzog
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

import re
import string
from Sketch.Lib.units import unit_dict


unit_dict = unit_dict.copy()
unit_dict.update(angular_units)

def convert(s):
    "Convert S (representing a value and unit) into a value in point."
    match = re.search('[^0-9]+$', s)
    if match:
        value, unit = s[:match.start()], s[match.start():]
        value = string.atof(value)
        unit = string.strip(unit)
        if unit_dict.has_key(unit):
            value = value * unit_dict[unit]
        elif unit:
            raise ValueError, "unsupported unit: " + unit
    else:
        value = string.atof(s)
    return value


class TransformDlg(SKModal):
    title = "Transform"

    def __init__(self, master, context, **kw):
        self.context = context
        self.main_window = context.main_window
        apply(SKModal.__init__, (self, master), kw)

    def build_dlg(self):
        top = self.top
        self.var_text = StringVar(top)

        frame = Frame(top)

        label = Label(frame, text = "duplicate:", anchor = 'e')
        label.grid(column = 0, row = 0, sticky = 'ew')
        
        self.var_duplicate = IntVar(top)
        checkbutton = Checkbutton(frame, variable = self.var_duplicate)
        checkbutton.grid(column = 2, row = 0, sticky = 'ew')

        self.var_movex = StringVar(top)
        self.var_movey = StringVar(top)

        label = Label(frame, text = "move:", anchor = 'e')
        label.grid(column = 0, row = 1, sticky = 'ew')
        label = Label(frame, text = "x=", anchor = 'e')
        label.grid(column = 1, row = 1, sticky = 'ew')
        entry = Entry(frame, textvariable = self.var_movex, width=5)
        entry.grid(column = 2, row = 1, sticky = 'ew')

        label = Label(frame, text = "y=", anchor = 'e')
        label.grid(column = 1, row = 2, sticky = 'ew')
        entry = Entry(frame, textvariable = self.var_movey, width=5)
        entry.grid(column = 2, row = 2, sticky = 'ew')

        self.var_rotate = StringVar(top)
        label = Label(frame, text = "rotate:", anchor = 'e')
        label.grid(column = 0, row = 3, sticky = 'ew')
        entry = Entry(frame, textvariable = self.var_rotate, width=5)
        entry.grid(column = 2, row = 3, sticky = 'ew')

        self.var_scale = DoubleVar(top)
        label = Label(frame, text = "scale:", anchor = 'e')
        label.grid(column = 0, row = 4, sticky = 'ew')
        entry = Entry(frame, textvariable = self.var_scale, width=5)
        entry.grid(column = 2, row = 4, sticky = 'ew')

        frame.pack(fill=BOTH, expand=1, side=TOP )
        frame = Frame(top)

        button = Button(frame, text= "Apply", command = self.apply)
        button.pack(side=LEFT)

        frame.pack(fill=BOTH, expand=1, anchor='w' )

        self.var_movex.set('0 pt')
        self.var_movey.set('0 pt')
        self.var_rotate.set('0 deg')
        self.var_scale.set(1)

    def warn(self, message):
        app = self.main_window.application
        app.MessageBox(title = 'Transform: Error',
                       message = message,
                       icon = 'warning')

    def apply(self, *args):
        try:
            dx = convert(self.var_movex.get())
            dy = convert(self.var_movey.get())
            theta = (convert(self.var_rotate.get()) % 360) *pi/180.
            fact = self.var_scale.get()
        except Exception, e:
            self.warn(e)
            return
            
        if fact == 0:
            self.warn(_('Zero is not allowed for scale.'))
            return 
        
        doc = self.main_window.document
        selected = doc.selection
        if len(selected) == 0:
            self.warn('No objects selected')
        else:
            center = None
            
            # trafoselection: rotate
            # sizeselection : scale
            
            if selected.__class__ == TrafoSelection:
                center = selected.center
                
            if center is None:
                p1 = selected.rect.end
                p2 = selected.rect.start
                center = 0.5*(p1+p2)
                
            cx, cy = center
            scale = Scale(fact)
            move1 = Translation(-cx, -cy)
            rotate = Rotation(theta)
            move2 = Translation(cx+dx, cy+dy)
            trafo = move2(scale(rotate(move1(Identity))))
            
            duplicate = self.var_duplicate.get()

            doc.BeginTransaction("Transforming Objects")
            try:
                try:
                    sel = []
                    for obj in doc.SelectedObjects():
                        if duplicate:
                            obj = obj.Duplicate()
                            obj.Transform(trafo)
                            doc.Insert(obj)
                            sel.append(obj)
                        else:
                            doc.AddUndo(obj.Transform(trafo))
                            
                    if duplicate:
                        # select inserted objects
                        doc.SelectObject(sel)
                        doc.selection = TrafoSelection(doc.selection)
                        selected = doc.selection
                        
                    selected.center = Translation(dx, dy)((cx,cy))
                except:
                    doc.AbortTransaction()
            finally:
                doc.EndTransaction()
        

def Transform(context):
    global Line_string
    dlg = TransformDlg(context.application.root, context)


Sketch.Scripting.AddFunction('Transform', 'Transform',
                             Transform,
                             script_type = Sketch.Scripting.AdvancedScript)
