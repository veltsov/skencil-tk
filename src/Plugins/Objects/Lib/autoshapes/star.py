import Sketch
from Sketch import _, Point, SingularMatrix, RegisterCommands, NullUndo, \
     Rotation
from Sketch.Graphics import handle

from autoshapelib import AutoshapeBase
from math import pi, sin, cos


class Star(AutoshapeBase):

    r1 = 20
    r2 = 30
    n = 6

    help_text = _("""
Star
~~~~

Keys:
    +       increase number of arms
    -       decrease number of arms

Modifier:
    none
    """)
    
    def GetHandles(self):
        r1, r2, n = self.r1, self.r2, self.n

        handles = []

        alpha = 2*pi / n
        for i in range(n):
            beta = i * alpha 
            p = r1*cos(beta), r1*sin(beta)
            handles.append(handle.MakeNodeHandle(self.trafo(p)))

        for i in range(n):
            beta = (i+0.5) * alpha 
            p = r2*cos(beta), r2*sin(beta)            
            handles.append(handle.MakeControlHandle(self.trafo(p)))

        return handles
                
    def recompute(self):
        new = Sketch.CreatePath()
        newpaths = [new]

        r1, r2, n = self.r1, self.r2, self.n
        
        alpha = 2*pi / n
        for i in range(n):
            beta = i * alpha 
            p = r1*cos(beta), r1*sin(beta)
            new.AppendLine(p)
            beta = (i+0.5) * alpha
            p = r2*cos(beta), r2*sin(beta)
            new.AppendLine(p)

        new.AppendLine((r1,0))
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
        r1, r2, n = self.r1, self.r2, self.n            
        alpha = 2*pi / n

        ra, beta = pa.polar()
        rot = Rotation(-beta)
        rb, gamma = rot(pb).polar()
    
        if selection <= n:
            if pa*pb < 0:
                self.r1 = 0
            else:
                self.r1 = min(r2, r1+rb-ra)
        else:
            n = n+int(2* gamma / alpha)    
            if n >= 1:
                self.n = n  

        self.recompute()

    def SetData(self, data, version=None):
        self.r1, self.r2, self.n = data

    def GetData(self):
        return (self.r1, self.r2, self.n)

    def Info(self):
        return _("Star with %s arms") % self.n

    def GetN(self):
        return self.n
    
    def SetN(self, n):
        return self.SetParameters({'n':max(2, n)})

    def ChangeN(self, delta):
        return self.SetN(self.GetN()+delta)

    def KeyHandler(self, key):
        if key == '+':
            return self.ChangeN(1)
        elif key == '-':
            return self.ChangeN(-1)


def register():
    return Star
