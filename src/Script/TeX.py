# Christian von Ferber <ferber@physik.uni-freiburg.de>
# including contributions from
# Lukasz Pankowski <lupan@zamek.gda.pl> (replace button) 2001-08-23
# Terry Hancock <hancock@earthlink.net> (Plain TeX) 27 Aug 2001
from posix import system
from os.path import exists
from re import search
from os import mkdir
from Tkinter import StringVar, Entry, Label, Button, Frame, Text, END
import Sketch.Scripting
from types import StringType
from Sketch.Graphics import image, eps
from Sketch.UI.sketchdlg import SKModal
from Sketch.Scripting.script import Context

# ------------------------------------------------------------------
class TeXDlg(SKModal):

    title = "TeX insert"

    def __init__(self, master, **kw):
	apply(SKModal.__init__, (self, master), kw)

    def build_dlg(self):
        top = self.top

        label = Label(top, text = tex.label, anchor = 'e')
        label.grid(column = 0, row = 0)

        # 'tex.string' is non-empty if a TeX object is selected
        self.text = Text(top)
        self.text.insert(END, tex.string)
        self.text.grid(column = 0, row = 1, sticky = 'ew')
        
	but_frame = Frame(top)
	but_frame.grid(column = 0, row = 2, columnspan = 2)

	button = Button(but_frame, text = "OK", command = self.ok)
	button.pack(side = 'left', expand = 1)
        if eps_filename(Context()) != '': # lupan
            button = Button(but_frame, text = "Replace", command = self.replace)
            button.pack(side = 'left', expand = 1)
	button = Button(but_frame, text = "Cancel", command = self.cancel)
	button.pack(side = 'right', expand = 1)


    def ok(self, *args):
        tex_result = self.text.get(1.0, END)
	self.close_dlg((tex_result, 0)) 
        
    def replace(self, *args):
        tex_result = self.text.get(1.0, END)
	self.close_dlg((tex_result, 1))

# This is based on the "create_star" example script.
# ------------------------------------------------------------------
# the same again for the TeX math: offer a single entry line
class TeXmathDlg(SKModal):

    title = "TeX insert"

    def __init__(self, master, **kw):
	apply(SKModal.__init__, (self, master), kw)

    def build_dlg(self):
        top = self.top

        label = Label(top, text = tex.label, anchor = 'e')
        label.grid(column = 0, row = 0)

        # 'tex.string' is non-empty if a TeX object is selected
	self.var_text = StringVar(top)
        self.var_text.set(tex.string)

        entry = Entry(top, textvariable = self.var_text, width = 40)
        entry.grid(column = 1, row = 0, sticky = 'ew')
        
        but_frame = Frame(top)
        but_frame.grid(column = 0, row = 1, columnspan = 2)
            
	button = Button(but_frame, text = "OK", command = self.ok)
	button.pack(side = 'left', expand = 1)
        if eps_filename(Context()) != '': 
            button = Button(but_frame, text = "Replace", command = self.replace)
            button.pack(side = 'left', expand = 1)
	button = Button(but_frame, text = "Cancel", command = self.cancel)
	button.pack(side = 'right', expand = 1)


    def ok(self, *args):
        tex_result = self.var_text.get()
	self.close_dlg((tex_result, 0))

    def replace(self, *args): 
        tex_result = self.var_text.get()
	self.close_dlg((tex_result, 1))
        
# ------------------------------------------------------------------

class TeX_error_Dlg(SKModal):

    title = "TeX error"

    def __init__(self, master, **kw):
	apply(SKModal.__init__, (self, master), kw)

    def build_dlg(self):
        top = self.top
        label = Label(top, text = "Please first save your unnamed.sk file.")
        label.grid(column = 0, row = 0)
        button=Button(top, text = "Cancel", command = self.cancel)
        button.grid(column = 0, row = 1)

# Here, we create the tex-file, latex and dvips it. 
def create_tex_eps(doc_dir,text):
    path='%s/TeXsketch' % doc_dir
    if not exists(path):
        mkdir(path)
    for m in range(1000):
        file='%03d' % (m)        
        if not exists('%s/%s.tex' % (path,file)):
            break
    open('%s/%s.tex' % (path,file),'w').write(tex.wrapper % text )
    system('cd %s\n %s -interaction=scrollmode %s\n dvips -E %s -o%s.eps' % (path,tex.cmd,file,file,file))
    return '%s/%s.eps' % (path,file)

# If a TeX object is selected, extract the filename
def eps_filename(context):
    doc = context.document
    selected=doc.SelectedObjects()
    if len(selected)==1:
        obj=selected[0]
        if obj.is_Eps:
            q=search(r"EpsFile `(.*)\.eps'",obj.Info())
            if q!=None:
                filename = q.group(1)
                return filename
    return ''

# Extract the TeX text or math formula
def tex_text(doc_dir,file):
    path='%s/TeXsketch' % doc_dir
    filename='%s/%s.tex' % (path,file)
    if exists(filename):
        text=open(filename,'r').read()
        if search(r"(?ms)(% Plain TeX)",text)!=None: # detect tex-mode
            tex.cmd = "tex"
            tex.label = "TeX text:"
        if search(r"(?ms)(% LaTeX)",text)!=None:
            tex.cmd = "latex"                     
            tex.label = "LaTeX text:"                 
        if tex.mode=='matex':
            q=search(r"(?ms)%--<snip>\n(.*?)\n%--</snip>",text)
            if q!=None:
                return q.group(1)
        else:
            if text!='':
                return text
    return tex.template

            

def anytex_insert(context):
    # check for selected TeX object and extract tex_string
    file=eps_filename(context)
    doc_dir  = context.document.meta.directory
    doc_name = context.document.meta.filename
    if doc_dir==None:
        dlg=TeX_error_Dlg(context.application.root)
        dlg.RunDialog()
        return
    
    tex.string=tex_text(doc_dir,file)

    # Instantiate the modal dialog...
    if tex.mode=="matex":
        dlg = TeXmathDlg(context.application.root)
    else:
        dlg = TeXDlg(context.application.root)
    # ... and run it.
    dlg.context = context # (lupan, 2001-08-23 23:26:09+0200)
    result = dlg.RunDialog()
    if result is not None:
        # if the result is not None, the user pressed OK or replace.
        # Now constuct the TeX formula...
        text, replace = result
        filename = create_tex_eps(doc_dir,text)
        # ... load the eps ...
        imageobj = eps.EpsImage(filename = filename)
        # ... and insert it into the document
        if replace: 
            selected = context.document.SelectedObjects()
            if len(selected) == 1:
                trafo = selected[0].Trafo()
                imageobj.Transform(trafo)
                context.document.RemoveSelected()
                context.document.Insert(imageobj) 
        else: 
            context.main_window.PlaceObject(imageobj)
            
class texclass:
    pass

def tex_insert(context):
    global tex
    tex = texclass()
    tex.mode="tex"
    tex.label="TeX text:"
    tex.cmd="tex"
    tex.wrapper="%s"
    tex.template= '''%% Plain TeX version (Terry Hancock)
\\font\\std = cmss10
\\font\\it  = cmssi10
\\font\\bf  = cmbx10

%% Edit the following two lines to control bubble size.
\\hsize=2.0in
\\vsize=2.0in

\\nopagenumbers
\\hbadness=1000
\\tolerance=10000
\\hfuzz=0.1in

\\std \\noindent
%%-- start -- of -- text -- here



%%-- end   -- of -- text -- here
\\vfill\\eject
\\end

'''
    anytex_insert(context)
    
def latex_insert(context):
    global tex
    tex = texclass()
    tex.mode="latex"
    tex.label="LaTeX text:"
    tex.cmd="latex"
    tex.wrapper="%s"
    tex.template= '''%% LaTeX
\\documentclass[12pt]{article}
\\usepackage[dvips,usenames]{color}
\\usepackage{txfonts}
\\pagestyle{empty}
\\parindent 0pt
\\textwidth 25cm
\\def\\baselinestretch{1.3}
\\begin{document}
%%-- start -- of -- text -- here











%%-- end   -- of -- text -- here
\\end{document}
'''
    anytex_insert(context)

def matex_insert(context):
    global tex
    tex = texclass()
    tex.mode="matex"
    tex.label="LaTeX math:"
    tex.cmd="latex"
    tex.wrapper='''%% LaTeX math
\\documentclass{slides}
\\usepackage[dvips,usenames]{color}
\\begin{document}
\\begin{slide}
\\thispagestyle{empty}
%%--<snip>
%s
%%--</snip>
\\end{slide}
\\end{document}
'''
    tex.template="$$  $$"
    anytex_insert(context)

# Add the "(La)TeX" functions to the Script-menue
Sketch.Scripting.AddFunction('tex_insert', 'Plain TeX',
                             tex_insert,
                             menu = "TeX",
                             script_type = Sketch.Scripting.AdvancedScript)
Sketch.Scripting.AddFunction('latex_insert', 'LaTeX',
                             latex_insert,
                             menu = "TeX",
                             script_type = Sketch.Scripting.AdvancedScript)
Sketch.Scripting.AddFunction('matex_insert', 'LaTeX math',
                             matex_insert,
                             menu = "TeX",
                             script_type = Sketch.Scripting.AdvancedScript)

