###Sketch Config
#type = PluginCompound
#class_name = 'Autoshape'
#menu_text = 'Autoshapes'
#standard_messages = 1
#custom_dialog = 'AutoshapeDlg'
###End

(''"Autoshapes")

_verbose = 0
_debug   = 0

from Sketch import _, Trafo, TrafoPlugin, Rotation, RegisterCommands
from Sketch.UI.sketchdlg import SketchPanel


import Tkinter
from PIL import Image
try:
    from PIL import ImageTk
except:
    import ImageTk
import array
import sys
import string
from math import pi
from ScrolledText import ScrolledText
from Lib.autoshapes.autoshapelib import VERSION, Autoshape
        

def byte(v):
    return min(255, int(v))
    
def colorize(img, fg, fr, fb):
    q_image = img.quantize(256)
    data = list(array.array('B', q_image.im.getpalette()))
    for i in range(0,len(data),3):
        red, green, blue = data[i:i+3]
        data[i:i+3] = [byte(fr*red), byte(fg*green), byte(fb*blue)]

    q_image.im.putpalette('RGB',string.join(map(chr, data), ''))
    return q_image
        
def highlight(img):
    return colorize(img, 1., 0.95, 0.4)

def grey(img):
    return colorize(img, 0.9, 0.9, 0.9)

class ShapeBtn(Tkinter.Button):
      def __init__(self, master, img):
          Tkinter.Button.__init__(self, master)
          normal = ImageTk.PhotoImage(grey(img))
          highlighted = ImageTk.PhotoImage(highlight(img))


          self.img = img
          self.configure(self,
                         image = normal,
                         height             = 27,
                         width              = 27,
                         background         = '#ffffff',
                         relief             = Tkinter.FLAT,
                         borderwidth        = 0,
                         highlightthickness = 0, 
                         activebackground   = '#ffff99'
                         )
          self.bind('<Enter>', lambda e, s=self:s.configure(image=highlighted))
          self.bind('<Leave>', lambda e, s=self:s.configure(image=normal))



class AutoshapeDlg(SketchPanel):
    title = _('Auto Shapes')
    receivers = SketchPanel.receivers[:]

    def __init__(self, master, main_window, doc):
        self.main_window = main_window

        SketchPanel.__init__(self, master, main_window, doc,
                             name = 'autoshapedlg')

    def build_dlg(self):
        from Lib.autoshapes.icons import icons
        
        top = self.top
        frame = Tkinter.Frame(top)
        text = ScrolledText(frame, background='#ffffff', height=10, width=40)
        self.text = text

        def NOOP():
            pass
        
        def add(text, bitmap, fun=NOOP):
            button = ShapeBtn(text, bitmap)
            button.config(command=fun)
            text.window_create("end", window=button)

        def newline(text):
            pass
            #text.insert('end', '\n')

        add(text, icons.uparrow, lambda s=self:s.insert('arrow', 270))
        add(text, icons.rightarrow, lambda s=self:s.insert('arrow', 180))
        add(text, icons.downarrow, lambda s=self:s.insert('arrow', 90))
        add(text, icons.leftarrow, lambda s=self:s.insert('arrow', 0))
        newline(text)
        add(text, icons.vdoublearrow, lambda s=self: \
            s.insert('doublearrow', 90))
        add(text, icons.hdoublearrow, lambda s=self: \
            s.insert('doublearrow', 0))
        newline(text)
        add(text, icons.thinleftturn1, lambda s=self:s.insert('thinturn'))
        add(text, icons.thinrightturn1, lambda s=self: \
            s.insert('thinturn', 180))
        add(text, icons.thinleftturn2, lambda s=self: \
            s.insert_toggle_dir('thinturn'))
        add(text, icons.thinrightturn2, lambda s=self: \
            s.insert_toggle_dir('thinturn', 180))
        add(text, icons.leftthinhalfturn, lambda s=self: \
            s.insert('thinhalfturn'))
        add(text, icons.rightthinhalfturn, lambda s=self: \
            s.insert('thinhalfturn', 180))
        newline(text)
        
        add(text, icons.scalebar, lambda s=self:s.insert('scalebar'))
        add(text, icons.happy, lambda s=self:s.insert('smiley'))
        add(text, icons.sad, lambda s=self:s.insert_sad())
        newline(text)
 
        add(text, icons.cube, lambda s=self:s.insert('cube'))
        add(text, icons.cylinder, lambda s=self:s.insert('cylinder'))
        add(text, icons.triangle, lambda s=self:s.insert_triangle())
        add(text, icons.hexagon, lambda s=self:s.insert_hexagon())
        newline(text)

        add(text, icons.star1, lambda s=self:s.insert_star(10,20,6))
        add(text, icons.star2, lambda s=self:s.insert_star(15,20,6))
        add(text, icons.star3, lambda s=self:s.insert_star(5,20,8))
        newline(text)
        
        add(text, icons.angle, lambda s=self:s.insert('angle'))
        add(text, icons.measure, lambda s=self:s.insert('measure'))
        #add(text, icons.roundedangle, lambda s=self:s.insert('roundedangle'))
        
        add(text, icons.raster, lambda s=self:s.insert('raster'))
        add(text, icons.tangent, lambda s=self:s.insert('tangent'))
        add(text, icons.divide, lambda s=self:s.insert('divide'))
        add(text, icons.intersection, lambda s=self:s.insert('intersection'))
        newline(text)

        
        add(text, icons.circle1, lambda s=self:s.insert('circle1'))
        add(text, icons.circle2, lambda s=self:s.insert('circle2'))
        add(text, icons.circle3, lambda s=self:s.insert('circle3'))
        add(text, icons.arc, lambda s=self:s.insert('arc'))
        add(text, icons.rim, lambda s=self:s.insert('rim'))
        newline(text)
        
        add(text, icons.vconnection, lambda s=self:s.insert('vconnection'))
        add(text, icons.hconnection, lambda s=self:s.insert('hconnection'))
        add(text, icons.dconnection, lambda s=self:s.insert('dconnection'))
        newline(text)

        text.configure(state='disabled')
        text.grid(column=0, row=0, sticky='ewns')
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)
        
        bottom = Tkinter.Frame(frame)    
        button = Tkinter.Button(bottom, text=_('Close'), \
                                command=self.close_dlg)
        button.pack(side='right')

        if _debug:
            button = Tkinter.Button(bottom, text=_('Shell'), \
                                    command=self.open_shell)
            button.pack(side='left')

        bottom.grid(column=0, row=1, sticky='ew')
        frame.pack(fill='both', expand=1)
        self.frame = frame
            
    def insert(self, name, angle=0):
        object = Autoshape(name)
        object.Transform(Rotation(angle*pi/180.))
        self.main_window.PlaceObject(object)

    def insert_toggle_dir(self, name, angle=0):
        object = Autoshape(name)
        object.Transform(Rotation(angle*pi/180.))
        object.ToggleDir()
        self.main_window.PlaceObject(object)

    def insert_angle(self):
        object = Autoshape('angle')
        object.SetData((50, 50, 16, 60, 360))
        self.main_window.PlaceObject(object)

    def insert_hexagon(self):
        object = Autoshape('star')
        object.SetData((20, 20, 3))
        self.main_window.PlaceObject(object)

    def insert_home(self):
        object = Autoshape('star')
        object.Transform(Rotation(-90*pi/180.))
        object.SetData((10, 10, 10, 30))
        self.main_window.PlaceObject(object)

    def insert_triangle(self):
        object = Autoshape('star')
        object.SetData((10, 20, 3))
        object.Transform(Rotation(-pi/2))
        self.main_window.PlaceObject(object)

    def insert_star(self, *data):
        object = Autoshape('star')
        object.SetData(data)
        self.main_window.PlaceObject(object)

    def insert_sad(self):
        object = Autoshape('smiley')
        object.SetData(7.)
        self.main_window.PlaceObject(object)

    def open_shell(self, *args):
        try:
            import pyshell.skshell as shell
        except:
            return
        namespace = locals()
        namespace['self'] = self
        import Sketch
        namespace['Sketch'] = Sketch
        namespace['doc'] = self.document
        shell.open(namespace)

def unload():
    import sys
    for key, val in sys.modules.items():
        try:
            f = val.__file__
        except:
            continue
        if f.find('autoshape') > -1:
            if _verbose:
                print "unloading module ", f
            del sys.modules[key]
        else:
            if 0:
                print "i ", f[-20:]


