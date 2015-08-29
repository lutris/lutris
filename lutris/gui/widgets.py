# -*- coding:Utf-8 -*-
"""Misc widgets used in the GUI."""
import os

from gi.repository import Gtk, GObject, GdkPixbuf, GLib

from lutris.downloader import Downloader
from lutris.util import datapath
from lutris.util.system import reverse_expanduser

PADDING = 5


def get_runner_icon(runner_name, format='image', size=None):
    icon_path = os.path.join(datapath.get(), 'media/runner_icons',
                             runner_name + '.png')
    if format == 'image':
        icon = Gtk.Image()
        icon.set_from_file(icon_path)
    elif format == 'pixbuf' and size:
        icon = GdkPixbuf.Pixbuf.new_from_file_at_size(icon_path,
                                                      size[0], size[1])
    else:
        raise ValueError("Invalid arguments")
    return icon


class DownloadProgressBox(Gtk.VBox):
    """Progress bar used to monitor a file download."""
    __gsignals__ = {
        'complete': (GObject.SignalFlags.RUN_LAST, None,
                     (GObject.TYPE_PYOBJECT,)),
        'cancelrequested': (GObject.SignalFlags.RUN_LAST, None,
                            (GObject.TYPE_PYOBJECT,))
    }

    def __init__(self, params, cancelable=True):
        super(DownloadProgressBox, self).__init__()

        self.downloader = None
        self.url = params['url']
        self.dest = params['dest']
        title = params.get('title', "Downloading {}".format(self.url))

        self.main_label = Gtk.Label(title)
        self.main_label.set_alignment(0, 0)
        self.main_label.set_property('wrap', True)
        self.main_label.set_margin_bottom(10)
        self.main_label.set_selectable(True)
        self.pack_start(self.main_label, True, True, 0)

        progress_box = Gtk.Box()

        self.progressbar = Gtk.ProgressBar()
        self.progressbar.set_margin_bottom(10)
        self.progressbar.set_margin_right(10)
        progress_box.pack_start(self.progressbar, True, True, 0)

        self.cancel_button = Gtk.Button('_Cancel')
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
        try:
            self.downloader = Downloader(self.url, self.dest)
        except RuntimeError as ex:
            from lutris.gui.dialogs import ErrorDialog
            ErrorDialog(ex.message)
            self.emit('cancelrequested', {})
            return
        timer_id = GLib.timeout_add(100, self.progress)
        self.cancel_button.set_sensitive(True)
        self.downloader.start()
        return timer_id

    def progress(self):
        """Show download progress."""
        progress = min(self.downloader.progress, 1)
        if self.downloader.cancelled:
            self.progressbar.set_fraction(0)
            self.set_text("Download cancelled")
            self.emit('cancelrequested', {})
            return False
        self.progressbar.set_fraction(progress)
        megabytes = 1024 * 1024
        progress_text = (
            "%0.2f / %0.2fMB (%0.2fMB/s), %d seconds remaining" % (
                float(self.downloader.downloaded_bytes) / megabytes,
                float(self.downloader.total_bytes) / megabytes,
                float(self.downloader.speed) / megabytes,
                self.downloader.time_remaining
            )
        )
        self.set_text(progress_text)
        self.progressbar.set_fraction(progress)
        if progress >= 1.0:
            self.cancel_button.set_sensitive(False)
            self.emit('complete', {})
            return False
        return True

    def cancel(self, _widget):
        """Cancel the current download."""
        if self.downloader:
            self.downloader.cancel()
            self.cancel_button.set_sensitive(False)

    def set_text(self, text):
        markup = u"<span size='10000'>{}</span>".format(text)
        self.progress_label.set_markup(markup)


class FileChooserEntry(Gtk.Box):
    def __init__(self, action=Gtk.FileChooserAction.SELECT_FOLDER,
                 default=None):
        super(FileChooserEntry, self).__init__()

        self.entry = Gtk.Entry()
        if default:
            self.entry.set_text(default)
        self.pack_start(self.entry, True, True, 0)

        self.path_completion = Gtk.ListStore(str)
        completion = Gtk.EntryCompletion()
        completion.set_model(self.path_completion)
        completion.set_text_column(0)
        self.entry.set_completion(completion)
        self.entry.connect("changed", self.entry_changed)

        self.file_chooser_dlg = Gtk.FileChooserDialog(
            title="Select folder",
            transient_for=None,
            action=action
        )

        self.file_chooser_dlg.add_buttons(
            '_Cancel', Gtk.ResponseType.CLOSE,
            '_OK', Gtk.ResponseType.OK
        )
        if default:
            self.file_chooser_dlg.set_current_folder(
                os.path.expanduser(default)
            )

        button = Gtk.Button()
        button.set_label("Browse...")
        button.connect('clicked', self.open_filechooser, default)
        self.add(button)

    def open_filechooser(self, widget, default):
        if default:
            self.file_chooser_dlg.set_current_folder(
                os.path.expanduser(default)
            )
        self.file_chooser_dlg.connect('response', self.select_file)
        self.file_chooser_dlg.run()

    def entry_changed(self, widget):
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

    def select_file(self, dialog, response):
        if response == Gtk.ResponseType.OK:
            target_path = dialog.get_filename()
            if target_path:
                self.file_chooser_dlg.set_current_folder(target_path)
                self.entry.set_text(reverse_expanduser(target_path))
        dialog.hide()

    def get_text(self):
        return self.entry.get_text()


class Label(Gtk.Label):
    """Standardised label for config vboxes."""
    def __init__(self, message=None):
        """Custom init of label"""
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
