"""Commonly used dialogs"""
# pylint: disable=no-member
import os
from gi.repository import GLib, Gtk, GObject

from lutris import api, pga, runtime, settings
from lutris.gui.widgets.download_progress import DownloadProgressBox
from lutris.util import datapath
from lutris.util.log import logger
from lutris.util.system import open_uri
from lutris.util.log import logger


class GtkBuilderDialog(GObject.Object):

    def __init__(self, parent=None, **kwargs):
        super(GtkBuilderDialog, self).__init__()
        ui_filename = os.path.join(datapath.get(), 'ui',
                                   self.glade_file)
        if not os.path.exists(ui_filename):
            raise ValueError("ui file does not exists: %s" % ui_filename)

        self.builder = Gtk.Builder()
        self.builder.add_from_file(ui_filename)
        self.dialog = self.builder.get_object(self.dialog_object)

        self.builder.connect_signals(self)
        if parent:
            self.dialog.set_transient_for(parent)
        self.dialog.show_all()
        self.dialog.connect("delete-event", lambda *x: x[0].destroy())
        self.initialize(**kwargs)

    def initialize(self, **kwargs):
        pass

    def on_close(self, *args):
        self.dialog.destroy()

    def on_response(self, widget, response):
        if response == Gtk.ResponseType.DELETE_EVENT:
            try:
                self.dialog.hide()
            except AttributeError:
                pass


class AboutDialog(GtkBuilderDialog):
    glade_file = 'about-dialog.ui'
    dialog_object = "about_dialog"

    def initialize(self):
        self.dialog.set_version(settings.VERSION)


class NoticeDialog(Gtk.MessageDialog):
    """Display a message to the user."""
    def __init__(self, message, parent=None):
        super(NoticeDialog, self).__init__(buttons=Gtk.ButtonsType.OK, parent=parent)
        self.set_markup(message)
        self.run()
        self.destroy()


class ErrorDialog(Gtk.MessageDialog):
    """Display an error message."""
    def __init__(self, message, secondary=None, parent=None):
        super(ErrorDialog, self).__init__(buttons=Gtk.ButtonsType.OK, parent=parent)
        self.set_markup(message)
        if secondary:
            self.format_secondary_text(secondary)
        self.run()
        self.destroy()


class QuestionDialog(Gtk.MessageDialog):
    """Ask the user a question."""
    YES = Gtk.ResponseType.YES
    NO = Gtk.ResponseType.NO

    def __init__(self, dialog_settings):
        super().__init__(
            message_type=Gtk.MessageType.QUESTION,
            buttons=Gtk.ButtonsType.YES_NO
        )
        self.set_markup(dialog_settings['question'])
        self.set_title(dialog_settings['title'])
        self.result = self.run()
        self.destroy()


class DirectoryDialog(Gtk.FileChooserDialog):
    """Ask the user to select a directory."""
    def __init__(self, message, parent=None):
        super(DirectoryDialog, self).__init__(
            title=message,
            action=Gtk.FileChooserAction.SELECT_FOLDER,
            buttons=('_Cancel', Gtk.ResponseType.CLOSE,
                     '_OK', Gtk.ResponseType.OK),
            parent=parent
        )
        self.result = self.run()
        self.folder = self.get_current_folder()
        self.destroy()


class FileDialog(Gtk.FileChooserDialog):
    """Ask the user to select a file."""
    def __init__(self, message=None, default_path=None):
        self.filename = None
        if not message:
            message = "Please choose a file"
        super(FileDialog, self).__init__(
            message, None, Gtk.FileChooserAction.OPEN,
            ('_Cancel', Gtk.ResponseType.CANCEL,
             '_OK', Gtk.ResponseType.OK)
        )
        if default_path and os.path.exists(default_path):
            self.set_current_folder(default_path)
        self.set_local_only(False)
        response = self.run()
        if response == Gtk.ResponseType.OK:
            self.filename = self.get_filename()

        self.destroy()


class DownloadDialog(Gtk.Dialog):
    """Dialog showing a download in progress."""
    def __init__(self, url=None, dest=None, title=None, label=None,
                 downloader=None):
        Gtk.Dialog.__init__(self, title or "Downloading file")
        self.set_size_request(485, 104)
        self.set_border_width(12)
        params = {'url': url,
                  'dest': dest,
                  'title': label or "Downloading %s" % url}
        self.download_box = DownloadProgressBox(params, downloader=downloader)

        self.download_box.connect('complete', self.download_complete)
        self.download_box.connect('cancel', self.download_cancelled)
        self.connect('response', self.on_response)

        self.get_content_area().add(self.download_box)
        self.show_all()
        self.download_box.start()

    def download_complete(self, _widget, _data):
        self.response(Gtk.ResponseType.OK)
        self.destroy()

    def download_cancelled(self, _widget, data):
        self.response(Gtk.ResponseType.CANCEL)
        self.destroy()

    def on_response(self, dialog, response):
        if response == Gtk.ResponseType.DELETE_EVENT:
            self.download_box.downloader.cancel()
            self.destroy()


class InstallOrPlayDialog(Gtk.Dialog):
    def __init__(self, game_name):
        Gtk.Dialog.__init__(self, "%s is already installed" % game_name)
        self.connect("delete-event", lambda *x: self.destroy())

        self.action = None
        self.action_confirmed = False

        self.set_size_request(320, 120)
        self.set_border_width(12)
        vbox = Gtk.VBox(spacing=6)
        self.get_content_area().add(vbox)

        play_button = Gtk.RadioButton.new_with_label_from_widget(None, "Launch game")
        play_button.connect('toggled', self.on_button_toggled, "play")
        vbox.pack_start(play_button, False, False, 0)
        install_button = Gtk.RadioButton.new_from_widget(play_button)
        install_button.set_label("Install the game again")
        install_button.connect('toggled', self.on_button_toggled, "install")
        vbox.pack_start(install_button, False, False, 0)

        confirm_button = Gtk.Button("OK")
        confirm_button.connect('clicked', self.on_confirm)
        vbox.pack_start(confirm_button, False, False, 0)

        self.show_all()
        self.run()

    def on_button_toggled(self, button, action):
        self.action = action

    def on_confirm(self, button):
        self.action_confirmed = True
        self.destroy()


class RuntimeUpdateDialog(Gtk.Dialog):
    """Dialog showing the progress of ongoing runtime update."""
    def __init__(self, parent=None):
        Gtk.Dialog.__init__(self, "Runtime updating", parent=parent)
        self.set_size_request(360, 104)
        self.set_border_width(12)
        progress_box = Gtk.Box()
        self.progressbar = Gtk.ProgressBar()
        self.progressbar.set_margin_top(40)
        self.progressbar.set_margin_bottom(40)
        self.progressbar.set_margin_right(20)
        self.progressbar.set_margin_left(20)
        progress_box.pack_start(self.progressbar, True, True, 0)
        self.get_content_area().add(progress_box)
        GLib.timeout_add(200, self.on_runtime_check)
        self.show_all()

    def on_runtime_check(self, *args, **kwargs):
        self.progressbar.pulse()
        if not runtime.is_updating():
            self.response(Gtk.ResponseType.OK)
            self.destroy()
            return False
        return True


class PgaSourceDialog(GtkBuilderDialog):
    glade_file = 'dialog-pga-sources.ui'
    dialog_object = 'pga_dialog'

    def __init__(self):
        super(PgaSourceDialog, self).__init__()

        # GtkBuilder Objects
        self.sources_selection = self.builder.get_object("sources_selection")
        self.sources_treeview = self.builder.get_object("sources_treeview")
        self.remove_source_button = self.builder.get_object(
            "remove_source_button"
        )

        # Treeview setup
        self.sources_liststore = Gtk.ListStore(str)
        renderer = Gtk.CellRendererText()
        renderer.set_padding(4, 10)
        uri_column = Gtk.TreeViewColumn("URI", renderer, text=0)
        self.sources_treeview.append_column(uri_column)
        self.sources_treeview.set_model(self.sources_liststore)
        sources = pga.read_sources()
        for index, source in enumerate(sources):
            self.sources_liststore.append((source, ))

        self.remove_source_button.set_sensitive(False)
        self.dialog.show_all()

    @property
    def sources_list(self):
        return [source[0] for source in self.sources_liststore]

    def on_apply(self, widget, data=None):
        pga.write_sources(self.sources_list)
        self.on_close(widget, data)

    def on_add_source_button_clicked(self, widget, data=None):
        chooser = Gtk.FileChooserDialog(
            "Select directory", self.dialog,
            Gtk.FileChooserAction.SELECT_FOLDER,
            ('_Cancel', Gtk.ResponseType.CANCEL,
             '_OK', Gtk.ResponseType.OK)
        )
        chooser.set_local_only(False)
        response = chooser.run()
        if response == Gtk.ResponseType.OK:
            uri = chooser.get_uri()
            if uri not in self.sources_list:
                self.sources_liststore.append((uri, ))
        chooser.destroy()

    def on_remove_source_button_clicked(self, widget, data=None):
        """Remove a source."""
        (model, treeiter) = self.sources_selection.get_selected()
        if treeiter:
            # TODO : Add confirmation
            model.remove(treeiter)

    def on_sources_selection_changed(self, widget, data=None):
        """Set sentivity of remove source button."""
        (model, treeiter) = self.sources_selection.get_selected()
        self.remove_source_button.set_sensitive(treeiter is not None)


class ClientLoginDialog(GtkBuilderDialog):
    glade_file = 'dialog-lutris-login.ui'
    dialog_object = 'lutris-login'
    __gsignals__ = {
        'connected': (GObject.SignalFlags.RUN_LAST, None,
                      (GObject.TYPE_PYOBJECT,)),
        'cancel': (GObject.SignalFlags.RUN_LAST, None,
                   (GObject.TYPE_PYOBJECT,))
    }

    def __init__(self, parent):
        super(ClientLoginDialog, self).__init__(parent=parent)

        self.parent = parent
        self.username_entry = self.builder.get_object('username_entry')
        self.password_entry = self.builder.get_object('password_entry')

        cancel_button = self.builder.get_object('cancel_button')
        cancel_button.connect('clicked', self.on_close)
        connect_button = self.builder.get_object('connect_button')
        connect_button.connect('clicked', self.on_connect)

    def get_credentials(self):
        username = self.username_entry.get_text()
        password = self.password_entry.get_text()
        return (username, password)

    def on_username_entry_activate(self, widget):
        if all(self.get_credentials()):
            self.on_connect(None)
        else:
            self.password_entry.grab_focus()

    def on_password_entry_activate(self, widget):
        if all(self.get_credentials()):
            self.on_connect(None)
        else:
            self.username_entry.grab_focus()

    def on_connect(self, widget):
        username, password = self.get_credentials()
        token = api.connect(username, password)
        if not token:
            NoticeDialog("Login failed", parent=self.parent)
        else:
            self.emit('connected', username)
            self.dialog.destroy()


class ClientUpdateDialog(GtkBuilderDialog):
    glade_file = 'dialog-client-update.ui'
    dialog_object = "client_update_dialog"

    def on_open_downloads_clicked(self, _widget):
        open_uri("http://lutris.net")


class NoInstallerDialog(Gtk.MessageDialog):
    MANUAL_CONF = 1
    NEW_INSTALLER = 2
    EXIT = 4

    def __init__(self, parent=None):
        Gtk.MessageDialog.__init__(self, parent, 0, Gtk.MessageType.ERROR,
                                   Gtk.ButtonsType.NONE,
                                   "Unable to install the game")
        self.format_secondary_text("No installer is available for this game")
        self.add_buttons("Configure manually", self.MANUAL_CONF,
                         "Write installer", self.NEW_INSTALLER,
                         "Close", self.EXIT)
        self.result = self.run()
        self.destroy()


class DontShowAgainDialog(Gtk.MessageDialog):
    """Display a message to the user and offer an option not to display this dialog again."""
    def __init__(self, setting, message, secondary_message=None, parent=None):
        super().__init__(type=Gtk.MessageType.WARNING, buttons=Gtk.ButtonsType.OK, parent=parent)

        if settings.read_setting(setting) == 'True':
            logger.info("Dialog %s dismissed by user", setting)
            self.destroy()
            return

        self.set_border_width(12)
        self.set_markup("<b>%s</b>" % message)
        if secondary_message:
            self.props.secondary_use_markup = True
            self.props.secondary_text = secondary_message

        dont_show_checkbutton = Gtk.CheckButton("Do not display this message again.")
        dont_show_checkbutton.props.halign = Gtk.Align.CENTER
        dont_show_checkbutton.show()

        content_area = self.get_content_area()
        # content_area.props.halign = Gtk.Align.CENTER
        content_area.pack_start(dont_show_checkbutton, False, False, 0)
        self.run()
        if dont_show_checkbutton.get_active():
            settings.write_setting(setting, True)
        self.destroy()
