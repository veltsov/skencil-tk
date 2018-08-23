
import Sketch
from Sketch import _, Point, SingularMatrix, Scale, Translation
from Sketch.Graphics import handle
from autoshapelib import AutoshapeBase

class ThinHalfTurn(AutoshapeBase):
    
    l1 = 10
    l2 = 50
    d1 = 10
    d2 = 5
    d3 = 30
    
    def GetHandles(self):
        handles = []
        l1, l2, d1, d2, d3 = self.l1, self.l2, self.d1, self.d2, self.d3
        for p in ((-l1,0), (0, d1+d2), (l2/2., d1), (l2, -d3)):
            handles.append(handle.MakeNodeHandle(self.trafo(p)))
        return handles
                
    def DragHandle(self, pa, pb, selection):
        try:
            inverse = self.trafo.inverse()
        except SingularMatrix:
            return

        pa, pb = map(inverse, (pa, pb))
        dw, dh = pb-pa            


        l1, l2, d1, d2, d3 = self.l1, self.l2, self.d1, self.d2, self.d3
        if selection == 1:
            self.l1 = max(0, l1-dw)
        elif selection == 2:
            self.d2 = max(0, d2+dh)
        elif selection == 3:
            self.d1 = max(0, d1+dh)
        elif selection == 4:
            self.l2 = max(0, l2+dw)
            self.d3 = d3-dh

        self.recompute()
        
    def recompute(self):
        l1, l2, d1, d2, d3 = self.l1, self.l2, self.d1, self.d2, self.d3
        
        new = Sketch.CreatePath()
        newpaths = [new]

        #draw the arrow head
        for p in ((0,-d1), (0, -d1-d2), (-l1,0), (0, d1+d2), (0, d1)):
            new.AppendLine(Point(p))

        # the rounded part
        k = 1.2
        new.AppendBezier(Point(l2,d1), Point(l2, d1-d3/k), Point(l2,d1-d3))
        new.AppendLine(Point(l2, -d1-d3))
        new.AppendBezier(Point(l2,-d1-d3/k), Point(l2,-d1), Point(0,-d1))
        

        for path in newpaths:
            path.Transform(self.trafo)
        if self.objects:
            self.objects[0].SetPaths(newpaths)
        else:
            obj = Sketch.PolyBezier(tuple(newpaths))
            self.set_objects([obj])         

    def SetData(self, data, version=None):
        self.l1, self.l2, self.d1, self.d2, self.d3 = data

    def GetData(self):
        return self.l1, self.l2, self.d1, self.d2, self.d3

    def Info(self):
        return _("ThinHalfTurn") 

def register():
    return ThinHalfTurn
