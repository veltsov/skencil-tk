import Sketch
from Sketch import _, Point, Scale, Ellipse, SingularMatrix
from Sketch.Graphics import handle
from autoshapelib import AutoshapeBase

class Circle1(AutoshapeBase):

    p1 = Point(-20,0)
    p2 = Point(20,0)

    help_text = _("""
Circle1
~~~~~~~
A circle which is defined by two tangent points.
The center is in the middle of both points.

Keys:
    none

Modifier:
    shift   translate circle
    """)
    
    def GetSnapPoints(self):
        p1, p2 = self.p1, self.p2
        return map(self.trafo, (p1, p2, 0.5*(p1+p2)))
    
    def GetHandles(self):
        handles = []
        for p in (self.p1, self.p2):
            handles.append(handle.MakeNodeHandle(self.trafo(p)))
        return handles
                
    def recompute(self):
        p1, p2 = self.p1, self.p2
        center = 0.5*(p1+p2)
        radius = 0.5*(p2-p1).polar()[0]
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
            pa, pb = map(inverse, (pa, pb))
            delta = pb-pa

            if selection == 1 or self.shift_pressed:
                self.p1 = self.p1 + delta
            if selection == 2 or self.shift_pressed:
                self.p2 = self.p2 + delta
                
            self.recompute()
        except SingularMatrix:
            pass

    def SetData(self, data, version=None):
        undo = self.SetData, self.GetData()
        self.p1, self.p2 = map(Point, data)
        return undo

    def GetData(self):
        return map(list, (self.p1, self.p2))

def register():
    return Circle1
