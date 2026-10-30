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

from Sketch import Scale, TrafoPlugin, PolyBezier, CreatePath
from Sketch.Base import main
from Sketch import Group, SketchError
from Sketch.Base import load
from Sketch.Base import config
from Sketch.Lib.util import as_unicode, run_gs_output, ghostscript_command
from tempfile import mkdtemp

import os
import sys
from os.path import exists
from os import getcwd, chdir
from shutil import rmtree, which
from subprocess import Popen, PIPE, TimeoutExpired

#set this to 1 to display the intermediate messages to the console
print_messages=0

default_size=25


# Expected failure of the external LaTeX toolchain: a missing or
# failing program, or a missing output file.  Raised as a
# (title, message) pair, reported to the user and re-raised, so that
# the caller (TrafoPlugin.SetParameters -> the plugin dialog) can
# reject the change.  A SketchError subclass, so that generic dialog
# code can catch it without importing this module.  (The original
# plugin derived it from BaseException, which made it invisible to
# `except Exception' handlers, while the bare `except:' handlers on
# its propagation path caught it anyway; the exception escaping
# recompute() used to result in an endless recompute exception loop.)
class cm_exc(SketchError):
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
	    # self.text is unicode in the model: the plugin dialog
	    # provides unicode directly, and byte strings loaded from a
	    # .sk file are utf-8 encoded parameters (see
	    # devdocs/string-handling.md)
            self.text = as_unicode(text)
            self.size = size
            self.group = None
            self.ptext = self.text
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
        # self.text is always unicode (normalized in __init__; see
        # devdocs/string-handling.md)
        if  self.text != self.ptext \
                or self.size != self.psize \
                or self.redraw:
            # text/size are new or changed (or the initial run requested
            # through self.redraw): render them.  Atomic: ptext/psize,
            # the group and the children are committed together, only
            # after create_tex_sk succeeded.  If it fails, it reports
            # the error and re-raises -- the object then stays exactly
            # as it was (the parameters are restored by
            # TrafoPlugin.SetParameters) and the caller rejects the
            # change.
            try:
                group = create_tex_sk(self.text,self.size,self.app.main_window.document)
            finally:
                # do not retry on unrelated recomputes (e.g. triggered
                # by a move), whether the run succeeded or not
                self.redraw = 0
            self.ptext = self.text
            self.psize = self.size
            self.group = group
        self.rebuild_children()

    def rebuild_children(self):
        # (re)build the children from the current rendering (self.group)
        # and the current transformation
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

    def SetParameters(self, kw):
        # Exact-state undo: on success the undo entry stores the
        # previous rendering (self.group) together with the previous
        # parameters, so Undo/Redo restore the exact curves without
        # re-running the LaTeX toolchain.  On failure cm_exc propagates
        # (after being reported by create_tex_sk); the object has not
        # been changed (recompute is atomic, the parameters are
        # restored by TrafoPlugin.SetParameters).
        old_params = (self.text, self.size)
        old_group = self.group
        stock_undo = TrafoPlugin.SetParameters(self, kw)
        if (self.text, self.size) == old_params and self.group is old_group:
            return stock_undo
        return (_restore_ltx_state, self, old_params, old_group,
                (self.text, self.size), self.group)

    def Text(self):
        return self.text

    def Size(self):
        return self.size

    def SaveToFile(self, file):
        TrafoPlugin.SaveToFile(self, file, self.text, self.size,
			       self.trafo.coeff())

    def Info(self):
        # self.text is unicode, so slicing cannot split a character
        return _("LaTeX Text: `%s', size %g") \
               % (self.text[:20],self.size)

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
\\IfFileExists{amssymb.sty}{\\usepackage{amssymb}}{}
\\IfFileExists{txfonts.sty}{\\usepackage{txfonts}}{}
\\IfFileExists{bm.sty}{\\usepackage{bm}}{}
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

        for dpre in [docdir,os.path.dirname(docdir),config.user_config_dir]:
            try:
                with open(os.path.join(dpre,'sk-ltx.tex'),'r') as fpre:
                    # the preamble file is utf-8 text; normalize so the
                    # wrapper below stays unicode throughout
                    preamb = as_unicode(fpre.read())
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
\\usepackage[usenames]{color}
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
    
    if pstoedit_can_pdf:
        lcmd, lext, sext = 'pdflatex', 'pdf', 'pdf'
    else:
        lcmd, lext, sext = 'latex', 'dvi', 'ps'

    tdir = mkdtemp()

    msgs = ''
    group = None

    try:
        # fail early, and with a clear message, when a required
        # external program is not installed (inside the try: the
        # cm_exc handler below must be the only exit path)
        check_tools((lcmd, 'pstoedit', ghostscript_command())
                    if pstoedit_can_pdf
                    else (lcmd, 'dvips', 'pstoedit', ghostscript_command()))
        chdir(tdir)
        with open('sk.tex','wb') as tfile:
            # texwrapper is always unicode (text and preamble are
            # normalized); the wrapper declares
            # \usepackage[utf8]{inputenc}, so write utf-8 bytes --
            # binary mode, exact bytes regardless of the locale and
            # without newline translation
            tfile.write(texwrapper.encode('utf-8'))
        if not exists('sk.tex'):
            raise cm_exc("LaTeX", "Can't create tempory file %s" %  os.path.join(tdir,'sk.tex'))

        res = run_tool('%s -interaction=scrollmode sk.tex' % lcmd,
                       'sk.%s' % lext, "LaTeX")
        msgs = msgs + '--latex--\n' + res

        if not pstoedit_can_pdf:
            res = run_tool('dvips sk', 'sk.ps', "dvips")
            msgs = msgs + '--dvips--\n' + res

        res = run_tool('pstoedit -nfr -nomaptoisolatin1 -dt -f sk sk.%s sk.sk'
                       % sext, 'sk.sk', "pstoedit")
        msgs = msgs + '--pstoedit--\n' + res

        doc = load.load_drawing('sk.sk')
        group = doc.as_group()
        messages = doc.meta.load_messages
        if messages:
            # warnings, not a failure: the render stays valid even when
            # the report fails (falls back to stderr)
            try:
                write_error('Import Warnings:', messages)
            except Exception:
                sys.stderr.write('LaTeX Text: Import Warnings:\n%s\n'
                                 % messages)
            doc.meta.load_messages = ''

    except cm_exc as val:
        # The error report itself must never raise: the message box may
        # be unavailable (then the report falls back to stderr).  After
        # reporting, re-raise, so that the caller rejects the change:
        # TrafoPlugin.SetParameters restores the parameters, recompute
        # is atomic (the children have not been touched), and the
        # plugin dialog aborts the transaction (no undo entry, no
        # EDITED message) -- the object and the dialog stay exactly as
        # they were before the update.
        title, message = val.args
        if print_messages:
            print(title, message)
        try:
            write_error(title, message)
        except Exception:
            sys.stderr.write('LaTeX Text: %s:\n%s\n' % (title, message))
        raise

    except SketchError as value:
        try:
            write_error('Loading formatted LaTeX', str(value))
        except Exception:
            sys.stderr.write('LaTeX Text: Loading formatted LaTeX:\n%s\n'
                             % value)
        raise

    finally:
        chdir(cwd)
        remove_temp_files(tdir)

    if print_messages:
        print(msgs)
    
    return group


# give up on a toolchain command after this many seconds; a hung TeX
# (or pstoedit/ghostscript) would otherwise freeze the whole UI
command_timeout = 120

def exec_command(command):
    try:
        po = Popen(command.split(),stdout=PIPE,stderr=PIPE,stdin=PIPE)
        try:
            out,err = po.communicate(timeout=command_timeout)
        except TimeoutExpired:
            po.kill()
            po.communicate()
            raise cm_exc('Timeout running external command',
                         'When running %s:\n'
                         'the program did not terminate within %d seconds'
                         % (command, command_timeout))
        # the output ends up in the warning messages (str); the tool
        # output is ascii/utf-8, undecodable bytes are replaced
        return (out + err).decode('utf-8', 'replace')
    except cm_exc:
        raise
    except Exception as val:
        raise cm_exc('Error executing external command',
                     'When running %s:\n%s' % (command,str(val)))

def check_tools(progs):
    # raise a single clear cm_exc naming the programs that are missing
    missing = [prog for prog in progs if which(prog) is None]
    if missing:
        raise cm_exc('LaTeX Text',
                     'Required external program(s) not found: %s\n'
                     'Install them (TeX Live, pstoedit, ghostscript) '
                     'and try again.' % ', '.join(missing))

def run_tool(command, output_file, title):
    # run one toolchain step and require its output file
    res = exec_command(command)
    if not exists(output_file):
        raise cm_exc(title, res)
    return res

def _restore_ltx_state(obj, params, group, other_params, other_group):
    # Undo/Redo entry of LtxObj.SetParameters: restore an exact
    # previous state -- parameters and rendering -- without running the
    # LaTeX toolchain, and return the entry for the opposite direction.
    obj.text, obj.size = params
    obj.ptext, obj.psize = params
    obj.group = group
    obj.rebuild_children()
    return (_restore_ltx_state, obj, other_params, other_group, params, group)

def write_error(btitle,bmessage):
    main.application.MessageBox(title = btitle, message=bmessage)

def remove_temp_files(dirname):
    rmtree(dirname,ignore_errors=True)

# Check if pstoedit can process pdf files directly.  Two constraints:
# - the new C-based PDF interpreter of ghostscript (pdfi), the default
#   since gs 9.56, bypasses the PostScript operators redefined by
#   pstoedit: PDF input then silently produces an empty output file
#   (the old PostScript-based interpreter must be the default; gs
#   9.55 is the last release with it);
# - gs >= 10 is reported as incompatible by older pstoedit versions.
# Hence the maximum allowed version is 9.55.
try:
    # the `gs -v' version banner goes to stderr
    banner = run_gs_output(['-v'])[1]
    version = banner.split()[2].split('.')
    pstoedit_can_pdf = (int(version[0]), int(version[1])) <= (9, 55)
except:
    pstoedit_can_pdf = False
