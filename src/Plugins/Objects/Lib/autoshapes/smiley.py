
import Sketch
from Sketch import Point, SingularMatrix, Scale, Translation
from Sketch.Graphics import handle
from autoshapelib import AutoshapeBase

class Smiley(AutoshapeBase):

    h = -5

    def GetObjectHandle(self, *args):
        return []

    def GetHandles(self):
        return [handle.MakeNodeHandle(self.trafo(Point(15, 5+self.h)))]
                
    def recompute(self):
        path = Sketch.CreatePath()
        newpaths = [path]
        h = self.h
        path.AppendLine((5,5))
        path.AppendBezier((7, 5+h/2.), (12, 5+h), (15,5+h))
        path.AppendBezier((18,5+h), (22, 5+h/2), (25, 5))
        path.Transform(self.trafo)
        if self.objects:
            self.objects[1].SetPaths(tuple(newpaths))            
        else:
            skull = Sketch.Ellipse(Scale(22))
            skull.Transform(Translation(15, 16))
            mouth = Sketch.PolyBezier(tuple(newpaths))
            r_eye = Sketch.Ellipse(Scale(3))
            l_eye = Sketch.Ellipse(Scale(3))
            l_eye.Transform(Translation(7, 21))
            r_eye.Transform(Translation(22, 21))
            self.set_objects([skull, mouth, r_eye, l_eye])
            
    def DragHandle(self, pa, pb, selection):
        try:
            inverse = self.trafo.inverse()
            pa, pb = map(inverse, (pa, pb))
            h = self.h + (pb-pa)[1]
            h = min(6, h)
            h = max(-6, h)
            self.h = h
            self.recompute()
        except SingularMatrix:
            pass

    def SetData(self, data, version=None):
        self.h = data

    def GetData(self):
        return self.h

def register():
    return Smiley
