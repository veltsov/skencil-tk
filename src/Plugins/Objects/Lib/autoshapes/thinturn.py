import Sketch
from Sketch import _, Point, SingularMatrix, Scale, Translation
from Sketch.Graphics import handle
from autoshapelib import AutoshapeBase

class ThinTurn(AutoshapeBase):

    back = 0
    l1 = 10
    l2 = 50
    l3 = 12
    d1 = 10
    d2 = 5
    d3 = 13
    help_text = _("""
Thin Turn
~~~~~~~~~

Keys:
    +       toggle to front /to back
    -       same

Modifier:
    none
    """)
     
    def GetHandles(self):
        handles = []
        back, l1, l2, l3, d1, d2, d3 = self.back, self.l1, self.l2, self.l3, \
                                       self.d1, self.d2, self.d3
        for p in ((-l1,0), (0, d1+d2), (-l3, -2*d3), (l2, -d3), \
                  (l2/2., d1)):
            handles.append(handle.MakeNodeHandle(self.trafo(p)))
        return handles
                
    def DragHandle(self, pa, pb, selection):
        try:
            inverse = self.trafo.inverse()
        except SingularMatrix:
            return

        pa, pb = map(inverse, (pa, pb))
        dw, dh = pb-pa            

        back, l1, l2, l3, d1, d2, d3 = self.back, self.l1, self.l2, self.l3, \
                                       self.d1, self.d2, self.d3
        if selection == 1:
            self.l1 = max(0, l1-dw)
        elif selection == 2:
            self.d2 = max(0, d2+dh)
        elif selection == 5:
            self.d1 = max(0, d1+dh)
        elif selection == 4:
            self.l2 = max(0, l2+dw)
        elif selection == 3:
            self.l3 = l3-dw
            self.d3 = max(0, d3-dh/2.)
        self.recompute()
        
    def recompute(self):
        back, l1, l2, l3, d1, d2, d3 = self.back, self.l1, self.l2, self.l3, \
                                       self.d1, self.d2, self.d3
        
        new = Sketch.CreatePath()
        newpaths1 = [new]

        #draw the arrow head
        for p in ((0,-d1), (0, -d1-d2), (-l1,0), (0, d1+d2), (0, d1)):
            new.AppendLine(Point(p))

        # the upper part of the arrow bar
        k = 1.2
        new.AppendBezier(Point(l2,d1), Point(l2, d1-d3/k), Point(l2,d1-d3))
        new.AppendLine(Point(l2, -d1-d3))
        new.AppendBezier(Point(l2,-d1-d3/k), Point(l2,-d1), Point(0,-d1))
        
        # the lower part of the arrow bar
        new = Sketch.CreatePath()
        newpaths2 = [new]        
        new.AppendLine(Point(-l3,-d1))
        new.AppendLine(Point(-l3,d1))
        new.AppendBezier(Point(l2,d1), Point(l2, d1-d3/3.), Point(l2,d1-d3))
        new.AppendLine(Point(l2, -d1-d3))
        new.AppendBezier(Point(l2,-d1-d3/3.), Point(l2,-d1), Point(-l3,-d1))

        new.Transform(Scale(1,-1))
        new.Transform(Translation(0, -2*d3))

        if back:
            newpaths2, newpaths1 = newpaths1, newpaths2

        for path in newpaths1+newpaths2:
            path.Transform(self.trafo)
        if self.objects:
            self.objects[0].SetPaths(newpaths1)
            self.objects[1].SetPaths(newpaths2)
        else:
            obj1 = Sketch.PolyBezier(tuple(newpaths1))
            obj2 = Sketch.PolyBezier(tuple(newpaths2))
            self.set_objects([obj1, obj2])         

    def ToggleDir(self):
        return self.SetParameters({'back' : int(not self.back)})

    def KeyHandler(self, key):
        if key in ('+', '-'):
            return self.ToggleDir()
                
    def SetData(self, data, version=None):
        self.back, self.l1, self.l2, self.l3, self.d1, self.d2, self.d3 = data

    def GetData(self):
        return self.back, self.l1, self.l2, self.l3, self.d1, self.d2, self.d3

def register():
    return ThinTurn
