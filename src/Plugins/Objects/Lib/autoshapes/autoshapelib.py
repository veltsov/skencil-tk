import Sketch
from Sketch import _, Trafo, Translation, TrafoPlugin, const, Rotation, \
     RegisterCommands, NullUndo, PolyBezier
from Sketch.UI.command import AddCmd
from Sketch.Graphics.base import Editor
from Sketch.UI.sketchdlg import SKModal
from ScrolledText import ScrolledText
import Tkinter

#############
VERSION = 0.2
#############

_debug  = 0

def note(msg, *args):
    if _debug:
        if len(args):
            print msg % map(str, args)
        else:
            print msg
        
def report_error(title, message):
    app = Sketch.main.application
    app.MessageBox(title = title,
                   message = message,
                   icon = 'warning')

def Loader(name):
    note("loading %s ", name)
    try:
        module = __import__(name, globals(), locals(), [])
    except Exception, e:
        report_error(_('Warning'), _('Failed to load autoshape \'%s\': %s') %
                     (name, e))
        return UnknownShape
    return module.register()

# This is a dummy class which is replaced in __init__ by the specific
# Autoshape's class. Would be equivalent to use a generating function. 

class Autoshape(TrafoPlugin):
    commands = []
    class_name = 'Autoshape'
    has_edit_mode = 1
    def __init__(self, name=None, *args,  **kw):
        self.__class__ = Loader(name)
        self.name = name
        apply(self.__init__, args, kw)


class AutoshapeBase(TrafoPlugin):
    class_name = 'Autoshape' # Pretend to be 'Autoshape'. This is used for
                             # saving.
    
    has_edit_mode  = 1
    is_Group       = 1
    is_Compound    = 0 # XXX Hack to avoid a bug in sketch: usually snap points
                       # of compounds and therefore PluginCompounds are ignored.
                       
    is_curve       = 1 # XXX This is only allowed for Autoshapes consisting of
                       # entirely curve_objects. Should be overridden otherwise.
    
    has_fill       = 1
    has_line       = 1
    has_properties = 1 # A lie ... but we will steal the properties from the
                       # kids when asked to return properties.

    Ungroup = TrafoPlugin.GetObjects

    control_pressed = 0
    shift_pressed = 0
    help_text = _('No help available for this shape.')

    commands = []
    
    def __init__(self, data = None, trafo = None, version = None, \
                 duplicate = None, loading = 0):
        TrafoPlugin.__init__(self, trafo = trafo, duplicate = duplicate)
        
        self.editor = None

        if duplicate:
            data = duplicate.GetData()
            self.SetData(data)
            self.name = duplicate.name

        if loading:
            self.SetData(data, version)

        else:
            self.recompute()

    def Properties(self):
        if self.objects:
            return self.objects[0].Properties()
        return TrafoPlugin.Properties(self)
    
    def SaveToFile(self, file):
        data = self.GetData()
        TrafoPlugin.SaveToFile(self, file, self.name, data, 
                               self.trafo.coeff(), VERSION)
    
    def Info(self):
        return _("Autoshape `%s'") % self.name

    def Help(self):
        # Is there a simpler path to toplevel ?
        top = Sketch.main.application.main_window.canvas.toplevel
        HelpWindow(top, self.help_text)
    AddCmd(commands, 'AutoshapeHelp', _('Help'), Help)

    def RemoveTransformation(self):
        
        # In the implemetation of the TrafoPlugin it is assumed, that all
        # childs are rebuild after the transformation is removed. Here,
        # recompute() usually only changes the children. Therefore
        # RemoveTransformation has to be modified. The solution below has the
        # dissadvantage that only invertable transformation can be removed.
        
        try:
            inv = self.trafo.inverse()
        except:
            return NullUndo
        offset = self.trafo.offset()
        shift = Translation(offset)
        undo = self.Transform(shift(inv))
        if self.editor is not None:
            self.editor.UpdateTransientObject()
        return undo
    AddCmd(commands, 'AutoshapeRemoveTransformation',
           _('Remove Transformation'), RemoveTransformation)
    
    ### The following method solves a bug by overriding the method
    ### definition of compound.py:
    def Snap(self, point):
        best_d = 1e100
        best_p = point

        for obj in self.objects:
            d, p = obj.Snap(point)
            if d < best_d:
                best_d = d
                best_p = p                
        return best_d, best_p
    ###
    ###

    # XXX As a consequence of setting is_Compound to zero childs are not
    # investigated automatically. Hence it has to be done explicitly.
    def GetSnapPoints(self):
        points = []
        for obj in self.objects:
            points.extend(obj.GetSnapPoints())
        return points
    
    def Paths(self):
        paths = []
        for obj in self.objects:
            p = obj.Paths()
            if p is not None:
                paths.extend(p)
        assert len(paths)
        return tuple(paths)
    
    def AsBezier(self):
        return PolyBezier(paths = self.Paths())
               
    def set_editor(self, editor):
        self.editor = editor

    def unset_editor(self, editor):
        if self.editor is editor:
            self.editor = None
        
    def drag_handle(self, pa, pb, selection):
        data = self.GetData()
        self.DragHandle(pa, pb, selection)
        return self.set_data, data

    def set_data(self, data):
        undo = self.set_data, self.GetData()
        self.SetData(data)
        self.recompute()
        return undo

    def getName(self):
        return self.autoshape_name
    
    def DrawDragged(self, device, partially):
        self.DrawShape(device)
        
    def KeyHandler(self, key):
        pass

    def Editor(self):
        return AutoshapeEditor(self) 

    def rebuild_bond_list(self): # XXX hack
        pass
    
    context_commands = ('AutoshapeHelp','AutoshapeRemoveTransformation')
    
    # The following methods have to be implemented by derived classes
    def GetData(self):
        return None

    def SetData(self, data, version=None):
        pass

    def GetHandles(self):
        pass
    
    def DragHandle(self, pa, pb, selection):
        pass

RegisterCommands(AutoshapeBase)

class AutoshapeEditor(Editor):
    EditedClass = AutoshapeBase

    commands = []
    selection = 0
        
    def __init__(self, object):        
        Editor.__init__(self, object)
        object.set_editor(self)
        self.transient_object = object.Duplicate()

    def Destroy(self):
        self.transient_object = None
        self.object.unset_editor(self)

    def ButtonDown(self, p, button, state):
        if self.selection is not None:
            self.UpdateTransientObject()
            start = self.selection.p
            Editor.DragStart(self, start)
            return p - start
        else:
            return None

    def ButtonUp(self, p, button, state):
        Editor.DragStop(self, p)
        undo = self.object.drag_handle(self.drag_start, p, \
                                       self.selection.index+1)
        self.rebuild_bond_list() # XXX hack
        return undo
    
    def MouseMove(self, p, state):
        transient = self.transient_object
        object = self.object
        
        self.UpdateTransientObject()
        object.control_pressed = state & const.ConstraintMask
        object.shift_pressed = state & const.ShiftMask
        transient.control_pressed = object.control_pressed
        transient.shift_pressed = object.shift_pressed
        transient.drag_handle(self.drag_start, p, self.selection.index+1)
        Editor.MouseMove(self, p, state)

    def GetHandles(self):
        return self.object.GetHandles()

    def SelectPoint(self, p, rect, device, mode):
        return 0

    def SelectHandle(self, handle, mode):
        self.selection = handle

    def UpdateTransientObject(self):
        self.transient_object.set_transformation(self.trafo)
        self.transient_object.SetData(self.object.GetData())
        
    def DrawDragged(self, device, partially):
        self.transient_object.DrawDragged(device, partially)
        
    def AnyKey(self, key):
        return self.KeyHandler(key)

    handled_keys = list('+-')
    handled_keys.append('Left')
    handled_keys.append('Right')
    handled_keys.append('Up')
    handled_keys.append('Down')
    handled_keys.append('S-Up')
    handled_keys.append('S-Down')
    handled_keys.append('C-Up')
    handled_keys.append('C-Down')

    AddCmd(commands, 'AutoshapeKey','', AnyKey, key_stroke=handled_keys, 
           invoke_with_keystroke=1)

RegisterCommands(AutoshapeEditor)

class UnknownShape(AutoshapeBase):
    def GetData(self):
        return ()

    def SetData(self, data, version=None):
        pass

    def GetHandles(self):
        return []

    def DragHandle(self, pa, pb, selection):
        pass
    
    def Info(self):
        return _("Unknown Autoshape Object `%s'") % self.name


class HelpWindow(SKModal):
    title = _('Help')
    def __init__(self, master, help_text, **kw):
        self.help_text = help_text
        apply(SKModal.__init__, (self, master), kw)

    def build_dlg(self):
        top = self.top
        top.resizable(0, 1)

        frame = Tkinter.Frame(top)
        text = ScrolledText(frame, height=13, width=50, background='white')
        text.insert('1.0', self.help_text)
        text.configure(state='disabled')
        text.grid(column=0, row=0, sticky='nesw')
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)
        
        button = Tkinter.Button(frame, text=_('Close'), command=self.cancel)
        button.grid(column=0, row=1)

        frame.pack(expand=1, fill='both')


# XXX this should be renamed

class StickyObject(AutoshapeBase):    
    bond_list = ()
    watch_list = () # contains all objects of the which are not bonded to self

    _connection_descr = _("""
Connections have "sticky" bonds. They adhere
to snap points of other objects. If the snap
point changes the Connector follows as if it
would be glued to this point.

A bond is 'active' when the corresponing end
of the connector is positioned _exactly_ on an
object's snap point. Therefore connections are
best positioned with 'snap to objects' turned
on. Otherwise the connector behaves as an
ordinary drawing object. 

Connectors are highly experimental thus far. A
known problem is undo: in some situations the
formation of a connection will not be un-done.

Keys:

Modifier:
    """)
    def __init__(self, *args, **kw):
        self.bond_list = []
        self.watch_list = []
        self.connections = {}
        apply(AutoshapeBase.__init__, (self,)+args, kw)

    def _changed(self, *args):        
        # This is called when the self is transformed. It is not called when
        # self reacts to an change of a client or when a handle is released.        
        self.rebuild_bond_list()
        AutoshapeBase._changed(self)
        
    def subscribe_to(self, object, channel, function, *args):
        note("subscribe to %s, %s",  id(object), channel)
        obj_id = id(object)
        object.Subscribe(channel, function, *args)
        data = (object, channel, function)+args

        if obj_id in self.connections:
            self.connections[obj_id].append(data)
        else:
            self.connections[obj_id] = [data]

    def unsubscribe_from(self, object, channel, function, *args):
        note("unsubscribe from %s, %s ", id(object), channel)
        object.Unsubscribe(channel, function, *args)

    def unsubscribe_all(self):
        failed = disconnected = 0
        for obj_id, data_list in self.connections.items():
            for data in data_list:
                object = data[0]
                note("trying to unconnect %s", data)
                try:
                    apply(object.Unsubscribe, data[1:])
                    disconnected = disconnected + 1
                except Exception, e:
                    failed = failed + 1
                    if _debug:
                        print "Warning: ",e

            #print "unsubscribed %s of %s" % (disconnected, disconnected+failed)
        self.connections = {}

    def subscription_info(self):
        for obj_id, data_list in self.connections.items():
            for data in data_list:
                print obj_id, data[1:]
                        
    def SetDocument(self, doc):
        note("SetDocument %s", self)
        AutoshapeBase.SetDocument(self, doc)
        if doc is not None:
            self.subscribe_to(doc, const.SELECTION, self.selection_changed)
        else:
            # this happens when an object is copied to the clipboard
            pass

    def selection_obj_changed(self, *args):
        # an object from slection which is not bonded changed -> check for new bonds
        note("selction_obj")
        self.update_bond_list_from_selection()
        
    def selection_changed(self, *args):
        note("selction")
        self.update_bond_list_from_selection()
        for obj in self.watch_list:
            self.remove_from_watch_list(obj)

        if self.document is not None:
                
            doc = self.document
            watches = doc.SelectedObjects()[:]

            for obj, i, j in self.bond_list:
                if obj in watches:
                    watches.remove(obj)

            for obj in watches:
                if not isinstance(obj, StickyObject):
                    self.add_to_watch_list(obj)
                                                    
    ### this is probably not needed ...           
    def Disconnect(self):
        self.unsubscribe_all()
        AutoshapeBase.Disconnect(self)
        
    def UntieFromDocument(self):
        self.unsubscribe_all()        
        AutoshapeBase.UntieFromDocument(self)

    def Unsubscribe(self, channel, func, *args):
        self.unsubscribe_all()
        AutoshapeBase.Unsubscribe(self, channel, func, *args)
        
    def Destroy(self):
        self.unsubscribe_all()
        AutoshapeBase.Destroy(self)
    ### ... until here


    def recompute(self):
        self.rebuild_bond_list()
        
    def client_changed(self, obj, i, j):
        note("client changed %s, %i, %i", obj, i, j)

        p = obj.GetSnapPoints()[i]
        
        doc = self.document
        doc.AddClearRect(self.bounding_rect)

        self.bond_changed(j, p)
        self.recompute()
        doc.AddClearRect(self.bounding_rect)
        doc.issue_redraw()
        
    def get_bonds_from_obj(self, obj, sticky_points, bonds):
        # Examine all snap points of object whether it is at the same position
        # as one of self's sticky points. Matches are appended to bonds.

        if isinstance(obj, StickyObject):
            return

        epsilon = 1e-3
        
        i = 0 # numbers snap points
        for snap in obj.GetSnapPoints():
            j = 0 # numbers sticky_points
            for p in sticky_points:
                if (p-snap).polar()[0] < epsilon:
                    bonds.append((obj, i, j))
                j = j+1
            i = i+1

    def rebuild_bond_list(self):
        note("rebuild bondlist")
        doc = self.document
        if doc is None:
            return

        new = []

        points = self.GetStickyPoints()
        doc.WalkHierarchy(lambda o, s=self,p=points, n=new: \
                          s.get_bonds_from_obj(o, p, n))

        for item in self.bond_list:
            if item in new:
                continue
            obj, i, j = item
            note("remove from bond list") 
            self.unsubscribe_from(obj, const.CHANGED, 
                                  self.client_changed, i, j)
        for item in new:
            if item in self.bond_list:
                continue
            obj, i, j = item
            if obj in self.watch_list:
                self.remove_from_watch_list(obj)
            note("add to bond list") 
            self.subscribe_to(obj, const.CHANGED,
                              self.client_changed, i, j)
        self.bond_list = list(new)
        note("set new bond list with %i clients" , len(new))

        
    def update_bond_list_from_object(self, object):        
        doc = self.document
        if doc is None:
            return

        bonds = []
        points = self.GetStickyPoints()
        self.get_bonds_from_obj(object, points, bonds)

        remove = []
        for item in self.bond_list:
            if item in bonds:
                continue
            obj, i, j = item
            if obj is object:
                remove.append(item)

        for item in remove:
            self.bond_list.remove(item)
            note( "remove obj from bonds ")
            self.unsubscribe_from(object, const.CHANGED, 
                                  self.client_changed, i, j)
        for item in bonds:
            if item in self.bond_list:
                continue
            obj, i, j = item
            note("add obj to bonds ")
            self.subscribe_to(object, const.CHANGED, 
                              self.client_changed, i, j)

            self.bond_list.append(item)

            if obj in self.watch_list:
                self.remove_from_watch_list(obj)

    def remove_from_watch_list(self, obj):
        self.watch_list.remove(obj)
        note("remove from watches ") 
        self.unsubscribe_from(obj, const.CHANGED, self.selection_obj_changed)

    def add_to_watch_list(self, obj):
        assert not obj in self.watch_list
        self.watch_list.append(obj)
        note("add to watches ")
        self.subscribe_to(obj, const.CHANGED, self.selection_obj_changed)

        
    def update_bond_list_from_selection(self):        
        doc = self.document
        if doc is None:
            return
        selected = doc.SelectedObjects()
        for obj in selected:
            self.update_bond_list_from_object(obj)

    def PointBonded(self, which):
        raise "deprected"
        for obj, i, j in self.bond_list:
            if j == which:
                return 1
        return 0
        
    ### The following has to be implemented by derived classes
    def bond_changed(self, i, p):
        return NullUndo

    def GetStickyPoints(self):
        return ()
