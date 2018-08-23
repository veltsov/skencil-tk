
import Sketch
from Sketch import _, SingularMatrix
from Sketch.Graphics import handle
from autoshapelib import AutoshapeBase

class DoubleArrow(AutoshapeBase):
    h1 = 10
    h2 = 10
    w1 = 15
    w2 = 20
    def GetHandles(self):
        h1, h2, w1, w2 = self.GetData()
        handles = []
        
        for p in ((-w1, 0),
                  (0,-h2-h1),
                  (w2/2.,-self.h1),
                  (w2,0)):
            handles.append(handle.MakeNodeHandle(self.trafo(p)))
        return handles
                
    def DragHandle(self, pa, pb, selection):
        try:
            inverse = self.trafo.inverse()
            pa, pb = map(inverse, (pa, pb))
            dw, dh = pb-pa            

            h1, h2, w1, w2 = self.GetData()
            
            if selection == 1:
                self.w1 = max(0, w1-dw)
            elif selection == 2:
                self.h2 = max(0, h2-dh)
            elif selection == 3:
                self.h1 = max(0, h1-dh)
            elif selection == 4:
                self.w2 = max(0, w2+dw)
            
            self.recompute()
        except SingularMatrix:
            pass
        
    def recompute(self):
        h1, h2, w1, w2 = self.GetData()
        new = Sketch.CreatePath()
        newpaths = [new]
        for p in ((-w1,0), (0,-h2-h1),
                  (0,-h1), (w2,-h1),
                  (w2, -h2-h1), (w2+w1,0),
                  (w2, h2+h1), (w2, h1),
                  (0,h1), 
                  (0, h2+h1), (-w1,0)):
            new.AppendLine(p)
                  
        new.Transform(self.trafo)
        if self.objects:
            self.objects[0].SetPaths(newpaths)
        else:
            obj = Sketch.PolyBezier(tuple(newpaths))
            self.set_objects([obj])         

    def SetData(self, data, version=None):
        self.h1, self.h2, self.w1, self.w2 = data

    def GetData(self):
        return (self.h1, self.h2, self.w1, self.w2)

def register():
    return DoubleArrow
