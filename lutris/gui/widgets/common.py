# -*- coding: utf-8 -*-
"""Misc widgets used in the GUI."""
import os

from gi.repository import Gtk, GObject

from lutris.util.system import reverse_expanduser


class FileChooserEntry(Gtk.Box):
    def __init__(self, title='Select file', action=Gtk.FileChooserAction.OPEN,
                 default_path=None):
        """Widget with text entry and button to select file or folder."""
        super().__init__()

        self.entry = Gtk.Entry()
        if default_path:
            self.entry.set_text(default_path)
        self.pack_start(self.entry, True, True, 0)

        self.path_completion = Gtk.ListStore(str)
        completion = Gtk.EntryCompletion()
        completion.set_model(self.path_completion)
        completion.set_text_column(0)
        self.entry.set_completion(completion)
        self.entry.connect("changed", self._entry_changed)

        self.file_chooser_dlg = Gtk.FileChooserDialog(
            title=title,
            transient_for=None,
            action=action
        )

        self.file_chooser_dlg.add_buttons(
            '_Cancel', Gtk.ResponseType.CLOSE,
            '_OK', Gtk.ResponseType.OK
        )

        self.file_chooser_dlg.set_create_folders(True)

        if default_path:
            self.file_chooser_dlg.set_current_folder(
                os.path.expanduser(default_path)
            )

        button = Gtk.Button()
        button.set_label("Browse...")
        button.connect('clicked', self._open_filechooser, default_path)
        self.add(button)

    def get_text(self):
        return self.entry.get_text()

    def _open_filechooser(self, widget, default_path):
        if default_path:
            self.file_chooser_dlg.set_current_folder(
                os.path.expanduser(default_path)
            )
        self.file_chooser_dlg.connect('response', self._select_file)
        self.file_chooser_dlg.run()

    def _entry_changed(self, widget):
        self.path_completion.clear()
        current_path = widget.get_text()
        if not current_path:
            current_path = "/"
        if not os.path.exists(current_path):
            current_path, filefilter = os.path.split(current_path)
        else:
            filefilter = None
        if os.path.isdir(current_path):
            index = 0
            for filename in sorted(os.listdir(current_path)):
                if filename.startswith("."):
                    continue
                if filefilter is not None \
                        and not filename.startswith(filefilter):
                    continue
                self.path_completion.append(
                    [os.path.join(current_path, filename)]
                )
                index += 1
                if index > 15:
                    break

    def _select_file(self, dialog, response):
        if response == Gtk.ResponseType.OK:
            target_path = dialog.get_filename()
            if target_path:
                self.file_chooser_dlg.set_current_folder(target_path)
                self.entry.set_text(reverse_expanduser(target_path))
        dialog.hide()


class Label(Gtk.Label):
    """Standardised label for config vboxes."""
    def __init__(self, message=None):
        """Custom init of label."""
        super().__init__(label=message)
        self.set_alignment(0.1, 0.0)
        self.set_padding(5, 0)
        self.set_line_wrap(True)


class VBox(Gtk.Box):
    def __init__(self, **kwargs):
        super().__init__(
            orientation=Gtk.Orientation.VERTICAL,
            margin_top=20,
            **kwargs
        )


class EditableGrid(Gtk.Grid):
    __gsignals__ = {
        "changed": (GObject.SIGNAL_RUN_FIRST, None, ())
    }

    def __init__(self, data, columns):
        self.columns = columns
        super().__init__()
        self.set_column_homogeneous(True)
        self.set_row_homogeneous(True)
        self.set_row_spacing(10)
        self.set_column_spacing(10)

        self.liststore = Gtk.ListStore(str, str)
        for item in data:
            self.liststore.append(list(item))

        self.treeview = Gtk.TreeView.new_with_model(self.liststore)
        self.treeview.set_grid_lines(Gtk.TreeViewGridLines.BOTH)
        for i, column_title in enumerate(self.columns):
            renderer = Gtk.CellRendererText()
            renderer.set_property("editable", True)
            renderer.connect("edited", self.on_text_edited, i)

            column = Gtk.TreeViewColumn(column_title, renderer, text=i)
            column.set_resizable(True)
            column.set_min_width(100)
            column.set_sort_column_id(0)
            self.treeview.append_column(column)

        self.buttons = []
        self.add_button = Gtk.Button("Add")
        self.buttons.append(self.add_button)
        self.add_button.connect("clicked", self.on_add)

        self.delete_button = Gtk.Button("Delete")
        self.buttons.append(self.delete_button)
        self.delete_button.connect("clicked", self.on_delete)

        self.scrollable_treelist = Gtk.ScrolledWindow()
        self.scrollable_treelist.set_vexpand(True)
        self.scrollable_treelist.add(self.treeview)

        self.attach(self.scrollable_treelist, 0, 0, 5, 5)
        self.attach(self.add_button, 5 - len(self.buttons), 6, 1, 1)
        for i, button in enumerate(self.buttons[1:]):
            self.attach_next_to(button, self.buttons[i], Gtk.PositionType.RIGHT, 1, 1)
        self.show_all()

    def on_add(self, widget):
        self.liststore.append(["", ""])
        self.emit('changed')

    def on_delete(self, widget):
        selection = self.treeview.get_selection()
        liststore, iter = selection.get_selected()
        self.liststore.remove(iter)
        self.emit('changed')

    def on_text_edited(self, widget, path, text, field):
        self.liststore[path][field] = text
        self.emit('changed')

    def get_data(self):
        model_data = []
        for row in self.liststore:
            model_data.append([col for col in row])
        return model_data
