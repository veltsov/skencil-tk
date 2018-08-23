
import Sketch
from Sketch import _, Polar, SingularMatrix, Scale, Rotation, RegisterCommands
from Sketch.Graphics import handle
from Sketch.UI.command import AddCmd

from autoshapelib import AutoshapeBase
from math import pi, cos, sin


class Rim(AutoshapeBase):
    
    r1 = 20
    r2 = 50
    theta1 = 60
    theta2 = 120
    help_text = _("""
Rim
~~~

Keys:
    +       increase angle by 1 deg
    -       decrease angle by 1 deg

Modifier:
    control only allow multiples of 5 deg
    shift   keep angles fixed
    """)
    
    def GetHandles(self):
        handles = []
        r1 = self.r1
        r2 = self.r2
        theta1 = self.theta1
        theta2 = self.theta2
        p1 = Polar(r1, theta1*pi/180)
        p2 = Polar(r2, theta1*pi/180)
        p3 = Polar(r1, theta2*pi/180)
        p4 = Polar(r2, theta2*pi/180)
        p5 = 0.5*(p1+p2)
        p6 = 0.5*(p3+p4)
        
        for p in (p1, p2, p3, p4, p5, p6):
            handles.append(handle.MakeControlHandle(self.trafo(p)))        
        return handles
                
    def recompute(self):
        r1 = self.r1
        r2 = self.r2
        theta1 = self.theta1
        theta2 = self.theta2
        if theta2 < theta1:
            theta2 = theta2+360

        ring2 = Sketch.Ellipse(start_angle=theta1*pi/180,
                               end_angle=theta2*pi/180,
                               arc_type=0).Paths()[0]
        ring1 = ring2.Duplicate()
        ring2.Transform(Scale(r2))
        ring1.Transform(Scale(r1))
        new = Sketch.CreatePath()
        newpaths = [new]

        new.AppendLine(Polar(r1, theta1*pi/180.))
        for i in range(ring2.len):
            segment = ring2.Segment(i)
            new.AppendSegment(*segment)

        new.AppendLine(Polar(r2, theta2*pi/180.))
        new.AppendLine(Polar(r1, theta2*pi/180.))

        ring1.Transform(Scale(-1,1))
        ring1.Transform(Rotation((180+theta1+theta2)*pi/180.))
        
        for i in range(ring1.len):
            s = ring1.Segment(i)
            new.AppendSegment(*s)

        for path in newpaths:
            path.Transform(self.trafo)
        if self.objects:
            self.objects[0].SetPaths(newpaths)
        else:
            obj = Sketch.PolyBezier(tuple(newpaths))
            self.set_objects([obj])
            
    def DragHandle(self, pa, pb, selection):
        try:
            inverse = self.trafo.inverse()
        except SingularMatrix:
            return
        
        pa, pb = map(inverse, (pa, pb))
        delta = pb-pa

        r1 = self.r1
        r2 = self.r2
        theta1 = self.theta1 % 360
        theta2 = self.theta2 % 360
        p1 = Polar(r1, theta1*pi/180)
        p2 = Polar(r2, theta1*pi/180)
        p3 = Polar(r1, theta2*pi/180)
        p4 = Polar(r2, theta2*pi/180)
        p5 = 0.5*(p1+p2)
        p6 = 0.5*(p3+p4)

        if theta2 < theta1:
            theta2 = theta2+360
            
        if selection == 1:
            p1 = p1 + delta
            self.r1, angle = p1.polar()
            angle = angle*180/pi % 360
            if angle < theta1-2 or angle > theta2+2:
                self.r1 = 0
            if not self.shift_pressed:
                self.theta1 = angle
            
        elif selection == 2:
            p2 = p2 + delta
            self.r2, angle = p2.polar()
            if not self.shift_pressed:                
                self.theta1 = angle*180/pi
        elif selection == 3:
            p3 = p3 + delta
            self.r1, angle = p3.polar()
            angle = angle*180/pi % 360    
            if angle < theta1-2 or angle > theta2+2:
                self.r1 = 0
            if not self.shift_pressed:
                self.theta2 = angle
        elif selection == 4:
            p4 = p4 + delta
            self.r2, angle = p4.polar()
            if not self.shift_pressed:                
                self.theta2 = angle*180/pi
        elif selection == 5:
            p5 = p5 + delta
            angle = p5.polar()[1]            
            self.theta1 = angle*180/pi    
        elif selection == 6:
            p6 = p6 + delta
            angle = p6.polar()[1]
            self.theta2 = angle*180/pi

        if self.control_pressed:
            if selection in (1,2,5):
                self.theta1 = int(0.5+self.theta1/5.)*5
            elif selection in (3,4,6):
                self.theta2 = int(0.5+self.theta2/5.)*5


        self.recompute()

    def SetData(self, data, version=None):
        self.r1, self.r2, self.theta1, self.theta2 = data

    def GetData(self):
        return self.r1, self.r2, self.theta1, self.theta2

    def Info(self):
        angle = self.theta2-self.theta1
        if angle < 0:
            angle = angle + 360
        value = int(angle*1000.+0.5)/1000.
        return "Rim of %s degrees. " % value

    def ChangeAngleRounded(self, delta, step=1):
        angle = self.theta2-self.theta1
        theta2 = self.theta1+int((0.5+angle+delta) % 360)
        return self.SetParameters({'theta2' : theta2})

    def KeyHandler(self, key):
        if key == '+':
            return self.ChangeAngleRounded(1)
        elif key == '-':
            return self.ChangeAngleRounded(-1)

def register():
    return Rim
