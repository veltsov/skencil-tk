import Sketch
from Sketch import _, Point, Polar, Scale, Ellipse, SingularMatrix
from Sketch.Graphics import handle
from autoshapelib import AutoshapeBase

class Circle2(AutoshapeBase):

    p1 = Point(0,0)
    p2 = Point(20,0)

    help_text = _("""
Circle2
~~~~~~~
A circle which is defined by two control
points on its line point on its line

Keys:
    none

Modifier:
    shift     translate circle
    control   fix radius when p2 is moved 
    """)

    def LayoutPoint(self):
        return self.trafo(self.p1)
    
    def GetSnapPoints(self):
        return map(self.trafo, (self.p1, self.p2))

    def GetHandles(self):
        handles = []
        for p in (self.p1, self.p2):
            handles.append(handle.MakeNodeHandle(self.trafo(p)))
        return handles
                
    def recompute(self):
        p1, p2 = self.p1, self.p2
        center = p1
        radius = (p2-p1).polar()[0]
        obj = Ellipse(Scale(radius))
        obj.Translate(center)
        obj.Transform(self.trafo)
        if self.objects:
            self.objects[0].set_transformation(obj.trafo)
        else:
            self.set_objects([obj])
                        
    def DragHandle(self, pa, pb, selection):
        p1, p2 = self.p1, self.p2
        try:
            inverse = self.trafo.inverse()
            pa, pb = map(inverse, (pa, pb))
            delta = pb-pa

            if selection == 1 or self.shift_pressed:
                self.p1 = p1 + delta
            if selection == 2 or self.shift_pressed:
                if self.control_pressed:
                    l = (p2-p1).polar()[0]
                    p2 = p2 + delta
                    angle = (p2-p1).polar()[1]
                    self.p2 = Polar(l, angle)+p1
                else:
                    self.p2 = p2 + delta

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
    return Circle2
