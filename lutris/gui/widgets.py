# -*- coding: utf-8 -*-
"""Misc widgets used in the GUI."""
import os

from gi.repository import Gtk, GObject, GdkPixbuf, GLib, Pango

from lutris.util.log import logger
from lutris.downloader import Downloader
from lutris.util import datapath
from lutris.util.system import reverse_expanduser

PADDING = 5
DEFAULT_BANNER = os.path.join(datapath.get(), 'media/default_banner.png')
DEFAULT_ICON = os.path.join(datapath.get(), 'media/default_icon.png')
UNAVAILABLE_GAME_OVERLAY = os.path.join(datapath.get(),
                                        'media/unavailable.png')
BANNER_SIZE = (184, 69)
BANNER_SMALL_SIZE = (120, 45)
ICON_SIZE = (32, 32)
ICON_SMALL_SIZE = (20, 20)

IMAGE_SIZES = {
    'banner': BANNER_SIZE,
    'banner_small': BANNER_SMALL_SIZE,
    'icon': ICON_SIZE,
    'icon_small': ICON_SMALL_SIZE
}


def get_pixbuf(image, default_image, size):
    """Return a pixbuf from file `image` at `size` or fallback to `default_image`"""
    x, y = size
    if not os.path.exists(image):
        image = default_image
    try:
        pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_size(image, x, y)
    except GLib.GError:
        if default_image:
            pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_size(default_image, x, y)
        else:
            raise
    return pixbuf


def get_runner_icon(runner_name, format='image', size=None):
    icon_path = os.path.join(datapath.get(), 'media/runner_icons',
                             runner_name + '.png')
    if not os.path.exists(icon_path):
        logger.error("Unable to find icon '%s'", icon_path)
        return
    if format == 'image':
        icon = Gtk.Image()
        icon.set_from_file(icon_path)
    elif format == 'pixbuf' and size:
        icon = get_pixbuf(icon_path, None, size)
    else:
        raise ValueError("Invalid arguments")
    return icon


def get_overlay(size):
    x, y = size
    transparent_pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_size(
        UNAVAILABLE_GAME_OVERLAY, x, y
    )
    transparent_pixbuf = transparent_pixbuf.scale_simple(
        x, y, GdkPixbuf.InterpType.NEAREST
    )
    return transparent_pixbuf


def get_pixbuf_for_game(game_slug, icon_type, is_installed=True):
    if icon_type in ("banner", "banner_small"):
        default_icon_path = DEFAULT_BANNER
        icon_path = datapath.get_banner_path(game_slug)
    elif icon_type in ("icon", "icon_small"):
        default_icon_path = DEFAULT_ICON
        icon_path = datapath.get_icon_path(game_slug)
    else:
        logger.error("Invalid icon type '%s'", icon_type)
        return

    size = IMAGE_SIZES[icon_type]

    pixbuf = get_pixbuf(icon_path, default_icon_path, size)
    if not is_installed:
        transparent_pixbuf = get_overlay(size).copy()
        pixbuf.composite(transparent_pixbuf, 0, 0, size[0], size[1],
                         0, 0, 1, 1, GdkPixbuf.InterpType.NEAREST, 100)
        return transparent_pixbuf
    return pixbuf


class DownloadProgressBox(Gtk.VBox):
    """Progress bar used to monitor a file download."""
    __gsignals__ = {
        'complete': (GObject.SignalFlags.RUN_LAST, None,
                     (GObject.TYPE_PYOBJECT,)),
        'cancel': (GObject.SignalFlags.RUN_LAST, None,
                   (GObject.TYPE_PYOBJECT,)),
        'error': (GObject.SignalFlags.RUN_LAST, None,
                  (GObject.TYPE_PYOBJECT,)),
    }

    def __init__(self, params, cancelable=True, downloader=None):
        super(DownloadProgressBox, self).__init__()

        self.downloader = downloader
        self.url = params.get('url')
        self.dest = params.get('dest')
        title = params.get('title', "Downloading {}".format(self.url))

        self.main_label = Gtk.Label(title)
        self.main_label.set_alignment(0, 0)
        self.main_label.set_property('wrap', True)
        self.main_label.set_margin_bottom(10)
        self.main_label.set_max_width_chars(70)
        self.main_label.set_selectable(True)
        self.main_label.set_property('ellipsize', Pango.EllipsizeMode.MIDDLE)
        self.pack_start(self.main_label, True, True, 0)

        progress_box = Gtk.Box()

        self.progressbar = Gtk.ProgressBar()
        self.progressbar.set_margin_top(5)
        self.progressbar.set_margin_bottom(5)
        self.progressbar.set_margin_right(10)
        progress_box.pack_start(self.progressbar, True, True, 0)

        self.cancel_button = Gtk.Button.new_with_mnemonic('_Cancel')
        self.cancel_button.connect('clicked', self.cancel)
        if not cancelable:
            self.cancel_button.set_sensitive(False)
        progress_box.pack_end(self.cancel_button, False, False, 0)

        self.pack_start(progress_box, False, False, 0)

        self.progress_label = Gtk.Label()
        self.progress_label.set_alignment(0, 0)
        self.pack_start(self.progress_label, True, True, 0)

        self.show_all()

    def start(self):
        """Start downloading a file."""
        if not self.downloader:
            try:
                self.downloader = Downloader(self.url, self.dest,
                                             overwrite=True)
            except RuntimeError as ex:
                from lutris.gui.dialogs import ErrorDialog
                ErrorDialog(ex.args[0])
                self.emit('cancel', {})
                return

        timer_id = GLib.timeout_add(100, self._progress)
        self.cancel_button.set_sensitive(True)
        if not self.downloader.state == self.downloader.DOWNLOADING:
            self.downloader.start()
        return timer_id

    def cancel(self, _widget=None):
        """Cancel the current download."""
        if self.downloader:
            self.downloader.cancel()
        self.cancel_button.set_sensitive(False)
        self.emit('cancel', {})

    def _progress(self):
        """Show download progress."""
        progress = min(self.downloader.check_progress(), 1)
        if self.downloader.state in [self.downloader.CANCELLED,
                                     self.downloader.ERROR]:
            self.progressbar.set_fraction(0)
            self._set_text("Download interrupted")
            if self.downloader.state == self.downloader.CANCELLED:
                self.emit('cancel', {})
            return False
        self.progressbar.set_fraction(progress)
        megabytes = 1024 * 1024
        progress_text = (
            "%0.2f / %0.2fMB (%0.2fMB/s), %s remaining" % (
                float(self.downloader.downloaded_size) / megabytes,
                float(self.downloader.full_size) / megabytes,
                float(self.downloader.average_speed) / megabytes,
                self.downloader.time_left
            )
        )
        self._set_text(progress_text)
        if self.downloader.state == self.downloader.COMPLETED:
            self.cancel_button.set_sensitive(False)
            self.emit('complete', {})
            return False
        return True

    def _set_text(self, text):
        markup = u"<span size='10000'>{}</span>".format(text)
        self.progress_label.set_markup(markup)


class FileChooserEntry(Gtk.Box):
    def __init__(self, title='Select file', action=Gtk.FileChooserAction.OPEN,
                 default_path=None):
        """Widget with text entry and button to select file or folder."""
        super(FileChooserEntry, self).__init__()

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
        super(Label, self).__init__(label=message)
        self.set_alignment(0.1, 0.0)
        self.set_padding(PADDING, 0)
        self.set_line_wrap(True)


class VBox(Gtk.VBox):
    def __init__(self):
        GObject.GObject.__init__(self)
        self.set_margin_top(20)


class Dialog(Gtk.Dialog):
    def __init__(self, title=None, parent=None, flags=0, buttons=None):
        super(Dialog, self).__init__(title, parent, flags, buttons)
        self.set_border_width(10)
        self.set_destroy_with_parent(True)


class EditableGrid(Gtk.Grid):
    __gsignals__ = {
        "changed": (GObject.SIGNAL_RUN_FIRST, None, ())
    }

    def __init__(self, data, columns):
        self.columns = columns
        super(EditableGrid, self).__init__()
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
