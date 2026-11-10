# Sketch - A Python-based interactive drawing program
# Copyright (C) 2026 by Vladimir Eltsov
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
# Panel containers
#
# A SketchPanel builds its widgets into the `body' of a container. The
# container provides the frame around it: a toplevel window managed by
# the window manager (WindowContainer) or, later, a frame docked in the
# side bar of the main window.
#
# Container interface:
#
#	body			the widget the panel builds into (panel.top)
#	after_build()		called once the panel has been built
#	show_raise()		make the panel visible and bring it to front
#	withdraw()		hide the panel
#	save_prefs()		store the geometry in the preferences
#	destroy()		destroy the container and the body
#

from Sketch.Base import config

from tkinter import Toplevel

from Sketch.UI import tkext
from Sketch.UI import skpixmaps
pixmaps = skpixmaps.PixmapTk


class WindowContainer:

    # The panel is a toplevel window. Its position relative to the main
    # window is stored in the preference dlg_pos_<panel class>.

    x_correction = 0
    y_correction = 0

    def __init__(self, panel, master, **kw):
        self.master = master
        title = panel.title

        kw['class'] = panel.class_name
        top = Toplevel(*(master,), **kw)
        top.title(title)
        self.pref_pos_name = 'dlg_pos_' + panel.__class__.__name__
        if config.preferences.panel_use_coordinates:
            posx, posy = config.get_preference(self.pref_pos_name, (0.1, 0.1))
            # avoid confusing behaviour of panels if the position is negative
            # or > 1:
            posx = max(min(posx, 1), 0)
            posy = max(min(posy, 1), 0)

            posx = master.winfo_rootx() + int(posx * master.winfo_width())
            posy = master.winfo_rooty() + int(posy * master.winfo_height())
            top.geometry('%+d%+d' % (posx, posy))
            self.posx = posx
            self.posy = posy

        top.transient(master)
        top.group(master)
        top.iconname(title)
        top.iconbitmap(pixmaps.Icon)
        top.iconmask(pixmaps.Icon_mask)
        top.protocol('WM_DELETE_WINDOW',
                     tkext.MakeMethodCommand(panel.close_dlg))
        # the following is a workaround for a Tkinter bug. Tkinter 1.63
        # doesn't like bindings for the Destroy event.
        top.tk.call('bind', top._w, '<Destroy>',
                    tkext.MakeMethodCommand(panel.destroyed) + ('%W',))

        self.top = top
        self.body = top

    def after_build(self):
        top = self.top
        if config.preferences.panel_use_coordinates \
           and config.preferences.panel_correct_wm:
            if not top.winfo_ismapped():
                top.wait_visibility()
            self.x_correction = self.posx - top.winfo_rootx()
            self.y_correction = self.posy - top.winfo_rooty()

    def show_raise(self):
        self.top.deiconify()
        self.top.tkraise()

    def withdraw(self):
        self.top.withdraw()

    def save_prefs(self):
        master = self.master
        top = self.top
        width = float(master.winfo_width())
        height = float(master.winfo_height())
        posx = (top.winfo_rootx() + self.x_correction - master.winfo_rootx())\
             / width
        posy = (top.winfo_rooty() + self.y_correction - master.winfo_rooty())\
             / height
        setattr(config.preferences, self.pref_pos_name, (posx, posy))

    def destroy(self):
        self.top.destroy()
        self.master = None
