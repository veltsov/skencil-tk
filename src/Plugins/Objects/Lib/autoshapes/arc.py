import Sketch
from Sketch import _, Point, Polar, Scale, Ellipse, SingularMatrix
from Sketch.Graphics import handle
from autoshapelib import AutoshapeBase
from math import sqrt

class Arc(AutoshapeBase):

    p1 = Point(10,10)
    p2 = Point(0,0)
    p3 = Point(10,-10)
    
    help_text = _("""
Arc
~~~

An arc drawn through three control points

Keys:
    none

Modifier:
    none
    """)
    
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
        p1, p2, p3 = self.p1, self.p2, self.p3
        center, radius = self.Calc()
        alpha = (p1-center).polar()[1]
        beta = (p3-center).polar()[1]

        a = p1-p2
        b = p2-p3
        # XXX I don not understand why, but this is necessary:
        if a.x*b.y-a.y*b.x < 0:
            alpha, beta = beta, alpha
        
        obj = Ellipse(Scale(radius), start_angle=alpha, end_angle=beta,
                      arc_type=0)
        obj.Translate(center)
        obj.Transform(self.trafo)
        if self.objects:
            self.objects[0].set_transformation(obj.trafo)
            self.objects[0].SetAngles(alpha, beta)
        else:
            self.set_objects([obj])
            
    def DragHandle(self, pa, pb, selection):
        try:
            inverse = self.trafo.inverse()
        except SingulareMatrix:
            return
        pa, pb = map(inverse, (pa, pb))
        delta = pb-pa
        
        if selection == 1:
            self.p1 = self.p1 + delta
        elif selection == 2:
            self.p2 = self.p2 + delta
        elif selection == 3:
            self.p3 = self.p3 + delta
            
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
    return Arc
