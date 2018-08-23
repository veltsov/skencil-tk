import Sketch
from Sketch import _, const, Point, SingularMatrix
from Sketch.Graphics.handle import MakeNodeHandle, Handle
from autoshapelib import StickyObject, VERSION

# Unitvectors
ux = Point(1,0)
uy = Point(0,1)

def MakeRoundHandle(p, code = 0):
    return Handle(const.Handle_FilledCircle, p, code = code)

class ConnectionDiag(StickyObject):

    p1 = Point(0,0)
    p2 = Point(50, 20)

    help_text = _("""
Diagonal Connection
~~~~~~~~~~~~~~~~~~~
""") + StickyObject._connection_descr

    
    def __init__(self, *args, **kw):
        apply(StickyObject.__init__, (self,)+args, kw)

    def GetSnapPoints(self):
        return map(self.trafo, (self.p1, self.p2))
    
    def GetHandles(self):
        handles = []
        p1, p2 = self.p1, self.p2
        for j, p in ((0,p1), (1,p2)):
            tp = self.trafo(p)
            handles.append(MakeRoundHandle(tp))            
        return handles


    def GetStickyPoints(self):
        return map(self.trafo, (self.p1, self.p2))
    
    def bond_changed(self, i, p):
        p = self.trafo.inverse()(p)
        if i == 0:
            self.p1 = p
        elif i == 1:
            self.p2 = p
        else:
            raise "internal error"
        
    def recompute(self):
        new = Sketch.CreatePath()
        newpaths = [new]
        p1, p2 = self.p1, self.p2

        new.AppendLine(p1)
        new.AppendLine(p2)
        
        new.Transform(self.trafo)
        if self.objects:
            self.objects[0].SetPaths(newpaths)
        else:
            obj = Sketch.PolyBezier(tuple(newpaths))
            self.set_objects([obj])
                    
    def DragHandle(self, pa, pb, selection):
        try:
            inverse = self.trafo.inverse()
        except SingularMatrix:
            return 

        pa, pb = map(inverse, (pa, pb))
        delta = pb-pa

        p1, p2 = self.p1, self.p2

        if selection == 1:
            self.p1 = p1 + delta
        elif selection == 2:
            self.p2 = p2 + delta

        self.recompute()

    def SetData(self, data, version=None):
        undo = self.SetData, self.GetData()
        
        self.p1, self.p2 = map(Point, data[:2])        
        return undo

    def GetData(self):
        return (self.p1.x, self.p1.y), (self.p2.x, self.p2.y)

def register():
    return ConnectionDiag
