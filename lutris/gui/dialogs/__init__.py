"""Commonly used dialogs"""
import os
from gettext import gettext as _

from gi.repository import GLib, GObject, Gtk

from lutris import api, settings
from lutris.gui.widgets.log_text_view import LogTextView
from lutris.util import datapath
from lutris.util.jobs import AsyncCall
from lutris.util.log import logger


class Dialog(Gtk.Dialog):

    def __init__(self, title=None, parent=None, flags=0, buttons=None):
        super().__init__(title, parent, flags, buttons)
        self.set_border_width(10)
        self.connect("delete-event", self.on_destroy)
        self.set_destroy_with_parent(True)

    def on_destroy(self, _widget, _data=None):
        self.destroy()


class GtkBuilderDialog(GObject.Object):
    dialog_object = NotImplemented

    __gsignals__ = {
        "destroy": (GObject.SignalFlags.RUN_LAST, None, ()),
    }

    def __init__(self, parent=None, **kwargs):
        # pylint: disable=no-member
        super().__init__()
        ui_filename = os.path.join(datapath.get(), "ui", self.glade_file)
        if not os.path.exists(ui_filename):
            raise ValueError("ui file does not exists: %s" % ui_filename)

        self.builder = Gtk.Builder()
        self.builder.add_from_file(ui_filename)
        self.dialog = self.builder.get_object(self.dialog_object)

        self.builder.connect_signals(self)
        if parent:
            self.dialog.set_transient_for(parent)
        self.dialog.show_all()
        self.dialog.connect("delete-event", self.on_close)
        self.initialize(**kwargs)

    def initialize(self, **kwargs):
        """Implement further customizations in subclasses"""

    def present(self):
        self.dialog.present()

    def on_close(self, *args):  # pylint: disable=unused-argument
        """Propagate the destroy event after closing the dialog"""
        self.dialog.destroy()
        self.emit("destroy")

    def on_response(self, widget, response):  # pylint: disable=unused-argument
        if response == Gtk.ResponseType.DELETE_EVENT:
            try:
                self.dialog.hide()
            except AttributeError:
                pass


class AboutDialog(GtkBuilderDialog):
    glade_file = "about-dialog.ui"
    dialog_object = "about_dialog"

    def initialize(self):  # pylint: disable=arguments-differ
        self.dialog.set_version(settings.VERSION)


class NoticeDialog(Gtk.MessageDialog):

    """Display a message to the user."""

    def __init__(self, message, parent=None):
        super().__init__(buttons=Gtk.ButtonsType.OK, parent=parent)
        self.set_markup(message)
        self.run()
        self.destroy()


class ErrorDialog(Gtk.MessageDialog):
    """Display an error message."""

    def __init__(self, message, secondary=None, parent=None):
        super().__init__(buttons=Gtk.ButtonsType.OK, parent=parent)
        # Gtk doesn't wrap long labels containing no space correctly
        # the length of the message is limited to avoid display issues
        self.set_markup(message[:256])
        if secondary:
            self.format_secondary_text(secondary[:256])
        self.run()
        self.destroy()


class QuestionDialog(Gtk.MessageDialog):

    """Ask the user a question."""

    YES = Gtk.ResponseType.YES
    NO = Gtk.ResponseType.NO

    def __init__(self, dialog_settings):
        super().__init__(message_type=Gtk.MessageType.QUESTION, buttons=Gtk.ButtonsType.YES_NO,
                         parent=dialog_settings.get("parent"))
        self.set_markup(dialog_settings["question"])
        self.set_title(dialog_settings["title"])
        if "widgets" in dialog_settings:
            for widget in dialog_settings["widgets"]:
                self.get_message_area().add(widget)
        self.result = self.run()
        self.destroy()


class DirectoryDialog(Gtk.FileChooserDialog):

    """Ask the user to select a directory."""

    def __init__(self, message, default_path=None, parent=None):
        super().__init__(
            title=message,
            action=Gtk.FileChooserAction.SELECT_FOLDER,
            buttons=(_("_Cancel"), Gtk.ResponseType.CLOSE, _("_OK"), Gtk.ResponseType.OK),
            parent=parent,
        )
        if default_path:
            self.set_current_folder(default_path)
        self.result = self.run()
        self.folder = self.get_current_folder()
        self.destroy()


class FileDialog(Gtk.FileChooserDialog):

    """Ask the user to select a file."""

    def __init__(self, message=None, default_path=None, mode="open"):
        self.filename = None
        if not message:
            message = _("Please choose a file")
        if mode == "save":
            action = Gtk.FileChooserAction.SAVE
        else:
            action = Gtk.FileChooserAction.OPEN
        super().__init__(
            message,
            None,
            action,
            (_("_Cancel"), Gtk.ResponseType.CANCEL, _("_OK"), Gtk.ResponseType.OK),
        )
        if default_path and os.path.exists(default_path):
            self.set_current_folder(default_path)
        self.set_local_only(False)
        response = self.run()
        if response == Gtk.ResponseType.OK:
            self.filename = self.get_filename()

        self.destroy()


class LutrisInitDialog(Gtk.Dialog):

    def __init__(self, init_lutris):
        super().__init__()
        self.set_size_request(320, 60)
        self.set_border_width(24)
        self.set_decorated(False)
        vbox = Gtk.Box.new(Gtk.Orientation.VERTICAL, 12)
        label = Gtk.Label(_("Checking for runtime updates, please wait…"))
        vbox.add(label)
        self.progress = Gtk.ProgressBar(visible=True)
        self.progress.set_pulse_step(0.1)
        vbox.add(self.progress)
        self.get_content_area().add(vbox)
        GLib.timeout_add(125, self.show_progress)
        self.show_all()
        AsyncCall(self.initialize, self.init_cb, init_lutris)

    def show_progress(self):
        self.progress.pulse()
        return True

    def initialize(self, init_lutris, *args):
        init_lutris()

    def init_cb(self, _result, error):
        if error:
            ErrorDialog(str(error))
        self.destroy()


class InstallOrPlayDialog(Gtk.Dialog):

    def __init__(self, game_name):
        Gtk.Dialog.__init__(self, _("%s is already installed") % game_name)
        self.connect("delete-event", lambda *x: self.destroy())

        self.action = "play"
        self.action_confirmed = False

        self.set_size_request(320, 120)
        self.set_border_width(12)
        vbox = Gtk.Box.new(Gtk.Orientation.VERTICAL, 6)
        self.get_content_area().add(vbox)

        play_button = Gtk.RadioButton.new_with_label_from_widget(None, _("Launch game"))
        play_button.connect("toggled", self.on_button_toggled, "play")
        vbox.pack_start(play_button, False, False, 0)
        install_button = Gtk.RadioButton.new_from_widget(play_button)
        install_button.set_label(_("Install the game again"))
        install_button.connect("toggled", self.on_button_toggled, "install")
        vbox.pack_start(install_button, False, False, 0)

        confirm_button = Gtk.Button(_("OK"))
        confirm_button.connect("clicked", self.on_confirm)
        vbox.pack_start(confirm_button, False, False, 0)

        self.show_all()
        self.run()

    def on_button_toggled(self, button, action):  # pylint: disable=unused-argument
        logger.debug("Action set to %s", action)
        self.action = action

    def on_confirm(self, button):  # pylint: disable=unused-argument
        logger.debug("Action %s confirmed", self.action)
        self.action_confirmed = True
        self.destroy()


class ClientLoginDialog(GtkBuilderDialog):
    glade_file = "dialog-lutris-login.ui"
    dialog_object = "lutris-login"
    __gsignals__ = {
        "connected": (GObject.SignalFlags.RUN_LAST, None, (GObject.TYPE_PYOBJECT, )),
        "cancel": (GObject.SignalFlags.RUN_LAST, None, (GObject.TYPE_PYOBJECT, )),
    }

    def __init__(self, parent):
        super().__init__(parent=parent)

        self.parent = parent
        self.username_entry = self.builder.get_object("username_entry")
        self.password_entry = self.builder.get_object("password_entry")

        cancel_button = self.builder.get_object("cancel_button")
        cancel_button.connect("clicked", self.on_close)
        connect_button = self.builder.get_object("connect_button")
        connect_button.connect("clicked", self.on_connect)

    def get_credentials(self):
        username = self.username_entry.get_text()
        password = self.password_entry.get_text()
        return username, password

    def on_username_entry_activate(self, widget):  # pylint: disable=unused-argument
        if all(self.get_credentials()):
            self.on_connect(None)
        else:
            self.password_entry.grab_focus()

    def on_password_entry_activate(self, widget):  # pylint: disable=unused-argument
        if all(self.get_credentials()):
            self.on_connect(None)
        else:
            self.username_entry.grab_focus()

    def on_connect(self, widget):  # pylint: disable=unused-argument
        username, password = self.get_credentials()
        token = api.connect(username, password)
        if not token:
            NoticeDialog(_("Login failed"), parent=self.dialog)
        else:
            self.emit("connected", username)
            self.dialog.destroy()


class InstallerSourceDialog(Gtk.Dialog):

    """Show install script source"""

    def __init__(self, code, name, parent):
        Gtk.Dialog.__init__(self, _("Install script for {}").format(name), parent=parent)
        self.set_size_request(500, 350)
        self.set_border_width(0)

        self.scrolled_window = Gtk.ScrolledWindow()
        self.scrolled_window.set_hexpand(True)
        self.scrolled_window.set_vexpand(True)

        source_buffer = Gtk.TextBuffer()
        source_buffer.set_text(code)

        source_box = LogTextView(source_buffer, autoscroll=False)

        self.get_content_area().add(self.scrolled_window)
        self.scrolled_window.add(source_box)

        close_button = Gtk.Button(_("OK"))
        close_button.connect("clicked", self.on_close)
        self.get_content_area().add(close_button)

        self.show_all()

    def on_close(self, *args):  # pylint: disable=unused-argument
        self.destroy()


class DontShowAgainDialog(Gtk.MessageDialog):

    """Display a message to the user and offer an option not to display this dialog again."""

    def __init__(
        self,
        setting,
        message,
        secondary_message=None,
        parent=None,
        checkbox_message=None,
    ):
        # pylint: disable=no-member
        if settings.read_setting(setting) == "True":
            logger.info("Dialog %s dismissed by user", setting)
            return

        super().__init__(type=Gtk.MessageType.WARNING, buttons=Gtk.ButtonsType.OK, parent=parent)

        self.set_border_width(12)
        self.set_markup("<b>%s</b>" % message)
        if secondary_message:
            self.props.secondary_use_markup = True
            self.props.secondary_text = secondary_message

        if not checkbox_message:
            checkbox_message = _("Do not display this message again.")

        dont_show_checkbutton = Gtk.CheckButton(checkbox_message)
        dont_show_checkbutton.props.halign = Gtk.Align.CENTER
        dont_show_checkbutton.show()

        content_area = self.get_content_area()
        content_area.pack_start(dont_show_checkbutton, False, False, 0)
        self.run()
        if dont_show_checkbutton.get_active():
            settings.write_setting(setting, True)
        self.destroy()


class WineNotInstalledWarning(DontShowAgainDialog):

    """Display a warning if Wine is not detected on the system"""

    def __init__(self, parent=None):
        super().__init__(
            "hide-wine-systemwide-install-warning",
            _("Wine is not installed on your system."),
            secondary_message=_(
                "Having Wine installed on your system guarantees that "
                "Wine builds from Lutris will have all required dependencies.\n\nPlease "
                "follow the instructions given in the <a "
                "href='https://github.com/lutris/lutris/wiki/Wine-Dependencies'>Lutris Wiki</a> to "
                "install Wine."
            ),
            parent=parent,
        )


class MoveDialog(Gtk.Dialog):
    __gsignals__ = {
        "game-moved": (GObject.SIGNAL_RUN_FIRST, None, ()),
    }

    def __init__(self, game, destination):
        super().__init__()

        self.game = game
        self.destination = destination
        self.new_directory = None

        self.set_size_request(320, 60)
        self.set_border_width(24)
        self.set_decorated(False)
        vbox = Gtk.Box.new(Gtk.Orientation.VERTICAL, 12)
        label = Gtk.Label(_("Moving %s to %s..." % (game, destination)))
        vbox.add(label)
        self.progress = Gtk.ProgressBar(visible=True)
        self.progress.set_pulse_step(0.1)
        vbox.add(self.progress)
        self.get_content_area().add(vbox)
        GLib.timeout_add(125, self.show_progress)
        self.show_all()

    def move(self):
        AsyncCall(self._move_game, self.on_game_moved)

    def show_progress(self):
        self.progress.pulse()
        return True

    def _move_game(self):
        self.new_directory = self.game.move(self.destination)

    def on_game_moved(self, _result, error):
        if error:
            ErrorDialog(str(error))
        self.emit("game-moved")
        self.destroy()
