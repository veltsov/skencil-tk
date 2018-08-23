
import Sketch
from Sketch import _, Polar, SingularMatrix, Scale, Rotation, RegisterCommands
from Sketch.Graphics import handle
from Sketch.UI.command import AddCmd

from autoshapelib import AutoshapeBase
from math import pi, cos, sin


class Angle(AutoshapeBase):
    
    l1 = 50
    l2 = 50
    r  = 10
    theta1 = 0
    theta2 = 90

    help_text = _("""
Angle
~~~~~

Keys:
    up         increase angle by 1 deg
    down       decrease angle by 1 deg
    shift-down increase angle by 0.1 deg
    shift-up   decrease angle by 0.1 deg

Modifier:
    control only allow multiples of 5 deg
    shift   keep angles fixed
    """)
    
    def GetHandles(self):
        handles = []
        theta1 = self.theta1
        theta2 = self.theta2
        if theta2 < theta1:
            theta2 = theta2+360
        p1 = Polar(self.l1, theta1*pi/180)
        p2 = Polar(self.l2, theta2*pi/180)
        p3 = Rotation(pi/360*(theta2-theta1))(Polar(self.r, theta1*pi/180))
                        
        for p in (p1, p2):
            handles.append(handle.MakeNodeHandle(self.trafo(p)))

        for p in (0.5*p1, 0.5*p2, p3):
            handles.append(handle.MakeControlHandle(self.trafo(p)))
        
        return handles
                
    def recompute(self):
        p1 = Polar(self.l1, self.theta1*pi/180)
        p2 = Polar(self.l2, self.theta2*pi/180)

        new = Sketch.CreatePath()
        newpaths = [new]

        new.AppendLine(p1)
        new.AppendLine((0,0))
        new.AppendLine(p2)
        
        new.Transform(self.trafo)
        alpha = p1.polar()[1]
        beta = p2.polar()[1]
        if self.objects:
            self.objects[0].SetPaths(newpaths)
            self.objects[1].SetAngles(alpha, beta)
            trafo = self.trafo(Scale(self.r, self.r))
            self.objects[1].set_transformation(trafo)
        else:
            lines = Sketch.PolyBezier(tuple(newpaths))
            circle = Sketch.Ellipse(start_angle=alpha, end_angle=beta)
            circle.Transform(Scale(self.r, self.r))
            self.set_objects([lines, circle])
            
    def DragHandle(self, pa, pb, selection):
        try:
            inverse = self.trafo.inverse()
        except SingularMatrix:
            return
        
        pa, pb = map(inverse, (pa, pb))
        delta = pb-pa

        theta1 = self.theta1
        theta2 = self.theta2
        if theta2 < theta1:
            theta2 = theta2+360

        p1 = Polar(self.l1, theta1*pi/180)
        p2 = Polar(self.l2, theta2*pi/180)
        p3 = Rotation(pi/360*(theta2-theta1))(Polar(self.r, theta1*pi/180))
        
        if selection == 1:
            p1 = p1 + delta
            self.l1, angle = p1.polar()            
            if not self.shift_pressed:
                self.theta1 = angle*180/pi    
        elif selection == 2:
            p2 = p2 + delta
            self.l2, angle = p2.polar()
            if not self.shift_pressed:                
                self.theta2 = angle*180/pi
        elif selection == 3:
            self.theta1 = (0.5*p1+delta).polar()[1]*180/pi 
        elif selection == 4:
            self.theta2 = (0.5*p2+delta).polar()[1]*180/pi
        elif selection == 5:
            p3 = p3 + delta
            l, angle = p3.polar()
            angle = angle*180/pi % 360
            begin = self.theta1 % 360
            end = self.theta2 % 360
            if end < begin:
                end = end+ 360
            if angle >= begin and angle <= end:
                self.r = l
            else:
                self.r = 0
        if self.control_pressed:
            if selection in (1,3):
                self.theta1 = int(0.5+self.theta1/5.)*5
            elif selection in (2,4):
                self.theta2 = int(0.5+self.theta2/5.)*5

        self.recompute()

    def SetData(self, data, version=None):
        self.l1, self.l2, self.r, self.theta1, self.theta2 = data

    def GetData(self):
        return self.l1, self.l2, self.r, self.theta1, self.theta2

    def Info(self):
        angle = self.theta2-self.theta1
        if angle < 0:
            angle = angle + 360
        value = int(angle*1000.+0.5)/1000.
        return "Angle of %s degrees" % value

    def ChangeAngleRounded(self, delta, step=1):
        step = float(step)
        angle = self.theta2-self.theta1
        theta2 = self.theta1+int(((angle+delta) % 360)/step+0.5)*step
        return self.SetParameters({'theta2' : theta2})

    def KeyHandler(self, key):
        if key == 'Up':
            return self.ChangeAngleRounded(1)
        elif key == 'Down':
            return self.ChangeAngleRounded(-1)
        elif key == 'S-Up':
            return self.ChangeAngleRounded(0.1, step=0.1)
        elif key == 'S-Down':
            return self.ChangeAngleRounded(-0.1, step=0.1)
        
def register():
    return Angle
