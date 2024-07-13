"""Misc widgets used in the GUI."""

# Standard Library
import os
import shlex
import urllib.parse
from gettext import gettext as _

# Third Party Libraries
from gi.repository import GLib, GObject, Gtk, Pango

from lutris.gui.widgets.utils import open_uri

# Lutris Modules
from lutris.util import system
from lutris.util.linux import LINUX_SYSTEM


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
        text=None,
        default_path=None,
        warn_if_non_empty=False,
        warn_if_non_writable_parent=False,
        warn_if_ntfs=False,
        activates_default=False,
        shell_quoting=False,
    ):  # pylint: disable=too-many-arguments
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0, visible=True)
        self.title = title
        self.action = action
        self.warn_if_non_empty = warn_if_non_empty
        self.warn_if_non_writable_parent = warn_if_non_writable_parent
        self.warn_if_ntfs = warn_if_ntfs
        self.shell_quoting = shell_quoting

        self.path_completion = Gtk.ListStore(str)

        self.entry = Gtk.Entry(visible=True)
        self.set_text(text)  # do before set up signal handlers
        self.original_text = self.get_text()
        self.default_path = os.path.expanduser(default_path) if default_path else self.get_path()

        self.entry.set_activates_default(activates_default)
        self.entry.set_completion(self.get_completion())
        self.entry.connect("changed", self.on_entry_changed)
        self.entry.connect("activate", self.on_activate)
        self.entry.connect("focus-out-event", self.on_focus_out)
        self.entry.connect("backspace", self.on_backspace)

        browse_button = Gtk.Button.new_from_icon_name("view-more-horizontal-symbolic", Gtk.IconSize.BUTTON)
        browse_button.show()
        if action == Gtk.FileChooserAction.SELECT_FOLDER:
            browse_button.set_tooltip_text(_("Select a folder"))
        else:
            browse_button.set_tooltip_text(_("Select a file"))
        browse_button.get_style_context().add_class("circular")
        browse_button.connect("clicked", self.on_browse_clicked)

        self.open_button = Gtk.Button.new_from_icon_name("folder-symbolic", Gtk.IconSize.BUTTON)
        self.open_button.show()
        self.open_button.set_tooltip_text(_("Open in file browser"))
        self.open_button.get_style_context().add_class("circular")
        self.open_button.connect("clicked", self.on_open_clicked)
        self.open_button.set_sensitive(bool(self.get_open_directory()))

        box = Gtk.Box(spacing=6, visible=True)
        box.pack_start(self.entry, True, True, 0)
        box.pack_end(self.open_button, False, False, 0)
        box.pack_end(browse_button, False, False, 0)
        self.pack_start(box, False, False, 0)

    def set_text(self, text):
        if self.shell_quoting and text:
            try:
                command_array = shlex.split(self.get_text())
            except ValueError:
                command_array = None  # split can fail due to imbalanced quoted

            if command_array:
                expanded = os.path.expanduser(command_array[0])
                command_array[0] = expanded
                rejoined = shlex.join(command_array)
                self.original_text = rejoined
                self.entry.set_text(rejoined)
                return

        expanded = os.path.expanduser(text) if text else ""
        self.original_text = expanded
        self.entry.set_text(expanded)

    def set_path(self, path):
        if self.shell_quoting:
            try:
                command_array = shlex.split(self.get_text())
            except ValueError:
                command_array = None  # split can fail due to imbalanced quoted

            if command_array:
                command_array[0] = os.path.expanduser(path) if path else ""
                rejoined = shlex.join(command_array)
                self.original_text = rejoined
                self.entry.set_text(rejoined)
                return

        expanded = os.path.expanduser(path) if path else ""
        self.original_text = expanded
        self.entry.set_text(expanded)

    def get_text(self):
        """Return the entry's text. If shell_quoting is one, this is actually a command
        line (with argument quoting) and not a simple path."""
        return self.entry.get_text()

    def get_path(self):
        """Returns the path in the entry; if shell_quoting is set, this extracts
        the command from the text and returns only that."""
        text = self.get_text()
        if self.shell_quoting:
            try:
                command_array = shlex.split(text)
                return command_array[0] if command_array else ""
            except ValueError:
                pass

        return text

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
        default_path = self.get_path() or self.default_path or ""
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

            if target_path and self.shell_quoting:
                try:
                    command_array = shlex.split(self.entry.get_text())
                    text = shlex.join([target_path] + command_array[1:])
                except ValueError:
                    text = shlex.join([target_path])
            else:
                text = target_path

            self.original_text = text
            self.entry.set_text(text)

        file_chooser_dialog.destroy()

    def on_open_clicked(self, _widget):
        path = self.get_open_directory()

        if path:
            open_uri(path)

    def get_open_directory(self):
        path = self.get_path()

        while path and not os.path.isdir(path):
            path = os.path.dirname(path)

        return path

    def on_entry_changed(self, widget):
        """Entry changed callback"""
        self.clear_warnings()

        # If the user isn't editing this entry, we'll apply updates
        # immediately upon any change

        if not self.entry.has_focus():
            if self.normalize_path():
                # We changed the text on commit, so we return here to avoid a double changed signal
                return

        text = self.get_text()
        path = self.get_path()
        self.original_text = text

        if self.warn_if_ntfs and LINUX_SYSTEM.get_fs_type_for_path(path) == "ntfs":
            ntfs_box = Gtk.Box(spacing=6, visible=True)
            warning_image = Gtk.Image(visible=True)
            warning_image.set_from_icon_name("dialog-warning", Gtk.IconSize.DND)
            ntfs_box.add(warning_image)
            ntfs_label = Gtk.Label(visible=True)
            ntfs_label.set_markup(
                _(
                    "<b>Warning!</b> The selected path is located on a drive formatted by Windows.\n"
                    "Games and programs installed on Windows drives <b>don't work</b>."
                )
            )
            ntfs_box.add(ntfs_label)
            self.pack_end(ntfs_box, False, False, 10)
        if self.warn_if_non_empty and os.path.exists(path) and os.listdir(path):
            non_empty_label = Gtk.Label(visible=True)
            non_empty_label.set_markup(
                _("<b>Warning!</b> The selected path " "contains files. Installation will not work properly.")
            )
            self.pack_end(non_empty_label, False, False, 10)
        if self.warn_if_non_writable_parent:
            parent = system.get_existing_parent(path)
            if parent is not None and not os.access(parent, os.W_OK):
                non_writable_destination_label = Gtk.Label(visible=True)
                non_writable_destination_label.set_markup(
                    _("<b>Warning</b> The destination folder " "is not writable by the current user.")
                )
                self.pack_end(non_writable_destination_label, False, False, 10)

        self.open_button.set_sensitive(bool(self.get_open_directory()))

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
        """Detects if the text has changed and updates self.original_text and fires
        the changed signal. Lame, but Gtk.Entry does not always fire its
        changed event when edited!"""
        new_text = self.get_text()
        if self.original_text != new_text:
            self.original_text = new_text
            self.emit("changed")
        return False  # used as idle function

    def normalize_path(self):
        original_path = self.get_path()
        path = original_path.strip("\r\n")

        if path.startswith("file:///"):
            path = urllib.parse.unquote(path[len("file://") :])

        path = os.path.expanduser(path)

        self.update_completion(path)

        if path != original_path:
            self.set_path(path)
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
        super().__init__(label=message, visible=True)
        self.set_line_wrap(True)
        self.set_max_width_chars(22)
        self.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)
        self.set_size_request(width_request, -1)
        self.set_alignment(0, 0.5)
        self.set_justify(Gtk.Justification.LEFT)


class VBox(Gtk.Box):
    def __init__(self, **kwargs):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, margin_top=18, **kwargs)


class EditableGrid(Gtk.Box):
    __gsignals__ = {"changed": (GObject.SIGNAL_RUN_FIRST, None, ())}

    def __init__(self, data, columns):
        self.columns = columns
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=6)

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
        self.scrollable_treelist.set_size_request(-1, 209)
        self.scrollable_treelist.add(self.treeview)
        self.scrollable_treelist.set_shadow_type(Gtk.ShadowType.IN)

        self.pack_start(self.scrollable_treelist, True, True, 0)
        button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        for button in reversed(self.buttons):
            button.set_size_request(80, -1)
            button_box.pack_end(button, False, False, 0)
        self.pack_end(button_box, False, False, 0)
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
