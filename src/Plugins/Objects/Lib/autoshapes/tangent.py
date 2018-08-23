
import Sketch
from Sketch import _, Point, Polar, SingularMatrix, const, config, NullUndo
from Sketch.Lib import units
from Sketch.Graphics.handle import Handle, MakeControlHandle

from autoshapelib import AutoshapeBase

def MakeRoundHandle(p, code = 0):
    return Handle(const.Handle_FilledCircle, p, code = code)

class TangentTool(AutoshapeBase):

    w1 = 10
    w2 = 10
    p1 = Point(0,0)
    p2 = Point(30,0)

    help_text = _("""
Tangent tool 
~~~~~~~~~~~~

Keys:

Modifier:    
    """)

    def GetSnapPoints(self):
        w1, w2, p1, p2 = self.w1, self.w2, self.p1, self.p2
        xvect = (p2-p1).normalized()
        return map(self.trafo, (self.p1, self.p2, p1-w1*xvect, p2+w2*xvect))
    
    def GetHandles(self):
        w1, w2, p1, p2 = self.w1, self.w2, self.p1, self.p2
        xvect = (p2-p1).normalized()
        handles = []
        for p in (p1, p2):
            handles.append(MakeRoundHandle(self.trafo(p)))

        for p in (p1-w1*xvect, p2+w2*xvect):
            handles.append(MakeControlHandle(self.trafo(p)))        
        return handles
                
    def recompute(self):
        w1, w2, p1, p2 = self.w1, self.w2, self.p1, self.p2

        xvect = (p2-p1).normalized()
        
        new = Sketch.CreatePath()
        newpaths = [new]

        new.AppendLine(p1-w1*xvect)
        new.AppendLine(p2+w2*xvect)        
        new.Transform(self.trafo)
        if self.objects:
            self.objects[0].SetPaths(newpaths)
        else:
            lines = Sketch.PolyBezier(tuple(newpaths))
            self.set_objects([lines])
            
    def DragHandle(self, pa, pb, selection):
        try:
            inverse = self.trafo.inverse()
        except SingularMatrix:
            return

        
        pa, pb = map(inverse, (pa, pb))
        delta = pb-pa

        w1, w2, p1, p2 = self.w1, self.w2, self.p1, self.p2

        xvect = (p2-p1).normalized()
        if selection == 1:
            self.p1 = p1 + delta
        elif selection == 2:
            self.p2 = p2 + delta
        elif selection == 3:
            self.w1 = max(0, w1-delta*xvect)
        elif selection == 4:
            self.w2 = max(0, w2+delta*xvect)
        self.recompute()

    def SetData(self, data, version=None):
        self.w1, self.w2 = data[:2]
        self.p1 = Point(*data[2:4])
        self.p2 = Point(*data[4:6])

    def GetData(self):
        return self.w1, self.w2, self.p1.x, self.p1.y, self.p2.x, self.p2.y

        
def register():
    return TangentTool
