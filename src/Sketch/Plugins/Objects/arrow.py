###Sketch Config
#type = PluginCompound
#class_name = 'Arrow'
#menu_text = 'Arrow'
###End

import Sketch
from Sketch import SingularMatrix
from Sketch.Graphics import handle

from Sketch import TrafoPlugin, _
from Sketch.Graphics.base import Editor
from Sketch.Graphics import handle

class GenericEditor(Editor):

    commands = []
    selection = 0

    def __init__(self, object):
        Editor.__init__(self, object)
        object.set_editor(self)
        self.transient_object = object.Duplicate()

    def Destroy(self):
        self.object.unset_editor(self)

    def ButtonDown(self, p, button, state):
        Editor.DragStart(self, p)
        self.transient_object = self.object.Duplicate()

    def ButtonUp(self, p, button, state):
        Editor.DragStop(self, p)
        return self.object.drag_handle(self.drag_start, p, self.selection)

    def MouseMove(self, p, state):
        Editor.MouseMove(self, p, state)
        self.transient_object = self.object.Duplicate()
        self.transient_object.drag_handle(self.drag_start, p, self.selection)

    def GetHandles(self):
        return self.object.GetHandles()

    def SelectPoint(self, p, rect, device, mode):
        return 0

    def SelectHandle(self, handle, mode):
        self.selection = handle.index+1

    def DrawDragged(self, device, partially):
        self.transient_object.DrawShape(device)

class AutoShape(TrafoPlugin):
    has_edit_mode = 1
    is_Group      = 1
    has_line      = 1
    has_fill      = 1

    Ungroup = TrafoPlugin.GetObjects
    def __init__(self, data = None, trafo = None, duplicate = None, \
                 loading = 0):
        TrafoPlugin.__init__(self, trafo = trafo, duplicate = duplicate)

        if duplicate:
            data = duplicate.GetData()
            self.SetData(data)

        if loading:
            self.SetData(data)

        else:
            self.recompute()
                    
    editor = None
    def set_editor(self, editor):
        self.editor = editor
        
    def unset_editor(self, editor):
        if self.editor is editor:
            self.editor = None

    def Editor(self):
        return GenericEditor(self)

    def Info(self):
        return _("Autoshape `%s'") % self.class_name

    def SaveToFile(self, file):
        data = self.GetData()
        TrafoPlugin.SaveToFile(self, file, data,
                               self.trafo.coeff())

    def drag_handle(self, pa, pb, selection):
        data = self.GetData()
        self.DragHandle(pa, pb, selection)
        return self.set_data, data

    def set_data(self, data):
        undo = self.set_data, self.GetData()
        self.SetData(data)
        self.recompute()
        return undo

    # The following methods are stubs working for a single-object compounds
    # Otherwise they have to be reimplemented
    def Properties(self):
        return self.objects[0].Properties()

    # The following methods need to be implemented by Autoshapes
    def GetData(self):
        return None

    def SetData(self, data):
        pass

    def DragHandle(self, pa, pb, selection):
        pass


class Arrow(AutoShape):
    class_name = 'Arrow'
    is_curve      = 1

    h1 = 5
    h2 = 10
    w1 = 10
    w2 = 30
    def GetHandles(self):
        handles = []
        w = (self.w2+self.w1)/2.
        for p in ((self.w1,-self.h2),
                  (w,-self.h1),
                  (w,self.h1),
                  (self.w1,self.h2)):
            handles.append(handle.MakeNodeHandle(self.trafo(p)))
        return handles
                
    def DragHandle(self, pa, pb, selection):
        try:
            inverse = self.trafo.inverse()
            pa, pb = map(inverse, (pa, pb))
            dw, dh = pb-pa            
            
            if selection > 2:
                selection = 5-selection
                dh = -dh

            if selection == 1:
                self.w1 = self.w1+dw
                if self.h2 > 0:
                    f = 1.-dh / self.h2
                    self.h1 = f*self.h1
                    self.h2 = f * self.h2
                else:
                    self.h1 = dh
                    self.h2 = 2*dh
            elif selection == 2:
                self.h1 = self.h1-dh

            self.h1 = max(0, self.h1)
            self.h2 = max(0, self.h2)
            self.w1 = max(0, self.w1)
            self.w2 = max(0, self.w2)
            self.h1 = min(self.h1,self.h2)
            self.w1 = min(self.w1, self.w2)
            
            self.recompute()
        except SingularMatrix:
            pass
        
    def recompute(self):
        new = Sketch.CreatePath()
        newpaths = [new]
        for p in ((0,0), (self.w1,-self.h2),
                  (self.w1,-self.h1), (self.w2,-self.h1),
                  (self.w2,self.h1), (self.w1,self.h1),
                  (self.w1, self.h2), (0,0)):
            new.AppendLine(p)
                  
        new.Transform(self.trafo)
        if self.objects:
            self.objects[0].SetPaths(newpaths)
        else:
            obj = Sketch.PolyBezier(tuple(newpaths))
            self.set_objects([obj])         

    def SetData(self, data):
        self.h1, self.h2, self.w1, self.w2 = data

    def GetData(self):
        return (self.h1, self.h2, self.w1, self.w2)

    def Info(self):
        return _("Arrow") 

    def AsBezier(self):
        return self.objects[0].AsBezier()

    def Paths(self):
        return self.objects[0].Paths()

