import Sketch
from Sketch import _, Point, Polar, Scale, Ellipse, SingularMatrix
from Sketch.Graphics import handle
from autoshapelib import AutoshapeBase
from math import sqrt

class Circle3(AutoshapeBase):

    p1 = Point(20,20)
    p2 = Point(0,0)
    p3 = Point(20,-20)

    help_text = _("""
Circle3
~~~~~~~
A circle through three control points

Keys:
    none

Modifier:
    shift     translate circle
    control   keep radius fixed
    """)

    def LayoutPoint(self):
        c = self.Calc()[0]
        return self.trafo(c)
    
    def GetSnapPoints(self):
        c = self.Calc()[0]
        return map(self.trafo, (self.p1, self.p2, self.p3, c))
    
    def GetHandles(self):
        handles = []      
        for p in (self.p1, self.p2, self.p3):
            handles.append(handle.MakeNodeHandle(self.trafo(p)))
        return handles

    def Calc(self):
        # calculate center position and radius
        p1, p2, p3 = self.p1, self.p2, self.p3
        f1 = 0.5*(p1+p2)
        f2 = 0.5*(p2+p3)
        tmp = (p2-p1).normalized()
        n1 = Point(tmp[1], -tmp[0])
        tmp = (p3-p2).normalized()
        n2 = Point(tmp[1], -tmp[0])
        x = f2-n2*(f2-f1)*n2

        nn2 = (p3-p2).normalized()
        sin_alpha = n1*nn2
        if sin_alpha == 0:
            return Point(0,0), 1e9 # XXX is there a better way ?

        h = (x-f1)*nn2
        s = h/sin_alpha
        c = f1+s*n1
        return c, (c-p1).polar()[0] 
    
    def recompute(self):        
        center, radius = self.Calc()
        obj = Ellipse(Scale(radius))
        obj.Translate(center)
        obj.Transform(self.trafo)
        if self.objects:
            self.objects[0].set_transformation(obj.trafo)
        else:
            self.set_objects([obj])
            
    def DragHandle(self, pa, pb, selection):
        try:
            inverse = self.trafo.inverse()
        except SingulareMatrix:
            return
        pa, pb = map(inverse, (pa, pb))
        delta = pb-pa

        p1, p2, p3 = self.p1, self.p2, self.p3
        if self.control_pressed:
            c = self.Calc()[0]
            l1 = (p1-c).polar()[0]
            l2 = (p2-c).polar()[0]
            l3 = (p3-c).polar()[0]
                                
        if selection == 1 or self.shift_pressed:
            p1 = p1 + delta
            if self.control_pressed:
                angle = (p1-c).polar()[1]
                p1 = Polar(l1, angle)+c
            self.p1 = p1
        if selection == 2 or self.shift_pressed:
            p2 = p2 + delta
            if self.control_pressed:
                angle = (p2-c).polar()[1]
                p2 = Polar(l2, angle)+c
            self.p2 = p2

        if selection == 3 or self.shift_pressed:
            p3 = p3 + delta
            if self.control_pressed:
                angle = (p3-c).polar()[1]
                p3 = Polar(l3, angle)+c
            self.p3 = p3
            
        self.recompute()

    def SetData(self, data, version=None):
        undo = self.SetData, self.GetData()
        self.p1 = Point(data[0:2])
        self.p2 = Point(data[2:4])
        self.p3 = Point(data[4:6])
        return undo

    def GetData(self):
        return list(self.p1)+list(self.p2)+list(self.p3)

def register():
    return Circle3
