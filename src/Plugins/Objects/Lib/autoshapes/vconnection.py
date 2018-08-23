import Sketch
from Sketch import _, const, Point, SingularMatrix
from Sketch.Graphics.handle import MakeNodeHandle, Handle
from autoshapelib import StickyObject

# Unitvectors
ux = Point(1,0)
uy = Point(0,1)

def MakeRoundHandle(p, code = 0):
    return Handle(const.Handle_FilledCircle, p, code = code)

class ConnectionVert(StickyObject):

    y = 10
    p1 = Point(0,0)
    p2 = Point(50,20)

    help_text = _("""
Vertical Connection
~~~~~~~~~~~~~~~~~~~
""") + StickyObject._connection_descr
    
    def __init__(self, *args, **kw):
        apply(StickyObject.__init__, (self,)+args, kw)
        
    def GetSnapPoints(self):
        return map(self.trafo, (self.p1, self.p2))

    def GetHandles(self):
        handles = []
        p1, p2, y = self.p1, self.p2, self.y
        trafo = self.trafo
        for j, p in ((0,p1), (1,p2)):
            handles.append(MakeRoundHandle(trafo(p)))
            
        p = Point(0.5*(p1.x+p2.x), y)
        handles.append(MakeNodeHandle(trafo(p)))
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
        p1, p2, y = self.p1, self.p2, self.y
        
        new.AppendLine(p1)
        new.AppendLine((p1.x, y))
        new.AppendLine((p2.x, y))
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
                         
        p1, p2, y = self.p1, self.p2, self.y
        
        if selection == 1:
            self.p1 = p1 + delta
        elif selection == 2:
            self.p2 = p2 + delta
        elif selection == 3:
            self.y = y + delta.y

        self.recompute()        

    def SetData(self, data, version=None):
        undo = self.SetData, self.GetData()
        self.p1, self.p2 = map(Point, data[:2])
        self.y = data[2]
        return undo

    def GetData(self):
        return (self.p1.x, self.p1.y), (self.p2.x, self.p2.y), self.y
    

def register():
    return ConnectionVert
