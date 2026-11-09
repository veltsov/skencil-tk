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
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Library General Public License for more details.
#
# You should have received a copy of the GNU Library General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA

#
# Change the page size to fit the objects of the document (or only the
# selected ones), with an optional margin around them. All objects are
# moved so that the fitted bounding box starts at (margin, margin) on the
# new page.
#

from tkinter import Label, Button, Frame, Checkbutton, IntVar

import Sketch.Scripting
from Sketch import _, Point, InfinityRect, EmptyRect
from Sketch.Graphics.pagelayout import PageLayout, Portrait
from Sketch.UI.sketchdlg import SKModal
from Sketch.UI.lengthvar import create_length_widgets


def fit_page_to_objects(doc, margin = 0, selected_only = 0):
    # Must be called inside a transaction. Returns false if there is
    # nothing to fit the page to.
    if selected_only:
        if not doc.HasSelection():
            return 0
        rect = doc.SelectionBoundingRect()
    else:
        rect = doc.BoundingRect()
    if rect is None or rect is InfinityRect or rect is EmptyRect:
        # e.g. a selected guide line
        return 0
    width = rect.right - rect.left + 2 * margin
    height = rect.top - rect.bottom + 2 * margin
    if width <= 0 or height <= 0:
        return 0
    offset = Point(margin - rect.left, margin - rect.bottom)
    for layer in doc.Layers():
        if layer.is_GridLayer:
            continue
        if layer.is_GuideLayer:
            # guide lines ignore Translate
            for guide in layer.GetObjects():
                doc.AddUndo(guide.SetPoint(guide.point + offset))
        else:
            doc.AddUndo(layer.Translate(offset))
    doc.SetLayout(PageLayout(width = width, height = height,
                             orientation = Portrait))
    return 1


class FitPageDlg(SKModal):

    title = _("Fit Page to Objects")

    def __init__(self, master, has_selection, **kw):
        self.has_selection = has_selection
        SKModal.__init__(self, master, **kw)

    def build_dlg(self):
        top = self.top

        frame = Frame(top)
        frame.grid(column = 0, row = 0, sticky = 'ew', padx = 4, pady = 4)
        label = Label(frame, text = _("Margin"), anchor = 'e')
        label.pack(side = 'left')
        self.var_margin, entry, scroll, optmenu \
                         = create_length_widgets(top, frame, None)
        self.var_margin.set(0)
        entry.pack(side = 'left', expand = 1, fill = 'x')
        scroll.pack(side = 'left', fill = 'y')
        optmenu.pack(side = 'left')

        self.var_selected = IntVar(top)
        self.var_selected.set(0)
        button = Checkbutton(top, text = _("Selected only"),
                             variable = self.var_selected, anchor = 'w')
        if not self.has_selection:
            button.configure(state = 'disabled')
        button.grid(column = 0, row = 1, sticky = 'ew', padx = 4)

        but_frame = Frame(top)
        but_frame.grid(column = 0, row = 2)
        button = Button(but_frame, text = _("OK"), command = self.ok)
        button.pack(side = 'left', expand = 1)
        button = Button(but_frame, text = _("Cancel"), command = self.cancel)
        button.pack(side = 'right', expand = 1)

    def ok(self, *args):
        self.close_dlg((self.var_margin.get(), self.var_selected.get()))


def fit_page(context):
    doc = context.document
    if doc.BoundingRect() is None:
        context.application.MessageBox(_("Fit Page to Objects"),
                                       _("The document has no objects."))
        return
    result = FitPageDlg(context.application.root,
                        doc.HasSelection()).RunDialog()
    if result is None:
        return
    margin, selected_only = result
    if not fit_page_to_objects(doc, margin, selected_only):
        context.application.MessageBox(_("Fit Page to Objects"),
                                       _("The objects have zero size."))


Sketch.Scripting.AddFunction('fit_page', _("Fit Page to Objects"),
                             fit_page,
                             script_type = Sketch.Scripting.AdvancedScript)
