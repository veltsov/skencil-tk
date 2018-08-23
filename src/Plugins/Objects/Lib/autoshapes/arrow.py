
import Sketch
from Sketch import _, SingularMatrix
from Sketch.Graphics import handle
from autoshapelib import AutoshapeBase

class Arrow(AutoshapeBase):
    h1 = 10
    h2 = 20
    w1 = 20
    w2 = 60
    def GetHandles(self):
        handles = []
        w = (self.w2+self.w1)/2.
        for p in ((self.w1,-self.h2),
                  (w,-self.h1),
                  (w,self.h1),
                  (self.w1,self.h2)):
            handles.append(handle.MakeNodeHandle(self.trafo(p)))
        return handles
                
    def DragHandle(self, pa, pb, selection):
        try:
            inverse = self.trafo.inverse()
            pa, pb = map(inverse, (pa, pb))
            dw, dh = pb-pa            
            
            if selection > 2:
                selection = 5-selection
                dh = -dh

            if selection == 1:
                self.w1 = self.w1+dw
                if self.h2 > 0:
                    f = 1.-dh / self.h2
                    self.h1 = f*self.h1
                    self.h2 = f * self.h2
                else:
                    self.h1 = dh
                    self.h2 = 2*dh
            elif selection == 2:
                self.h1 = self.h1-dh

            self.h1 = max(0, self.h1)
            self.h2 = max(0, self.h2)
            self.w1 = max(0, self.w1)
            self.w2 = max(0, self.w2)
            self.h1 = min(self.h1,self.h2)
            self.w1 = min(self.w1, self.w2)
            
            self.recompute()
        except SingularMatrix:
            pass
        
    def recompute(self):
        new = Sketch.CreatePath()
        newpaths = [new]
        for p in ((0,0), (self.w1,-self.h2),
                  (self.w1,-self.h1), (self.w2,-self.h1),
                  (self.w2,self.h1), (self.w1,self.h1),
                  (self.w1, self.h2), (0,0)):
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

    def Info(self):
        return _("Arrow") 


def register():
    return Arrow
