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

from Sketch import _
from Sketch.UI import tkext, tooltips
from Sketch.UI import skpixmaps
pixmaps = skpixmaps.PixmapTk


#
#	Keyboard traversal
#
# The widgets of the panels do not take the focus with Tk's standard
# traversal (`*SKPanel*takeFocus: 0'). Tab and Shift-Tab cycle through
# the input fields of the panels instead: of all docked panels in the
# side bar, of the panel in a window.

_field_classes = ('Entry', 'Spinbox', 'Text')

def focus_fields(widget):
    # The enabled input fields below WIDGET that are shown, in the order
    # of creation
    fields = []
    for child in widget.winfo_children():
        if not child.winfo_viewable():
            continue
        if child.winfo_class() in _field_classes:
            if str(child.cget('state')) != 'disabled':
                fields.append(child)
        else:
            fields.extend(focus_fields(child))
    return fields

def cycle_focus(fields, current, step):
    # Move the focus from CURRENT to the next (STEP 1) or the previous
    # (STEP -1) of FIELDS
    if not fields:
        return
    names = [str(field) for field in fields]
    if str(current) in names:
        index = (names.index(str(current)) + step) % len(fields)
    else:
        index = step > 0 and 0 or len(fields) - 1
    # tk::TabToWindow also selects the text of an entry
    fields[index].tk.call('tk::TabToWindow', fields[index]._w)


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

        body = Frame(top, name = 'body', class_ = panel.class_name)
        body.pack(side = TOP, fill = 'both', expand = 1)
        top.bind('<Tab>', lambda event: self.traverse(event, 1))
        top.bind('<<PrevWindow>>', lambda event: self.traverse(event, -1))

        self.top = top
        self.body = body

    def traverse(self, event, step):
        cycle_focus(focus_fields(self.body), event.widget, step)
        return 'break'

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

# 9x9 bitmaps for the buttons in the title bar

_bitmaps = {
    'expanded': ('.........',
                 '.........',
                 '#########',
                 '.#######.',
                 '..#####..',
                 '...###...',
                 '....#....',
                 '.........',
                 '.........'),
    'collapsed': ('..#......',
                  '..##.....',
                  '..###....',
                  '..####...',
                  '..#####..',
                  '..####...',
                  '..###....',
                  '..##.....',
                  '..#......'),
    'close': ('##.....##',
              '.##...##.',
              '..##.##..',
              '...###...',
              '...###...',
              '..##.##..',
              '.##...##.',
              '##.....##',
              '.........'),
    # a window popping out of another one
    'undock': ('...######',
               '...#....#',
               '...#....#',
               '######..#',
               '#....#..#',
               '#....####',
               '#....#...',
               '#....#...',
               '######...'),
    }

def _xbm_data(name, rows):
    width = len(rows[0])
    data = []
    for row in rows:
        bits = 0
        for i in range(width):
            if row[i] == '#':
                bits = bits | (1 << i)
        for i in range(0, width, 8):
            data.append('0x%02x' % ((bits >> i) & 0xff))
    return ('#define %s_width %d\n#define %s_height %d\n'
            'static unsigned char %s_bits[] = { %s };\n'
            % (name, width, name, len(rows), name, ', '.join(data)))

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
        image = _images[name] = BitmapImage(master = master,
                                            data = _xbm_data(name,
                                                             _bitmaps[name]),
                                            foreground = title_colors(master)[1])
    return image

def title_button(bar, name, command, tooltip):
    background = title_colors(bar)[0]
    button = Label(bar, image = _image(name, bar), name = name,
                   background = background)
    button.bind('<ButtonRelease-1>', lambda event: command())
    tooltips.AddDescription(button, tooltip)
    return button


class DockContainer:

    # The panel is a frame in the side bar: a title bar with the collapse
    # toggle, the title, the undock and the close buttons, the body and a
    # grip at the bottom to change the height of the body (only for
    # panels with an elastic layout).
    #
    # UNDOCK, if given, is called to move the panel to a window.

    def __init__(self, panel, sidebar, undock = None, **kw):
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
        # the room around the triangle is part of the label and takes the
        # click: the whole height of the bar and a wider label (padx is
        # ignored for an image; the width of an image label is in pixels)
        self.toggle.configure(width = 25)
        self.toggle.pack(side = 'left', fill = 'y')
        label = Label(bar, text = panel.title, anchor = 'w', name = 'title',
                      background = background, foreground = foreground)
        label.pack(side = 'left', fill = X, expand = 1)
        close = title_button(bar, 'close', panel.close_dlg, _("Close"))
        close.pack(side = 'right', padx = 3)
        if undock is not None:
            button = title_button(bar, 'undock', undock, _("Undock"))
            button.pack(side = 'right', padx = 3)
        self.toggle.bind('<ButtonRelease-1>', self.toggle_collapsed)
        # the title moves the panel in the side bar by dragging (only the
        # toggle collapses: a click on the title happens by accident)
        self.drag_from = None
        for widget in (bar, label):
            widget.bind('<ButtonPress-1>', self.title_press)
            widget.bind('<B1-Motion>', self.title_motion)
            widget.bind('<ButtonRelease-1>', self.title_release)
        self.titlebar = bar

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

    drag_threshold = 5

    def title_press(self, event):
        self.drag_from = event.y_root
        self.dragging = 0

    def title_motion(self, event):
        if self.drag_from is None:
            return
        if not self.dragging:
            if abs(event.y_root - self.drag_from) < self.drag_threshold:
                return
            self.dragging = 1
            for widget in self.titlebar.winfo_children() + [self.titlebar]:
                widget['cursor'] = 'fleur'
        self.sidebar.DragMotion(self, event.x_root, event.y_root)

    def title_release(self, event):
        if self.drag_from is None:
            return
        self.drag_from = None
        if self.dragging:
            self.dragging = 0
            for widget in self.titlebar.winfo_children() + [self.titlebar]:
                widget['cursor'] = ''
            self.sidebar.DragEnd(self, event.x_root, event.y_root)

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
        top = self.winfo_toplevel()
        top.bind('<Tab>', lambda event: self.traverse(event, 1), add = 1)
        top.bind('<<PrevWindow>>', lambda event: self.traverse(event, -1),
                 add = 1)

    def set_vbar(self, first, last):
        if float(first) <= 0.0 and float(last) >= 1.0:
            self.vbar.grid_remove()
        else:
            self.vbar.grid(row = 0, column = 1, sticky = 'ns')
        self.vbar.set(first, last)

    def inner_configured(self, event):
        self.canvas.configure(scrollregion = (0, 0, self.inner.winfo_width(),
                                              self.inner.winfo_height()))
        self.keep_top()

    def canvas_configured(self, event):
        self.canvas.itemconfigure(self.window, width = event.width)
        self.keep_top()

    def fits(self):
        return self.inner.winfo_height() <= self.canvas.winfo_height()

    def keep_top(self):
        # when the panels fit, the first one is at the top (the canvas
        # would scroll a region smaller than the window)
        if self.fits() and self.canvas.canvasy(0) != 0:
            self.canvas.yview_moveto(0)

    def scroll(self, units):
        if not self.fits():
            self.canvas.yview_scroll(units, 'units')

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
            self.scroll(-1)
        else:
            self.scroll(1)

    def traverse(self, event, step):
        # Tab in a docked panel: cycle through the fields of the docked
        # panels. Elsewhere in the main window Tk's traversal applies.
        if not str(event.widget).startswith(str(self.inner) + '.'):
            return None
        fields = []
        for dock in self.docks:
            if dock not in self.hidden:
                fields.extend(focus_fields(dock.body))
        cycle_focus(fields, event.widget, step)
        return 'break'

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

    def MovePanel(self, dock, index):
        # move DOCK in front of the panel at INDEX of the panels before
        # the move (len(self.docks): to the end)
        old = self.docks.index(dock)
        if index > old:
            index = index - 1
        if index != old:
            self.docks.remove(dock)
            self.docks.insert(index, dock)
            self.repack()

    # Dragging a panel by its title bar (DockContainer.title_*): a line
    # marks where it goes; near the top and bottom edges the side bar
    # scrolls. Released outside the side bar, the panel stays.

    drag_marker = None
    drag_scroll = None		# the after id of the autoscroll
    drag_pointer = None		# (dock, x_root, y_root) of the last motion
    scroll_zone = 20
    marker_color = 'red'
    marker_width = 6

    def drop_position(self, x_root, y_root):
        # the index in self.docks to move the dragged panel to and the y
        # coordinate of the gap in self.inner, or None outside the side bar
        x = x_root - self.winfo_rootx()
        y = y_root - self.canvas.winfo_rooty()
        if not (0 <= x < self.winfo_width()
                and 0 <= y < self.canvas.winfo_height()):
            return None
        y = y_root - self.inner.winfo_rooty()
        shown = [dock for dock in self.docks if dock not in self.hidden]
        for dock in shown:
            top = dock.frame.winfo_y()
            if y < top + dock.frame.winfo_height() // 2:
                return self.docks.index(dock), top
        last = shown[-1].frame
        return len(self.docks), last.winfo_y() + last.winfo_height()

    def DragMotion(self, dock, x_root, y_root):
        self.drag_pointer = (dock, x_root, y_root)
        if self.drag_marker is None:
            self.drag_marker = Frame(self.inner, name = 'dropmarker',
                                     background = self.marker_color)
        position = self.drop_position(x_root, y_root)
        if position is None:
            self.drag_marker.place_forget()
        else:
            height = self.inner.winfo_height()
            width = self.marker_width
            y = min(max(position[1] - width // 2, 0), height - width)
            self.drag_marker.place(x = 0, y = y, relwidth = 1,
                                   height = width)
            self.drag_marker.lift()
        # scroll when the pointer is near the top or bottom edge
        y = y_root - self.canvas.winfo_rooty()
        if position is not None and (y < self.scroll_zone or
                y > self.canvas.winfo_height() - self.scroll_zone):
            if self.drag_scroll is None:
                self.drag_scroll = self.after(50, self.drag_autoscroll)
        elif self.drag_scroll is not None:
            self.after_cancel(self.drag_scroll)
            self.drag_scroll = None

    def drag_autoscroll(self):
        self.drag_scroll = None
        dock, x_root, y_root = self.drag_pointer
        y = y_root - self.canvas.winfo_rooty()
        self.scroll(-1 if y < self.scroll_zone else 1)
        self.update_idletasks()
        self.DragMotion(dock, x_root, y_root)

    def DragEnd(self, dock, x_root, y_root):
        if self.drag_scroll is not None:
            self.after_cancel(self.drag_scroll)
            self.drag_scroll = None
        if self.drag_marker is not None:
            self.drag_marker.place_forget()
        self.drag_pointer = None
        position = self.drop_position(x_root, y_root)
        if position is not None:
            self.MovePanel(dock, position[0])

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
