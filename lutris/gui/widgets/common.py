"""Misc widgets used in the GUI."""
# Standard Library
import os
import urllib.parse
from gettext import gettext as _

# Third Party Libraries
from gi.repository import GLib, GObject, Gtk, Pango

# Lutris Modules
from lutris.util import system
from lutris.util.linux import LINUX_SYSTEM
from lutris.util.log import logger


class SlugEntry(Gtk.Entry, Gtk.Editable):

    def do_insert_text(self, new_text, length, position):
        """Filter inserted characters to only accept alphanumeric and dashes"""
        new_text = "".join([c for c in new_text if c.isalnum() or c == "-"]).lower()
        length = len(new_text)
        self.get_buffer().insert_text(position, new_text, length)
        return position + length


class NumberEntry(Gtk.Entry, Gtk.Editable):

    def do_insert_text(self, new_text, length, position):
        """Filter inserted characters to only accept numbers"""
        new_text = "".join([c for c in new_text if c.isnumeric()])
        if new_text:
            self.get_buffer().insert_text(position, new_text, length)
            return position + length
        return position


class FileChooserEntry(Gtk.Box):

    """Editable entry with a file picker button"""

    max_completion_items = 15  # Maximum number of items to display in the autocompletion dropdown.

    __gsignals__ = {
        "changed": (GObject.SIGNAL_RUN_FIRST, None, ()),
    }

    def __init__(
        self,
        title=_("Select file"),
        action=Gtk.FileChooserAction.OPEN,
        path=None,
        default_path=None,
        warn_if_non_empty=False,
        warn_if_ntfs=False,
        activates_default=False,
    ):
        super().__init__(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=0,
            visible=True
        )
        self.title = title
        self.action = action
        self.path = os.path.expanduser(path) if path else None
        self.default_path = os.path.expanduser(default_path) if default_path else path
        self.warn_if_non_empty = warn_if_non_empty
        self.warn_if_ntfs = warn_if_ntfs

        self.path_completion = Gtk.ListStore(str)

        self.entry = Gtk.Entry(visible=True)
        self.entry.set_activates_default(activates_default)
        self.entry.set_completion(self.get_completion())
        self.entry.connect("changed", self.on_entry_changed)
        self.entry.connect("activate", self.on_activate)
        self.entry.connect("focus-out-event", self.on_focus_out)
        self.entry.connect("backspace", self.on_backspace)

        if path:
            self.entry.set_text(path)

        browse_button = Gtk.Button(_("Browse..."), visible=True)
        browse_button.connect("clicked", self.on_browse_clicked)

        box = Gtk.Box(spacing=6, visible=True)
        box.pack_start(self.entry, True, True, 0)
        box.add(browse_button)
        self.pack_start(box, False, False, 0)

    def set_text(self, path):
        self.path = os.path.expanduser(path)
        self.entry.set_text(self.path)

    def get_text(self):
        """Return the entry's text"""
        return self.entry.get_text()

    def get_filename(self):
        """Deprecated"""
        logger.warning("Just use get_text")
        return self.get_text()

    def get_completion(self):
        """Return an EntryCompletion widget"""
        completion = Gtk.EntryCompletion()
        completion.set_model(self.path_completion)
        completion.set_text_column(0)
        return completion

    def get_filechooser_dialog(self):
        """Return an instance of a FileChooserNative configured for this widget"""
        dialog = Gtk.FileChooserNative.new(self.title, self.get_toplevel(), self.action, _("_OK"), _("_Cancel"))
        dialog.set_create_folders(True)
        dialog.set_current_folder(self.get_default_folder())
        return dialog

    def get_default_folder(self):
        """Return the default folder for the file picker"""
        default_path = self.path or self.default_path or ""
        if not default_path or not system.path_exists(default_path):
            current_entry = self.get_text()
            if system.path_exists(current_entry):
                default_path = current_entry
        if not os.path.isdir(default_path):
            default_path = os.path.dirname(default_path)
        return os.path.expanduser(default_path or "~")

    def on_browse_clicked(self, _widget):
        """Browse button click callback"""
        file_chooser_dialog = self.get_filechooser_dialog()
        response = file_chooser_dialog.run()

        if response == Gtk.ResponseType.ACCEPT:
            target_path = file_chooser_dialog.get_filename()
            if target_path:
                self.entry.set_text(system.reverse_expanduser(target_path))

        file_chooser_dialog.destroy()

    def on_entry_changed(self, widget):
        """Entry changed callback"""
        self.clear_warnings()
        path = widget.get_text()
        if not path:
            return

        # If the user isn't editing this entry, we'll apply updates
        # immediately upon any change

        if not self.entry.has_focus():
            if self.normalize_path():
                # We changed the text on commit, so we return here to avoid a double changed signal
                return

        self.path = path

        if self.warn_if_ntfs and LINUX_SYSTEM.get_fs_type_for_path(path) == "ntfs":
            ntfs_box = Gtk.Box(spacing=6, visible=True)
            warning_image = Gtk.Image(visible=True)
            warning_image.set_from_icon_name("dialog-warning", Gtk.IconSize.DND)
            ntfs_box.add(warning_image)
            ntfs_label = Gtk.Label(visible=True)
            ntfs_label.set_markup(_(
                "<b>Warning!</b> The selected path is located on a drive formatted by Windows.\n"
                "Games and programs installed on Windows drives usually <b>don't work</b>."
            ))
            ntfs_box.add(ntfs_label)
            self.pack_end(ntfs_box, False, False, 10)
        if self.warn_if_non_empty and os.path.exists(path) and os.listdir(path):
            non_empty_label = Gtk.Label(visible=True)
            non_empty_label.set_markup(_(
                "<b>Warning!</b> The selected path "
                "contains files. Installation might not work properly."
            ))
            self.pack_end(non_empty_label, False, False, 10)
        parent = system.get_existing_parent(path)
        if parent is not None and not os.access(parent, os.W_OK):
            non_writable_destination_label = Gtk.Label(visible=True)
            non_writable_destination_label.set_markup(_(
                "<b>Warning</b> The destination folder "
                "is not writable by the current user."
            ))
            self.pack_end(non_writable_destination_label, False, False, 10)

        self.emit("changed")

    def on_activate(self, _widget):
        self.normalize_path()
        self.detect_changes()

    def on_focus_out(self, _widget, _event):
        self.normalize_path()
        self.detect_changes()

    def on_backspace(self, _widget):
        GLib.idle_add(self.detect_changes)

    def detect_changes(self):
        """Detects if the text has changed and updates self.path and fires
        the changed signal. Lame, but Gtk.Entry does not always fire its
        changed event when edited!"""
        new_path = self.get_text()
        if self.path != new_path:
            self.path = new_path
            self.emit("changed")
        return False  # used as idle function

    def normalize_path(self):
        original_path = self.get_text()
        path = original_path.strip("\r\n")

        if path.startswith('file:///'):
            path = urllib.parse.unquote(path[len('file://'):])

        path = os.path.expanduser(path)

        self.update_completion(path)

        if path != original_path:
            self.entry.set_text(path)
            return True

        return False

    def update_completion(self, current_path):
        """Update the auto-completion widget with the current path"""
        self.path_completion.clear()

        if not os.path.exists(current_path):
            current_path, filefilter = os.path.split(current_path)
        else:
            filefilter = None

        if os.path.isdir(current_path):
            index = 0
            for filename in sorted(os.listdir(current_path)):
                if filename.startswith("."):
                    continue
                if filefilter is not None and not filename.startswith(filefilter):
                    continue
                self.path_completion.append([os.path.join(current_path, filename)])
                index += 1
                if index > self.max_completion_items:
                    break

    def clear_warnings(self):
        """Delete all the warning labels from the container"""
        for index, child in enumerate(self.get_children()):
            if index > 0:
                child.destroy()


class Label(Gtk.Label):
    """Standardised label for config vboxes."""

    def __init__(self, message=None, width_request=230):
        """Custom init of label."""
        super().__init__(label=message)
        self.set_line_wrap(True)
        self.set_max_width_chars(22)
        self.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)
        self.set_size_request(width_request, -1)
        self.set_alignment(0, 0.5)
        self.set_justify(Gtk.Justification.LEFT)


class VBox(Gtk.Box):
    def __init__(self, **kwargs):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, margin_top=18, **kwargs)


class EditableGrid(Gtk.Grid):
    __gsignals__ = {"changed": (GObject.SIGNAL_RUN_FIRST, None, ())}

    def __init__(self, data, columns):
        self.columns = columns
        super().__init__()
        self.set_column_homogeneous(True)
        self.set_row_homogeneous(True)
        self.set_row_spacing(6)
        self.set_column_spacing(6)

        self.liststore = Gtk.ListStore(str, str)
        for item in data:
            self.liststore.append([str(value) for value in item])

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
        self.add_button = Gtk.Button(_("Add"))
        self.buttons.append(self.add_button)
        self.add_button.connect("clicked", self.on_add)

        self.delete_button = Gtk.Button(_("Delete"))
        self.buttons.append(self.delete_button)
        self.delete_button.connect("clicked", self.on_delete)

        self.scrollable_treelist = Gtk.ScrolledWindow()
        self.scrollable_treelist.set_vexpand(True)
        self.scrollable_treelist.add(self.treeview)
        self.scrollable_treelist.set_shadow_type(Gtk.ShadowType.IN)

        self.attach(self.scrollable_treelist, 0, 0, 5, 5)
        self.attach(self.add_button, 5 - len(self.buttons), 6, 1, 1)
        for i, button in enumerate(self.buttons[1:]):
            self.attach_next_to(button, self.buttons[i], Gtk.PositionType.RIGHT, 1, 1)
        self.show_all()

    def on_add(self, widget):  # pylint: disable=unused-argument
        self.liststore.append(["", ""])
        row_position = len(self.liststore) - 1
        self.treeview.set_cursor(row_position, None, False)
        self.treeview.scroll_to_cell(row_position, None, False, 0.0, 0.0)
        self.emit("changed")

    def on_delete(self, widget):  # pylint: disable=unused-argument
        selection = self.treeview.get_selection()
        _, iteration = selection.get_selected()
        self.liststore.remove(iteration)
        self.emit("changed")

    def on_text_edited(self, widget, path, text, field):  # pylint: disable=unused-argument
        self.liststore[path][field] = text.strip()  # pylint: disable=unsubscriptable-object
        self.emit("changed")

    def get_data(self):  # pylint: disable=arguments-differ
        model_data = []
        for row in self.liststore:  # pylint: disable=not-an-iterable
            model_data.append(row)
        return model_data
