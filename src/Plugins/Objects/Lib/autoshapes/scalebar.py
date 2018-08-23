
import Sketch
from Sketch import _, Point, SingularMatrix
from Sketch.Graphics import handle
from Sketch.UI.command import AddCmd
from autoshapelib import AutoshapeBase

# Unitvectors
ux = Point(1,0)
uy = Point(0,1)

# f1: width of bar
# f2: height of small lines
f1 = 0.4
f2 = 0.7

class Scalebar(AutoshapeBase):

    p1 = Point(0,0)
    p2 = Point(50,0)
    h = 20
    n = 5
    
    help_text = _("""
ScaleBar
~~~~~~~~

Keys:
    +       increase number of intervals
    -       decrease number of intervals

Modifier:
    none
    """)
    
    def GetHandles(self):
        p1, p2, h, n = self.p1, self.p2, self.h, self.n
        handles = []
        y = h*uy
        for p in (p1, p2, y+p1, y+p2):
            handles.append(handle.MakeNodeHandle(self.trafo(p)))

        if n > 0:
            x = (p2-p1).x / float(n) *ux
            p = p1 + f2*y + x

            for i in range(n-1):
                handles.append(handle.MakeNodeHandle(self.trafo(p)))
                p = p + x 
        return handles
                
    def recompute(self):
        new = Sketch.CreatePath()
        newpaths = [new]
        p1, p2, h, n = self.p1, self.p2, self.h, self.n

        y1 = f1 *h*uy
        y2 = f2 *h*uy
        y3 = h*uy
        x = (p2-p1)/ float(n) 
        
        new.AppendLine(p1)
        new.AppendLine(p2)
        new.AppendLine(p2+y3)
        
        p = p2
        new.AppendLine(p+y1)
        for i in range(n):
            p = p-x
            new.AppendLine(p+y1)
            new.AppendLine(p+y2)
            new.AppendLine(p+y1)
        
        new.AppendLine(p1+y1)
        new.AppendLine(p1+y3)
        new.AppendLine(p1)
        
        new.Transform(self.trafo)
        if self.objects:
            self.objects[0].SetPaths(newpaths)
        else:
            obj = Sketch.PolyBezier(tuple(newpaths))
            self.set_objects([obj])
            
    def DragHandle(self, pa, pb, selection):
        try:
            inverse = self.trafo.inverse()
            pa, pb = map(inverse, (pa, pb))
            delta = pb-pa
                         
            p1, p2, h, n = self.p1, self.p2, self.h, self.n

            if selection == 1:
                p1 = p1 + delta
                p2 = p2 + delta.y*uy
            elif selection == 2:
                p1 = p1 + delta.y*uy
                p2 = p2 + delta
                
            elif selection in (3, 4):
                h = h + delta.y

            else:
                w = float((p2-p1).x)
                if w>0:
                    dn = int(n*delta.x/w)
                    n = n+dn
            self.p1, self.p2, self.h, self.n = p1, p2, h, n 
            self.recompute()
        except SingularMatrix:
            pass

    def SetData(self, data, version=None):
        self.p1, self.p2 = map(Point, data[:2])
        self.h, self.n = data[2:]

    def ChangeN(self, delta):
        n = self.n
        if n+delta > 0:
            n = n+delta
        return self.SetParameters({'n':n})

    def KeyHandler(self, key):        
        if key == '+':
            return self.ChangeN(1)
        elif key == '-':
            return self.ChangeN(-1)

    def GetData(self):
        return (list(self.p1), list(self.p2), self.h, self.n)

    def Info(self):
        return _("Scalebar with %s intervals") % self.n

    
def register():
    return Scalebar
