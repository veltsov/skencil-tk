
import Sketch
from Sketch import _, Point, Polar, SingularMatrix, const, config, NullUndo
from Sketch.Lib import units
from Sketch.Graphics.handle import Handle, MakeControlHandle

from autoshapelib import AutoshapeBase

def MakeRoundHandle(p, code = 0):
    return Handle(const.Handle_FilledCircle, p, code = code)

class DivideTool(AutoshapeBase):

    h1 = 5
    h2 = 0
    n = 4
    p1 = Point(0,0)
    p2 = Point(50,0)

    help_text = _("""
Divide tool 
~~~~~~~~~~~

Keys:
    +  increse divisions
    -  decrease divisions

Modifier:    
    """)
    
    def GetHandles(self):
        h1, h2, n, p1, p2 = self.h1, self.h2, self.n, self.p1, self.p2

        p12 = p2-p1
        xvect = p12.normalized()
        yvect = Point(xvect.y, -xvect.x)
        
        handles = []

        
        for p in (p1, p2, p1+1./3*p12-h1*yvect, p1+2./3*p12+h2*yvect):
            handles.append(MakeControlHandle(self.trafo(p)))
        return handles
                
    def recompute(self):
        h1, h2, n, p1, p2 = self.h1, self.h2, self.n, self.p1, self.p2
        
        xvect = (p2-p1).normalized()
        yvect = Point(xvect.y, -xvect.x)
        
        new = Sketch.CreatePath()
        newpaths = [new]

        new.AppendLine(p1)
        new.AppendLine(p2)        
        new.Transform(self.trafo)

        for i in range(0, n+1):
            new = Sketch.CreatePath()
            newpaths.append(new)

            p = p1+(p2-p1)/float(n)*i
            new.AppendLine(p-yvect*h1)
            new.AppendLine(p+yvect*h2)        
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

        h1, h2, n, p1, p2 = self.h1, self.h2, self.n, self.p1, self.p2

        xvect = (p2-p1).normalized()
        yvect = Point(xvect.y, -xvect.x)

        if selection == 1:
            self.p1 = p1 + delta
        elif selection == 2:
            self.p2 = p2 + delta
        elif selection == 3:
            self.h1 = max(0, h1-delta*yvect)
        elif selection == 4:
            self.h2 = max(0, h2+delta*yvect)
        self.recompute()

    def SetData(self, data, version=None):
        self.h1, self.h2, self.n = data[:3]
        self.p1 = Point(*data[3:5])
        self.p2 = Point(*data[5:7])

    def GetData(self):
        return self.h1, self.h2, self.n, self.p1.x, self.p1.y, self.p2.x, \
               self.p2.y

    def SetN(self, n):
        old = self.n
        self.n = n
        self.recompute()
        return self.SetN, old
    
    def KeyHandler(self, key):
        unit_name = config.preferences.default_unit
        pt_per_unit = units.unit_dict[unit_name]
        f = float(pt_per_unit)
        
        if key == '+':
            return self.SetN(self.n+1)
        elif key == '-':
            return self.SetN(max(1, self.n-1))
        
def register():
    return DivideTool
