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
# the window manager (WindowContainer) or a frame docked in the side bar
# of the main window (DockContainer).
#
# Container interface:
#
#	body			the widget the panel builds into (panel.top)
#	after_build()		called once the panel has been built
#	show_raise()		make the panel visible and bring it to front
#	withdraw()		hide the panel
#	save_prefs()		store the geometry in the preferences
#	get_state()		the state to restore when the panel is opened
#				again (None if there is nothing to restore)
#	set_state(state)	restore the state returned by get_state
#	destroy()		destroy the container and the body
#

from Sketch.Base import config

from tkinter import Toplevel, Frame, Label, Canvas, Scrollbar, BitmapImage, Menu
from tkinter import TOP, X

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

    def get_state(self):
        return None

    def set_state(self, state):
        pass

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


#
#	Docked panels
#

# 9x9 bitmaps for the buttons in the title bar of a docked panel

_expanded_bits = """#define expanded_width 9
#define expanded_height 9
static unsigned char expanded_bits[] = {
   0x00, 0x00, 0x00, 0x00, 0xff, 0x01, 0xfe, 0x00, 0x7c, 0x00, 0x38, 0x00,
   0x10, 0x00, 0x00, 0x00, 0x00, 0x00};
"""

_collapsed_bits = """#define collapsed_width 9
#define collapsed_height 9
static unsigned char collapsed_bits[] = {
   0x04, 0x00, 0x0c, 0x00, 0x1c, 0x00, 0x3c, 0x00, 0x7c, 0x00, 0x3c, 0x00,
   0x1c, 0x00, 0x0c, 0x00, 0x04, 0x00};
"""

_close_bits = """#define close_width 9
#define close_height 9
static unsigned char close_bits[] = {
   0x83, 0x01, 0xc6, 0x00, 0x6c, 0x00, 0x38, 0x00, 0x38, 0x00, 0x6c, 0x00,
   0xc6, 0x00, 0x83, 0x01, 0x00, 0x00};
"""

_title_colors = None

def title_colors(master):
    # The colors of the title bar: those of a highlighted menu item, as
    # Tk has them (the option database included)
    global _title_colors
    if _title_colors is None:
        menu = Menu(master)
        _title_colors = (menu.cget('activebackground'),
                         menu.cget('activeforeground'))
        menu.destroy()
    return _title_colors

_images = {}

def _image(name, master):
    image = _images.get(name)
    if image is None:
        data = {'expanded': _expanded_bits, 'collapsed': _collapsed_bits,
                'close': _close_bits}[name]
        image = _images[name] = BitmapImage(master = master, data = data,
                                            foreground = title_colors(master)[1])
    return image


class DockContainer:

    # The panel is a frame in the side bar: a title bar with the collapse
    # toggle, the title and the close button, the body and a grip at the
    # bottom to change the height of the body (only for panels with an
    # elastic layout).

    def __init__(self, panel, sidebar, **kw):
        self.panel = panel
        self.sidebar = sidebar
        self.collapsed = 0
        self.height = None	# None: the natural height of the body

        frame = Frame(sidebar.inner, name = kw.get('name'), class_ = 'SKDock',
                      relief = 'raised', borderwidth = 1)
        frame.columnconfigure(0, weight = 1)
        frame.rowconfigure(1, weight = 1)

        background, foreground = title_colors(frame)
        bar = Frame(frame, name = 'titlebar', background = background)
        bar.grid(row = 0, column = 0, sticky = 'ew')
        self.toggle = Label(bar, image = _image('expanded', frame),
                            name = 'collapse', background = background)
        self.toggle.pack(side = 'left', padx = 3)
        label = Label(bar, text = panel.title, anchor = 'w', name = 'title',
                      background = background, foreground = foreground)
        label.pack(side = 'left', fill = X, expand = 1)
        close = Label(bar, image = _image('close', frame), name = 'close',
                      background = background)
        close.pack(side = 'right', padx = 3)
        for widget in (self.toggle, label):
            widget.bind('<ButtonRelease-1>', self.toggle_collapsed)
        close.bind('<ButtonRelease-1>', lambda event: panel.close_dlg())

        body = Frame(frame, name = 'body', class_ = panel.class_name)
        body.grid(row = 1, column = 0, sticky = 'news')
        body.tk.call('bind', body._w, '<Destroy>',
                     tkext.MakeMethodCommand(panel.destroyed) + ('%W',))

        grip = Frame(frame, name = 'grip', height = 6, relief = 'raised',
                     borderwidth = 1, cursor = 'sb_v_double_arrow')
        grip.bind('<ButtonPress-1>', self.grip_press)
        grip.bind('<B1-Motion>', self.grip_motion)
        grip.bind('<Double-ButtonPress-1>', self.grip_reset)
        self.elastic = panel.resize_policy == 'elastic'

        self.frame = frame
        self.body = body
        self.grip = grip
        self.show_grip()
        sidebar.AddPanel(self)

    def show_grip(self):
        if self.elastic and not self.collapsed:
            self.grip.grid(row = 2, column = 0, sticky = 'ew')
        else:
            self.grip.grid_remove()

    def after_build(self):
        self.sidebar.ShowPanel(self)

    def toggle_collapsed(self, event = None):
        self.set_collapsed(not self.collapsed)

    def set_collapsed(self, collapsed):
        self.collapsed = collapsed
        if collapsed:
            self.body.grid_remove()
            self.toggle['image'] = _image('collapsed', self.frame)
        else:
            self.body.grid()
            self.toggle['image'] = _image('expanded', self.frame)
        self.show_grip()

    def set_height(self, height):
        # Fix the height of the body to HEIGHT pixels. None restores the
        # natural height.
        body = self.body
        self.height = height
        if height is None:
            body.pack_propagate(1)
            body.grid_propagate(1)
            body.configure(width = 0, height = 0)
        else:
            body.configure(width = body.winfo_reqwidth(), height = height)
            body.pack_propagate(0)
            body.grid_propagate(0)

    def grip_press(self, event):
        self.drag_start = (event.y_root, self.body.winfo_height())

    def grip_motion(self, event):
        y, height = self.drag_start
        self.set_height(max(height + event.y_root - y, self.sidebar.min_body))

    def grip_reset(self, event):
        self.set_height(None)

    def show_raise(self):
        if self.collapsed:
            self.set_collapsed(0)
        self.sidebar.ShowPanel(self)

    def withdraw(self):
        self.sidebar.HidePanel(self)

    def get_state(self):
        # (height of the body or None, collapsed)
        return (self.height, self.collapsed)

    def set_state(self, state):
        height, collapsed = state
        if height is not None and self.elastic:
            self.set_height(height)
        self.set_collapsed(collapsed)

    def save_prefs(self):
        pass

    def destroy(self):
        self.sidebar.RemovePanel(self)
        self.frame.destroy()
        self.sidebar = None
        self.panel = None


class SideBar(Frame):

    # The column of docked panels at the right of the main window. The
    # panels are stacked in a frame embedded in a canvas, so that the
    # column can be scrolled vertically when the panels do not fit. The
    # scrollbar is shown only when needed.
    #
    # VISIBLE_CB is called with a true value when the first panel is
    # shown and with a false value when the last one is hidden.

    min_body = 30		# the minimum height of a resized panel body

    def __init__(self, master, visible_cb, **kw):
        Frame.__init__(self, master, **kw)
        self.visible_cb = visible_cb
        self.docks = []
        self.hidden = []
        self.visible = 0

        canvas = Canvas(self, highlightthickness = 0, borderwidth = 0,
                        width = 0, height = 0)
        canvas.grid(row = 0, column = 0, sticky = 'news')
        self.columnconfigure(0, weight = 1)
        self.rowconfigure(0, weight = 1)
        self.vbar = Scrollbar(self, command = canvas.yview)
        canvas['yscrollcommand'] = self.set_vbar

        self.inner = Frame(canvas, name = 'panels')
        self.window = canvas.create_window(0, 0, window = self.inner,
                                           anchor = 'nw')
        self.inner.bind('<Configure>', self.inner_configured)
        canvas.bind('<Configure>', self.canvas_configured)
        self.canvas = canvas

        self.bind_all('<4>', self.wheel, add = 1)
        self.bind_all('<5>', self.wheel, add = 1)

    def set_vbar(self, first, last):
        if float(first) <= 0.0 and float(last) >= 1.0:
            self.vbar.grid_remove()
        else:
            self.vbar.grid(row = 0, column = 1, sticky = 'ns')
        self.vbar.set(first, last)

    def inner_configured(self, event):
        self.canvas.configure(scrollregion = (0, 0, self.inner.winfo_width(),
                                              self.inner.winfo_height()))

    def canvas_configured(self, event):
        self.canvas.itemconfigure(self.window, width = event.width)

    def wheel(self, event):
        # scroll the side bar with the mouse wheel, except over widgets
        # that scroll themselves
        widget = event.widget
        if not isinstance(widget, str):
            widget = str(widget)
        if not widget.startswith(str(self.inner) + '.'):
            return
        if self.tk.call('winfo', 'class', widget) in ('Listbox', 'Text',
                                                      'Canvas'):
            return
        if event.num == 4:
            self.canvas.yview_scroll(-1, 'units')
        else:
            self.canvas.yview_scroll(1, 'units')

    def update_visible(self):
        visible = len(self.docks) > len(self.hidden)
        if visible != self.visible:
            self.visible = visible
            self.visible_cb(visible)

    def repack(self):
        for dock in self.docks:
            dock.frame.pack_forget()
        for dock in self.docks:
            if dock not in self.hidden:
                dock.frame.pack(side = TOP, fill = X)
        self.update_visible()

    def AddPanel(self, dock, index = None):
        if index is None:
            self.docks.append(dock)
        else:
            self.docks.insert(index, dock)
        self.repack()

    def RemovePanel(self, dock):
        if dock in self.hidden:
            self.hidden.remove(dock)
        self.docks.remove(dock)
        self.repack()

    def HidePanel(self, dock):
        if dock not in self.hidden:
            self.hidden.append(dock)
            self.repack()

    def Panels(self):
        # the panels in the side bar, from top to bottom
        return [dock.panel for dock in self.docks]

    def ShowPanel(self, dock):
        if dock in self.hidden:
            self.hidden.remove(dock)
            self.repack()
        # scroll the panel into view
        self.update_idletasks()
        height = self.inner.winfo_height()
        top = dock.frame.winfo_y()
        bottom = top + dock.frame.winfo_height()
        first, last = self.canvas.yview()
        if top < first * height or bottom > last * height:
            self.canvas.yview_moveto(float(top) / max(height, 1))
