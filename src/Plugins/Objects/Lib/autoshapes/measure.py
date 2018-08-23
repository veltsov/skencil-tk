
import Sketch
from Sketch import _, Point, Polar, SingularMatrix, const, config, NullUndo
from Sketch.Lib import units
from Sketch.Graphics.handle import Handle, MakeControlHandle

from autoshapelib import AutoshapeBase
from math import pi

def MakeRoundHandle(p, code = 0):
    return Handle(const.Handle_FilledCircle, p, code = code)

class Measure(AutoshapeBase):

    h1 = 15
    h2 = 15
    h3 = 5
    theta = 90
    p1 = Point(0,0)
    p2 = Point(50,0)

    help_text = _("""
Length Measure
~~~~~~~~~~~~~~

Keys:
    up           increase length by 1 unit
    down         decrease length by 1 unit
    shift-up     increase length by 0.1 units
    shift-down   decrease length by 0.1 units
    control-up   increase length by 0.01 units
    control-down decrease length by 0.01 units

    "unit" is the default unit e.g. 1 cm

Modifier:    
    shift   keep length fixed
    control round orientation to multiples of
            15 deg
    """)
    
    def GetHandles(self):
        h1, h2, h3, theta, p1, p2 = self.h1, self.h2, self.h3, self.theta, \
                                    self.p1, self.p2
        xvect = (p2-p1).normalized()
        angle = (p2-p1).polar()[1] + theta*pi/180
        yvect = Polar(1, angle)

        handles = []
        for p in (p1, p2):
            handles.append(MakeRoundHandle(self.trafo(p)))

        for p in (p1+h1*yvect, p2+h2*yvect, 0.5*(p1+p2)+h3*yvect,
                  p1+h1*yvect*0.5, p2+h2*yvect*0.5):
            handles.append(MakeControlHandle(self.trafo(p)))        
        return handles
                
    def recompute(self):
        h1, h2, h3, theta, p1, p2 = self.h1, self.h2, self.h3, self.theta, \
                                    self.p1, self.p2
        xvect = (p2-p1).normalized()
        angle = (p2-p1).polar()[1] + theta*pi/180
        yvect = Polar(1, angle)

        new = Sketch.CreatePath()
        newpaths = [new]

        new.AppendLine(p1)
        new.AppendLine(p1+h1*yvect)
        new = Sketch.CreatePath()
        newpaths.append(new)
        new.AppendLine(p1+h3*yvect)
        new.AppendLine(p2+h3*yvect)
        new = Sketch.CreatePath()
        newpaths.append(new)        
        new.AppendLine(p2)
        new.AppendLine(p2+h2*yvect)

        for new in newpaths:
            new.Transform(self.trafo)
        if self.objects:
            self.objects[0].SetPaths(newpaths)
        else:
            lines = Sketch.PolyBezier(tuple(newpaths))
            self.set_objects([lines])
            
    def DragHandle(self, pa, pb, selection):
        try:
            inverse = self.trafo.inverse()
        except SingularMatrix:
            return

        
        pa, pb = map(inverse, (pa, pb))
        delta = pb-pa

        h1, h2, h3, theta, p1, p2 = self.h1, self.h2, self.h3, self.theta, \
                                    self.p1, self.p2
        xvect = (p2-p1).normalized()
        xnvect = Point(xvect.y, -xvect.x)
        angle = (p2-p1).polar()[1] + theta*pi/180
        yvect = Polar(1, angle)
        sin_theta = xnvect * yvect
        if sin_theta == 0:
            h = delta*xvect
        else:
            h = (xnvect*delta)/sin_theta
        l, angle = (p1-p2).polar()
        
        if selection == 1:            
            p1 = p1 + delta
            if self.shift_pressed:
                s, angle = (p1-p2).polar()
                p1 = (p1-p2)*l/s+p2
            if self.control_pressed:
                s, angle = (p1-p2).polar()
                theta = int(theta*180/pi/15+0.5)*pi/180*15.
                p1 = p2+s*Polar(1,angle)                
            self.p1 = p1
        elif selection == 2:
            l, angle = (p1-p2).polar()
            p2 = p2 + delta
            if self.shift_pressed:
                s, angle = (p2-p1).polar()
                p2 = (p2-p1)*l/s+p1
            if self.control_pressed:
                s, angle = (p2-p1).polar()
                theta = int(theta*180/15/pi+0.5)*pi/180*15.
                p2 = p1+s*Polar(1,theta)                                
            self.p2 = p2
        elif selection == 3:
            self.h1 = h1+h
        elif selection == 4:
            self.h2 = h2+h
        elif selection == 5:
            # the middle line
            h3 = max(0, h3+h)
            if h3 > h1: h3 = h1
            if h3 > h2: h3 = h2            
            self.h3 = h3
            
        elif selection == 6:
            g = p1+h1*yvect*0.5
            p = g+delta
            angle = (p-p1).polar()[1]-(p2-p1).polar()[1]
            self.theta = 180*angle/pi
        elif selection == 7:
            g = p2+h2*yvect*0.5
            p = g+delta
            angle = (p-p2).polar()[1]-(p2-p1).polar()[1]
            self.theta = 180*angle/pi
            
        self.recompute()

    def SetData(self, data, version=None):
        self.h1, self.h2, self.h3, self.theta = data[:4]
        self.p1 = Point(*data[4:6])
        self.p2 = Point(*data[6:8])

    def GetData(self):
        return self.h1, self.h2, self.h3, self.theta, \
               self.p1.x, self.p1.y, self.p2.x, self.p2.y

    def Info(self):
        unit_name = config.preferences.default_unit
        pt_per_unit = units.unit_dict[unit_name]
        
        l = (self.p1-self.p2).polar()[0] / float(pt_per_unit)
        value = int(l*10000.+0.5)/10000.
        return "Measure of %s %s" % (value, unit_name)

    def ChangeLengthRounded(self, delta, step=1):
        p1, p2 = self.p1, self.p2
        
        l = (p1-p2).polar()[0]+delta
        l = int(l/float(step)+0.5)*step
        if l <= 0:
            return NullUndo
        xvect = (p2-p1).normalized()
        return self.SetParameters({'p2' : (p1+xvect*l)})

    def KeyHandler(self, key):
        unit_name = config.preferences.default_unit
        pt_per_unit = units.unit_dict[unit_name]
        f = float(pt_per_unit)
        
        if key == 'Up':
            return self.ChangeLengthRounded(f, step=f)
        elif key == 'Down':
            return self.ChangeLengthRounded(-f, step=f)
        elif key == 'S-Up':
            return self.ChangeLengthRounded(0.1*f, step=0.1*f)
        elif key == 'S-Down':
            return self.ChangeLengthRounded(-0.1*f, step=0.1*f)
        elif key == 'C-Up':
            return self.ChangeLengthRounded(0.01*f, step=0.01*f)
        elif key == 'C-Down':
            return self.ChangeLengthRounded(-0.01*f, step=0.01*f)
        
def register():
    return Measure
