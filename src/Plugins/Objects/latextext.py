# latextext.py - a plugin for Sketch to include LaTeX equations
# Soren Henriksen  2002-06-07
# Vladimir Eltsov 2002-2026
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Library General Public
# License as published by the Free Software Foundation; either
# version 2 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.	See the GNU
# Library General Public License for more details.
#
# You should have received a copy of the GNU Library General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307	USA
#
# --------------------------------------------------------------------
#
# latextext.py
# 
# This plugin implements a LaTeXText object for including LaTeX fragments
# into a sketch document.  S.J.Henriksen 12/2001
# Requires that the computer modern postscript fonts be available to
# X and to sketch
#
# needs a pstoedit with the font name bug fixed, and that works with
# font encodings that use the low ascii characters
#
# This plugin was inspired by Christian von Ferber's TeXSketch script
#
# sjh@2pi.info  http://www.2pi.info/latex/sketchlatex/
#


###Sketch Config
#type = PluginCompound
#class_name = 'LtxObj'
#menu_text = 'LaTeX Text'
#parameters = (\
#    ('text', 'text', '0', None, 'Text'), \
#    ('size', 'ptlength', 25.0, (0.0, None), 'Size'))
#standard_messages = 1
###End

(''"LaTeX Text")
(''"Text")
(''"Size")

from Sketch import Scale, TrafoPlugin, PolyBezier, CreatePath, main
from Sketch import load, Group, SketchError
from tempfile import mkdtemp

import os
from os.path import exists
from os import getcwd, chdir
from posix import system
from string import replace
from shutil import rmtree
from subprocess import Popen, PIPE

#set this to 1 to display the intermediate messages to the console
print_messages=0

default_size=25


class cm_exc(BaseException):
    pass

class LtxObj(TrafoPlugin):

    class_name = 'LtxObj'
    has_edit_mode       = 0
    is_Text             = 0
    is_SimpleText       = 0
    is_curve            = 0
    is_clip             = 0
    has_font            = 0
    has_fill            = 0
    has_line            = 0
    is_Group            = 1

    def __init__(self, text = '0', size = default_size, trafo = None, loading = 0,
		 duplicate = None):
	TrafoPlugin.__init__(self, trafo = trafo, duplicate = duplicate)
	if duplicate is not None:
	    self.text = duplicate.text
	    self.size = duplicate.size
            self.group = duplicate.group
	    self.ptext = duplicate.ptext
	    self.psize = duplicate.psize
            self.redraw = duplicate.redraw
	else:
	    self.text = text
	    self.size = size
	    self.group = None
            self.ptext = text
            self.psize = size
            self.redraw = 1

        self.app = main.application

        if loading:
            self.redraw = 0
        else:
	    self.recompute()


    def load_Done(self):
        TrafoPlugin.load_Done(self)
        self.group = Group(duplicate=Group(self.objects))
        self.group.Transform(self.trafo.inverse())

    def recompute(self):
        if  self.text != self.ptext or self.size != self.psize:
            #text is new or changed
            self.ptext = self.text
            self.psize = self.size
	    self.redraw = 1

	if self.redraw:
            self.redraw = 0
	    self.group = create_tex_sk(self.text,self.size,self.app.main_window.document)

        trafo = self.trafo

        if self.group is None:
            objects=[]
        else:
            #duplicate the object, and transform the duplicate to the trafo    
            group=self.group.__class__(duplicate = self.group)
            group.Transform(trafo)
            objects=group.Ungroup()


        self.set_objects(objects)
        self.connect_objects()

    def Text(self):
	return self.text

    def Size(self):
	return self.size

    def SaveToFile(self, file):
	TrafoPlugin.SaveToFile(self, file, self.text, self.size,
			       self.trafo.coeff())

    def Info(self):
        return _("LaTeX Text: `%s', size %g") % (self.text[:20],self.size)

    def AsBezier(self):
	return self.objects[0].AsBezier()

    def Paths(self):
	return self.objects[0].Paths()

    def Ungroup(self):
        return self.objects


def FontSizeCommand(size):
    return('\\fontsize{%g}{%g}\\selectfont '% (size, size*1.2)  )

def create_tex_sk(text,fontsz,doc=None):
    # default preamble
    preamb='''
\\usepackage{amssymb}
\\usepackage{txfonts}
\\usepackage{bm}
\\renewcommand{\\baselinestretch}{1.3}'''

    cwd = getcwd();
    if text.startswith('\\noskltx'):
        text = text[8:]
    else:
        # try to find the user's preamble
        if doc is not None and doc.meta.fullpathname is not None:
            docdir = os.path.dirname(doc.meta.fullpathname)
        else:
            docdir = cwd

        for dpre in [docdir,os.path.dirname(docdir)]:
            try:
                with open(os.path.join(dpre,'sk-ltx.tex'),'r') as fpre:
                    preamb=fpre.read()
                    break
            except IOError:
                pass

    # allow additions to the preamble as \preamble<char>pretext<char>
    # where <char> is any char not in pretext
    extrapre = ''
    if len(text) > 12 and text.startswith('\\preamble'):
        ie = text.find(text[9],10)
        if ie > 10:
            preamb += '\n' + text[10:ie]
            text = text[ie+1:]
        
    # separate sktextwidth is introduced for freedom of implementaions
    # e.g. I played with implementation via minipage
    texwrapper='''\\documentclass{article}
\\usepackage[dvips,usenames]{color}
\\usepackage[utf8]{inputenc}
\\parindent 0pt
\\pagestyle{empty}
\\newlength\\sktextwidth
\\sktextwidth 29cm
%s
\\textwidth\\sktextwidth
\\begin{document}
%s%s
\\end{document}
''' % (preamb,FontSizeCommand(fontsz),text)
    #print(texwrapper)
    
    tdir = mkdtemp()

    msgs = ''
    group = None

    try:
        chdir(tdir)
        with open('sk.tex','w') as tfile:
            tfile.write(texwrapper)
        if not exists('sk.tex'):
            raise cm_exc("LaTeX", "Can't create tempory file %s" %  os.path.join(tdir,'sk.tex'))

        if pstoedit_can_pdf:
            lcmd = 'pdflatex'
            lext = 'pdf'
            sext = 'pdf'
        else:
            lcmd = 'latex'
            lext = 'dvi'
            sext = 'ps'
        
        res = exec_command('%s -interaction=scrollmode sk.tex' % lcmd)
        if not exists('sk.%s' %lext):
            raise cm_exc("LaTeX",res)
        msgs = msgs + '--latex--\n' + res

        if not pstoedit_can_pdf:
            res = exec_command('dvips sk')
            if not exists('sk.ps'):
                raise cm_exc("dvips",res)
            msgs = msgs + '--dvips--\n' + res

        res = exec_command('pstoedit -nfr -nomaptoisolatin1 -dt -f sk sk.%s sk.sk' % sext)
        if not exists('sk.sk'):
            raise cm_exc("pstoedit",res)
        msgs = msgs + '--pstoedit--\n' + res

        doc = load.load_drawing('sk.sk')
        group = doc.as_group()
        messages = doc.meta.load_messages
        if messages:
            write_error('Import Warnings:', messages)
            doc.meta.load_messages = ''

    except cm_exc as val:
        print(val[0], val[1])
        write_error(val[0], val[1])

    except SketchError as value:
        write_error('Loading formatted LaTeX', str(value))

    finally:
        chdir(cwd)
        remove_temp_files(tdir)

    if print_messages:
        print msgs
    
    return group


def exec_command(command):
    po = Popen(command.split(),stdout=PIPE,stderr=PIPE)
    out,err = po.communicate()
    return out+err

def write_error(btitle,bmessage):
    main.application.MessageBox(title = btitle, message=bmessage)

def remove_temp_files(dirname):
    rmtree(dirname,ignore_errors=True)

# Check if pstoedit can process pdf files directly
try:
    # get ghostscript major version. pstoedit cannot do pdf for version >= 10
    pstoedit_can_pdf = int(exec_command('gs -v').split()[2].split('.')[0]) < 10
except:
    pstoedit_can_pdf = False
