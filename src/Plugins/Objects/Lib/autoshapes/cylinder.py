###Sketch Config
#type = PluginCompound
#class_name = 'Cylinder'
#menu_text = 'Cylinder'
###End

import Sketch
from Sketch import Point, SingularMatrix
from Sketch.Graphics import handle
from autoshapelib import AutoshapeBase

width = 50
class Cylinder(AutoshapeBase):
    h = 5

    def GetHandles(self):
        p = Point(width/2., width-self.h)
        return [handle.MakeNodeHandle(self.trafo(p))]
                
    def recompute(self):
        path = Sketch.CreatePath()
        top = [path]

        h = self.h
        dh = 0.55197 * h
        d = l = width
        dd = 0.55197 * d /2.
        c = d/2.
        
        path.AppendLine((0, l))
        path.AppendBezier((0, l+dh), (c-dd, l+h), (c, l+h))
        path.AppendBezier((c+dd, h+l), (d, l+dh), (d, l))

        path.AppendBezier((d, l-dh), (c+dd, l-h), (c, l-h))
        path.AppendBezier((c-dd, l-h), (0, l-dh), (0, l))
        path.Transform(self.trafo)
        
        path = Sketch.CreatePath()
        hull = [path]
        
        path.AppendLine((d, l))
        path.AppendLine((d, 0))
        path.AppendBezier((d, -dh), (c+dd, -h), (c, -h))
        path.AppendBezier((c-dd, -h), (0, -dh), (0, 0))
        path.AppendLine((0, l))
        path.AppendBezier((0, l-dh), (c-dd, l-h), (c, l-h))
        path.AppendBezier((c+dd,l-h), (d, l-dh), (d, l))
        path.Transform(self.trafo)
        
        if self.objects:
            self.objects[0].SetPaths(hull)
            self.objects[1].SetPaths(top)
        else:
            obj_hull = Sketch.PolyBezier(tuple(hull))
            obj_hull.SetProperties(line_join=Sketch.const.JoinRound)
            obj_top = Sketch.PolyBezier(tuple(top))
            self.set_objects([obj_hull, obj_top])
            
    def DragHandle(self, pa, pb, selection):
        try:
            inverse = self.trafo.inverse()
            pa, pb = map(inverse, (pa, pb))
            dw, dh = pb-pa
            self.h = max(0, self.h-dh)
            self.recompute()
        except SingularMatrix:
            pass

    def SetData(self, data, version=None):
        self.h = data

    def GetData(self):
        return self.h


def register():
    return Cylinder
