_libmod = __import__(__name__[:-6], fromlist=['pkg_dir'])
#from Lib.autoshapes import pkg_dir
import os.path
import glob
from PIL import Image
try:
    from PIL import ImageTk
except:
    import ImageTk

icon_dir = os.path.join(_libmod.pkg_dir, 'icons')
pattern = os.path.join(icon_dir, '*.png')

class IconManager:    
    dict = None
    def __init__(self):
        self.dict = {}
    def __getattr__(self, name):
        if name not in self.dict:
            self.init()
            if not name in self.dict:
                raise "icon '%s' not found " % name, icon_dir 
        return self.dict[name]

    def init(self):
        for path in glob.glob(icon_dir+'/*'):
            filename = os.path.split(path)[-1]
            name = os.path.splitext(filename)[0]
            image = Image.open(path)
            self.dict[name] = image

icons = IconManager()

        
    
