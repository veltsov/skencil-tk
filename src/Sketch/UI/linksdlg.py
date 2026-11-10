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


# A panel listing the external files linked into the document (EPS
# files and raster images), one row per file, to update, embed or
# relink them.

import os

from tkinter import Scrollbar, Frame, IntVar, Canvas, Label, Entry, \
     Checkbutton
from tkinter import RIGHT, BOTTOM, TOP, X, Y, BOTH, LEFT, W, NW, END

from Sketch import _, SketchError
from Sketch.Base import config
from Sketch.Base.const import EDITED, LAYER, LINKS, CHANGED, SELECTION, \
     SelectSet
from Sketch.Lib import util

from Sketch.UI.tkext import UpdatedButton, UpdatedMenu, MakeCommand
from Sketch.UI.sketchdlg import SketchPanel
from Sketch.UI import skapp, tooltips
from Sketch.UI import skpixmaps
pixmaps = skpixmaps.PixmapTk

epsfiletypes = ((_("Encapsulated PostScript"), ('.eps', '.ps')),
                (_("All Files"), '*'))


def ask_link_filename(main_window, filename, is_eps):
    # Ask for the file to replace the linked (or missing, or embedded,
    # then FILENAME is empty) file FILENAME with. Return the file name or
    # None. Used by the Links panel and the Replace Image/EPS commands.
    directory = os.path.dirname(filename)
    if not filename and not is_eps:
        directory = config.preferences.image_dir
    if not directory or not os.path.isdir(directory):
        directory = main_window.document.meta.directory or os.getcwd()
    if is_eps:
        filetypes = epsfiletypes
        title = _("Replace EPS")
    else:
        filetypes = skapp.bitmapfiletypes
        title = _("Replace Image")
    app = main_window.application
    return app.GetOpenFilename(title = title, filetypes = filetypes,
                               initialdir = directory,
                               initialfile = os.path.basename(filename)) \
                               or None

def relink_objects(main_window, objects, filename, embed = 0,
                   patterns = (), owners = ()):
    # document.RelinkObjects with the errors shown to the user. Return
    # true on success.
    try:
        main_window.document.RelinkObjects(objects, filename, embed = embed,
                                           patterns = patterns,
                                           owners = owners)
    except SketchError as value:
        main_window.application.MessageBox(
            title = _("Replace"),
            message = _("Cannot load %(filename)s:\n%(message)s")
            % {'filename': util.as_display_name(filename), 'message': value})
        return 0
    return 1

def can_select(obj):
    # whether OBJ is in an editable, selectable place of the document
    parent = obj.parent
    while parent is not None and not parent.is_Layer:
        if not parent.is_Group and not parent.is_MaskGroup:
            return 0
        parent = parent.parent
    return parent is not None and parent.CanSelect()


class LinkRow:

    def __init__(self, panel, frame, idx, group):
        self.missing = group.IsMissing()
        # the indicator: an arrow if objects of the row are selected,
        # else a warning if the file is missing
        self.indicator = Label(frame)
        self.foreground = self.indicator.cget('foreground')
        # the kind of the users: mini icons with the number of objects
        self.kind = Frame(frame)
        self.kind_labels = []
        if group.is_eps:
            kinds = [(pixmaps.MiniEps, len(group.objects))]
            description = _("EPS objects: %d") % len(group.objects)
        else:
            # patterns of unused dynamic styles have no owners
            patterns = len(group.pattern_owners) or len(group.patterns)
            kinds = [(pixmaps.MiniImage, len(group.objects)),
                     (pixmaps.MiniPattern, patterns)]
            description = _("Images: %(images)d, pattern fills: %(patterns)d") \
                          % {'images': len(group.objects),
                             'patterns': patterns}
        if self.missing:
            description = _("File not found") + '\n' + description
        for bitmap, count in kinds:
            if count:
                self.kind_labels.append(Label(self.kind, bitmap = bitmap))
                self.kind_labels.append(Label(self.kind, text = str(count)))
        for i, label in enumerate(self.kind_labels):
            # a gap after each count
            label.pack(side = LEFT, padx = (0, 4 * (i % 2)))
            if self.missing:
                label['foreground'] = 'red'
        for widget in [self.kind] + self.kind_labels:
            tooltips.AddDescription(widget, description)
            widget.bind('<ButtonPress-3>',
                        lambda event: panel.popup_context_menu(event, idx))
        self.entry = Entry(frame, width = 40)
        self.entry.insert(0, group.filename)
        self.entry.xview(END)
        self.entry.bind('<Return>', lambda event: panel.relink(idx))
        self.entry.bind('<KP_Enter>', lambda event: panel.relink(idx))
        self.update = UpdatedButton(frame, bitmap = pixmaps.MiniReload,
                                    command = panel.update_link, args = idx)
        tooltips.AddDescription(self.update, _("Update"))
        self.widgets = (self.indicator, self.kind, self.entry, self.update)
        for column, widget in enumerate(self.widgets):
            widget.grid(row = idx, column = column, sticky = 'NEWS')
            widget.bind('<ButtonPress-3>',
                        lambda event: panel.popup_context_menu(event, idx))
        self.SetSelected(0)

    def SetSelected(self, selected):
        if selected:
            self.indicator.configure(bitmap = pixmaps.MiniArrowRight,
                                     foreground = self.foreground)
            tooltips.AddDescription(self.indicator, _("Selected"))
        elif self.missing:
            self.indicator.configure(bitmap = 'warning', foreground = 'red')
            tooltips.AddDescription(self.indicator, _("File not found"))
        else:
            self.indicator.configure(bitmap = '')
            tooltips._tooltips.RemoveDescription(self.indicator)
        self.selected = selected

    def Destroy(self):
        for widget in self.widgets:
            widget.destroy()
        self.widgets = ()


class LinksPanel(SketchPanel):

    title = _("Links")
    receivers = SketchPanel.receivers[:]

    def __init__(self, master, main_window, doc):
        self.rows = []
        self.groups = []
        self.signature = None
        self.context_idx = 0
        self.auto_command = main_window.commands.ToggleAutoReload
        SketchPanel.__init__(self, master, main_window, doc, name = 'linksdlg')
        self.auto_command.Subscribe(CHANGED, self.update_auto)

    def build_dlg(self):
        top = self.top

        frame = Frame(top)
        frame.pack(side = BOTTOM, fill = X)
        button = UpdatedButton(frame, text = _("Update All"),
                               command = self.update_all,
                               sensitivecb = self.main_window.CanReloadAllImages)
        button.pack(side = LEFT, fill = BOTH, expand = 1)
        self.update_all_button = button
        self.var_auto = IntVar(top)
        button = Checkbutton(frame, text = _("Update Automatically"),
                             variable = self.var_auto,
                             command = self.toggle_auto)
        button.pack(side = LEFT, fill = BOTH, expand = 1)
        button = UpdatedButton(frame, text = _("Close"), name = 'close',
                               command = self.close_dlg)
        button.pack(side = LEFT, fill = BOTH, expand = 1)

        list_frame = Frame(top)
        list_frame.pack(side = TOP, expand = 1, fill = BOTH)

        sb_vert = Scrollbar(list_frame, takefocus = 0)
        sb_vert.pack(side = RIGHT, fill = Y)

        self.canvas = canvas = Canvas(list_frame)
        canvas.pack(expand = 1, fill = BOTH)

        self.frame = frame = Frame(canvas, name = 'list')
        frame.grid_columnconfigure(0, minsize = 16)
        frame.grid_columnconfigure(2, weight = 1)
        self.window = canvas.create_window(0, 0, window = frame, anchor = NW)
        # the list follows the width of the panel (the file name column
        # takes the extra space)
        canvas.bind('<Configure>', self.canvas_resized)
        sb_vert['command'] = (canvas, 'yview')
        canvas['yscrollcommand'] = (sb_vert, 'set')

        self.empty_label = Label(frame, text = _("No linked files"))

    def init_from_doc(self):
        self.signature = None
        self.Update()
        self.update_auto()

    receivers.append((LINKS, 'Update'))
    receivers.append((EDITED, 'Update'))
    receivers.append((LAYER, 'Update'))
    def Update(self, *args):
        self.groups = groups = self.document.LinkGroups()
        signature = []
        for group in groups:
            signature.append((group.filename, group.is_eps,
                              group.IsMissing(), len(group.objects),
                              len(group.patterns), len(group.pattern_owners)))
        if signature != self.signature:
            self.signature = signature
            self.create_widget_list()
        self.update_all_button.Update()

    receivers.append((SELECTION, 'update_selected'))
    def update_selected(self, *args):
        # mark the rows of the selected objects (also of objects inside
        # selected groups)
        selected = set()
        def add(obj):
            selected.add(id(obj))
        for obj in self.document.SelectedObjects():
            if obj.is_Compound:
                obj.WalkHierarchy(add)
            else:
                add(obj)
        for row, group in zip(self.rows, self.groups):
            on = 0
            for obj in group.users():
                if id(obj) in selected:
                    on = 1
                    break
            if on != row.selected:
                row.SetSelected(on)

    def create_widget_list(self):
        for row in self.rows:
            row.Destroy()
        self.rows = []
        frame = self.frame
        if self.groups:
            self.empty_label.grid_forget()
            for idx in range(len(self.groups)):
                self.rows.append(LinkRow(self, frame, idx, self.groups[idx]))
        else:
            self.empty_label.grid(row = 0, column = 0, columnspan = 4)
        self.update_selected()
        frame.update_idletasks()
        width = frame.winfo_reqwidth()
        height = frame.winfo_reqheight()
        if not self.canvas.winfo_ismapped() \
           or self.canvas.winfo_width() < width:
            # initial size, or the first rows: show them completely
            # (a size set by the user is kept by the window manager)
            self.canvas['width'] = width
            self.canvas['height'] = min(height, 300)
        self.update_scrollregion()

    def canvas_resized(self, event):
        self.canvas.itemconfigure(self.window, width = event.width)
        self.update_scrollregion()

    def update_scrollregion(self):
        self.frame.update_idletasks()
        self.canvas['scrollregion'] = (0, 0, self.canvas.winfo_width(),
                                       self.frame.winfo_reqheight())

    def update_auto(self, *args):
        self.var_auto.set(not not self.main_window.IsAutoReloading())

    context_menu = None
    def popup_context_menu(self, event, idx):
        self.context_idx = idx
        if self.context_menu is None:
            self.context_menu = UpdatedMenu(self.frame, [], tearoff = 0,
                                            auto_rebuild = self.build_context_menu)
        self.context_menu.Popup(event.x_root, event.y_root)

    def build_context_menu(self):
        idx = self.context_idx
        entries = [
            (_("Replace..."), self.replace, idx),
            (_("Embed"), self.embed, idx, self.can_embed),
            (_("Select Objects"), self.select_objects, idx, self.can_select),
            None,
            (_("Update"), self.update_link, idx),
            ]
        return list(map(MakeCommand, entries))

    def close_dlg(self):
        self.auto_command.Unsubscribe(CHANGED, self.update_auto)
        SketchPanel.close_dlg(self)
        if self.context_menu is not None:
            self.context_menu.destroy()

    #
    #   Actions
    #

    def message(self, title, message):
        self.main_window.application.MessageBox(title = title,
                                                message = message)

    def context_group(self):
        if self.context_idx < len(self.groups):
            return self.groups[self.context_idx]
        return None

    def update_all(self):
        self.main_window.ReloadAllImages()

    def toggle_auto(self):
        self.main_window.ToggleAutoReload()
        self.update_auto()

    def resolve(self, filename):
        filename = os.path.expanduser(filename.strip())
        if filename and not os.path.isabs(filename):
            directory = self.document.meta.directory or os.getcwd()
            filename = os.path.join(directory, filename)
        return filename

    def set_link(self, idx, filename):
        # all users of the file are changed
        group = self.groups[idx]
        if not filename or filename == group.filename:
            return
        if not relink_objects(self.main_window, group.objects, filename,
                              patterns = group.patterns,
                              owners = group.pattern_owners):
            self.signature = None
            self.Update()

    def relink(self, idx):
        if idx < len(self.rows):
            self.set_link(idx, self.resolve(self.rows[idx].entry.get()))

    def replace(self, idx):
        group = self.groups[idx]
        newname = ask_link_filename(self.main_window, group.filename,
                                    group.is_eps)
        if newname:
            self.set_link(idx, newname)

    def update_link(self, idx):
        idx = int(idx)
        group = self.groups[idx]
        if group.IsMissing() and not os.path.exists(group.filename):
            self.message(_("Update"),
                         _("File not found:\n%s")
                         % util.as_display_name(group.filename))
            return
        for data in group.datas():
            data.reload_file(documents = (self.document,))
        self.Update()

    def can_embed(self):
        group = self.context_group()
        if group is not None:
            for obj in group.objects:
                if self.document.CanEmbedObject(obj):
                    return 1
            for pattern in group.patterns:
                if self.document.CanEmbedPattern(pattern):
                    return 1
        return 0

    def embed(self, idx):
        group = self.groups[idx]
        filename = group.filename
        try:
            messages = self.document.EmbedObjects(
                group.objects, patterns = group.patterns,
                owners = group.pattern_owners)
        except SketchError as value:
            self.message(_("Embed"),
                         _("Cannot embed %(filename)s:\n%(message)s")
                         % {'filename': util.as_display_name(filename),
                            'message': value})
            return
        if messages:
            self.message(_("Embed"),
                         _("Warnings from the import filter:\n") + messages)

    def can_select(self):
        group = self.context_group()
        if group is not None:
            for obj in group.users():
                if can_select(obj):
                    return 1
        return 0

    def select_objects(self, idx):
        objects = [obj for obj in self.groups[idx].users()
                   if can_select(obj)]
        if objects:
            self.document.SelectObject(objects, SelectSet)
