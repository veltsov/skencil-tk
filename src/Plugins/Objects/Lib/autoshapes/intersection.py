
import Sketch
from Sketch import _, Point, Polar, SingularMatrix, const, config, NullUndo
from Sketch.Lib import units
from Sketch.Graphics.handle import Handle, MakeControlHandle, MakePixmapHandle

from autoshapelib import AutoshapeBase

def MakeRoundHandle(p, code = 0):
    pixmap = Sketch.UI.skpixmaps.pixmaps.Center
    offset = Point(0,0) 
    return MakePixmapHandle(p, offset, pixmap)


class Intersection(AutoshapeBase):

    p1 = Point(0,0)
    p2 = Point(50,50)
    p3 = Point(0,50)
    p4 = Point(50,0)

    help_text = _("""
Intersection tool 
~~~~~~~~~~~~~~~~~

The interesection between both lines can be used
as snap point.

Keys:

Modifier:    
    """)

    def Calc(self):
        # calculate the intersection between line p1p2 and p2p3
        p1, p2, p3, p4 = self.p1, self.p2, self.p3, self.p4
        n_a = (p2-p1).normalized()
        n_b = (p4-p3).normalized()
        f_a = p1
        f_b = p3
        
        x = f_b-n_b*(f_b-f_a)*n_b

        # x liegt auf g2 und ist der Fusspunkt zu p1
        
        nn_b = Point(n_b.y, -n_b.x)
        sin_alpha = n_a*nn_b
        if sin_alpha == 0:
            return None

        h = (x-f_a)*nn_b
        s = h/sin_alpha
        c = f_a+s*n_a
        return c
    
    def GetSnapPoints(self):
        p = self.Calc()
        if p is not None:
            return (self.trafo(p),)
        return ()
    
    def GetHandles(self):
        p1, p2, p3, p4 = self.p1, self.p2, self.p3, self.p4

        handles = []
        for p in (p1, p2, p3, p4):
            handles.append(MakeControlHandle(self.trafo(p)))

        p = self.Calc()
        if p is not None:
            handles.append(MakeRoundHandle(self.trafo(p)))
        return handles
                
    def recompute(self):
        p1, p2, p3, p4 = self.p1, self.p2, self.p3, self.p4
        
        new = Sketch.CreatePath()
        newpaths = [new]

        new.AppendLine(p1)
        new.AppendLine(p2)        
        new.Transform(self.trafo)

        new = Sketch.CreatePath()
        newpaths.append(new)
        new.AppendLine(p3)
        new.AppendLine(p4)        
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

        p1, p2, p3, p4 = self.p1, self.p2, self.p3, self.p4
        if selection == 1:
            self.p1 = p1 + delta
        elif selection == 2:
            self.p2 = p2 + delta
        elif selection == 3:
            self.p3 = p3 + delta
        elif selection == 4:
            self.p4 = p4 + delta
        self.recompute()

    def SetData(self, data, version=None):
        self.p1, self.p2, self.p3, self.p4 = map(Point, data)

    def GetData(self):
        return map(tuple, (self.p1, self.p2, self.p3, self.p4))
                        
def register():
    return Intersection
