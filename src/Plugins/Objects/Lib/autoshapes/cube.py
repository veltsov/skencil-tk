
import Sketch
from Sketch import Point, SingularMatrix
from Sketch.Graphics import handle
from autoshapelib import AutoshapeBase

size = 50
class Cube3D(AutoshapeBase):

    p = Point(10,10)
    depth = 0
    
    def GetHandles(self):
        w, h = self.p
        depth = self.depth
        handles = []
        for xy in ((w+depth, h+size), (w+size, h+size), (w+size, h+depth)):
            p = self.trafo(Point(xy))
            handles.append(handle.MakeNodeHandle(p))
        return handles
                
    def recompute(self):
        w, h = self.p
        depth = self.depth
        
        path = Sketch.CreatePath()
        newpaths = [path]
        path.AppendLine((size, 0))
        path.AppendLine((size+w, h+depth))
        path.AppendLine((size+w, h+size))
        path.AppendLine((size, size))
        
        path = Sketch.CreatePath()
        newpaths.append(path)
        path.AppendLine((size, size))
        path.AppendLine((size+w, h+size))
        path.AppendLine((w+depth, h+size))
        path.AppendLine((0, size))

        path = Sketch.CreatePath()
        newpaths.append(path)
        path.AppendLine((0,0))
        path.AppendLine((0, size))
        path.AppendLine((size, size))
        path.AppendLine((size, 0))
        path.AppendLine((0,0))

        for path in newpaths:
            path.Transform(self.trafo)
        if self.objects:
            self.objects[0].SetPaths(newpaths)
        else:
            obj = Sketch.PolyBezier(tuple(newpaths))
            obj.SetProperties(line_cap=Sketch.const.CapButt)
            obj.SetProperties(line_join=Sketch.const.JoinRound)
            self.set_objects([obj])
            
    def DragHandle(self, pa, pb, selection):
        try:
            inverse = self.trafo.inverse()
        except  SingularMatrix:
            return
        
        pa, pb = map(inverse, (pa, pb))
        if selection == 1:
            depth = self.depth            
            self.depth = min(size, max(0, depth+(pb-pa)[0]))
        elif selection == 2:
            w, h = self.p + pb-pa
            if w<0: w = 0
            if h<0: h = 0                
            self.p = Point(w,h)
        else:
            depth = self.depth
            self.depth = min(size, max(0, depth+(pb-pa)[1]))
        self.recompute()
        

    def SetData(self, data, version=None):
        self.p = Point(data[:2])
        self.depth = data[-1]

    def GetData(self):
        return list(self.p)+[self.depth]

def register():
    return Cube3D
