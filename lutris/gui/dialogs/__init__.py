"""Commonly used dialogs"""
import os
from gettext import gettext as _

import gi

gi.require_version('Gdk', '3.0')
gi.require_version('Gtk', '3.0')

from gi.repository import Gdk, GLib, GObject, Gtk

from lutris import api, settings
from lutris.gui.widgets.log_text_view import LogTextView
from lutris.migrations import migrate
from lutris.util import datapath
from lutris.util.jobs import AsyncCall
from lutris.util.log import logger


class Dialog(Gtk.Dialog):

    def __init__(self, title=None, parent=None, flags=0, buttons=None, **kwargs):
        super().__init__(title, parent, flags, buttons, **kwargs)
        self.connect("delete-event", self.on_destroy)
        self.set_destroy_with_parent(True)

    def on_destroy(self, _widget, _data=None):
        self.destroy()

    def add_styled_button(self, button_text, response_id, css_class):
        button = self.add_button(button_text, response_id)
        if css_class:
            style_context = button.get_style_context()
            style_context.add_class(css_class)
        return button

    def add_default_button(self, button_text, response_id, css_class="suggested-action"):
        """Adds a button to the dialog with a particular response id, but
        also makes it the default and styles it as the suggested action."""
        button = self.add_styled_button(button_text, response_id, css_class)
        self.set_default_response(response_id)
        return button


class ModalDialog(Dialog):
    """A base class of moodal dialogs, which sets the flag for you."""

    def __init__(self, title=None, parent=None, flags=0, buttons=None, **kwargs):
        super().__init__(title, parent, flags | Gtk.DialogFlags.MODAL, buttons, **kwargs)


class ModelessDialog(Dialog):
    """A base class for modeless dialogs. They have a parent only temporarily, so
    they can be centered over it during creation. But each modeless dialog gets
    its own window group, so it treats its own modal dialogs separately, and it resets
    its transient-for after being created."""

    def __init__(self, title=None, parent=None, flags=0, buttons=None, **kwargs):
        super().__init__(title, parent, flags, buttons, **kwargs)
        # These are not stuck above the 'main' window, but can be
        # re-ordered freely.
        self.set_type_hint(Gdk.WindowTypeHint.NORMAL)

        # These are independent windows, but start centered over
        # a parent like a dialog. Not modal, not really transient,
        # and does not share modality with other windows - so it
        # needs its own window group.
        Gtk.WindowGroup().add_window(self)
        GLib.idle_add(self._clear_transient_for)

    def _clear_transient_for(self):
        # we need the parent set to be centered over the parent, but
        # we don't want to be transient really - we want other windows
        # able to come to the front.
        self.set_transient_for(None)
        return False


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

    def __init__(self, message, secondary=None, parent=None):
        super().__init__(message_type=Gtk.MessageType.INFO, buttons=Gtk.ButtonsType.OK, parent=parent)
        self.set_markup(message)
        if secondary:
            self.format_secondary_text(secondary[:256])

        # So you can copy warning text
        for child in self.get_message_area().get_children():
            if isinstance(child, Gtk.Label):
                child.set_selectable(True)

        self.run()
        self.destroy()


class WarningDialog(Gtk.MessageDialog):
    """Display a warning to the user, who responds with whether to proceed, like
    a QuestionDialog."""

    def __init__(self, message, secondary=None, parent=None):
        super().__init__(message_type=Gtk.MessageType.WARNING, buttons=Gtk.ButtonsType.OK_CANCEL, parent=parent)
        self.set_markup(message)
        if secondary:
            self.format_secondary_text(secondary[:256])

        # So you can copy warning text
        for child in self.get_message_area().get_children():
            if isinstance(child, Gtk.Label):
                child.set_selectable(True)

        self.result = self.run()
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

        # So you can copy error text
        for child in self.get_message_area().get_children():
            if isinstance(child, Gtk.Label):
                child.set_selectable(True)

        self.run()
        self.destroy()


class QuestionDialog(Gtk.MessageDialog):
    """Ask the user a question."""

    YES = Gtk.ResponseType.YES
    NO = Gtk.ResponseType.NO

    def __init__(self, dialog_settings):
        super().__init__(message_type=Gtk.MessageType.QUESTION, buttons=Gtk.ButtonsType.YES_NO)
        self.set_markup(dialog_settings["question"])
        self.set_title(dialog_settings["title"])
        if "parent" in dialog_settings:
            self.set_transient_for(dialog_settings["parent"])
        if "widgets" in dialog_settings:
            for widget in dialog_settings["widgets"]:
                self.get_message_area().add(widget)
        self.result = self.run()
        self.destroy()


class DirectoryDialog:
    """Ask the user to select a directory."""

    def __init__(self, message, default_path=None, parent=None):
        self.folder = None
        dialog = Gtk.FileChooserNative.new(
            message,
            parent,
            Gtk.FileChooserAction.SELECT_FOLDER,
            _("_OK"),
            _("_Cancel"),
        )
        if default_path:
            dialog.set_current_folder(default_path)
        self.result = dialog.run()
        if self.result == Gtk.ResponseType.ACCEPT:
            self.folder = dialog.get_filename()
        dialog.destroy()


class FileDialog:
    """Ask the user to select a file."""

    def __init__(self, message=None, default_path=None, mode="open", parent=None):
        self.filename = None
        if not message:
            message = _("Please choose a file")
        if mode == "save":
            action = Gtk.FileChooserAction.SAVE
        else:
            action = Gtk.FileChooserAction.OPEN
        dialog = Gtk.FileChooserNative.new(
            message,
            parent,
            action,
            _("_OK"),
            _("_Cancel"),
        )
        if default_path and os.path.exists(default_path):
            dialog.set_current_folder(default_path)
        dialog.set_local_only(False)
        response = dialog.run()
        if response == Gtk.ResponseType.ACCEPT:
            self.filename = dialog.get_filename()

        dialog.destroy()


class LutrisInitDialog(Gtk.Dialog):

    def __init__(self, runtime_updater):
        super().__init__()
        self.runtime_updater = runtime_updater

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
        self.progress_timeout = GLib.timeout_add(125, self.show_progress)
        self.show_all()

        self.connect("response", self.on_response)
        self.connect("destroy", self.on_destroy)
        AsyncCall(self.run_init, self.init_cb)

    def show_progress(self):
        self.progress.pulse()
        return True

    def run_init(self):
        migrate()
        self.runtime_updater.update_runtimes()

    def init_cb(self, _result, error):
        if error:
            ErrorDialog(str(error), parent=self)
        self.destroy()

    def on_response(self, _widget, response):
        self.runtime_updater.cancel()
        self.destroy()

    def on_destroy(self, window):
        GLib.source_remove(self.progress_timeout)
        return True


class InstallOrPlayDialog(ModalDialog):

    def __init__(self, game_name, parent=None):
        super().__init__(title=_("%s is already installed") % game_name, parent=parent, border_width=10)
        self.action = "play"
        self.action_confirmed = False

        self.add_button(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL)
        self.add_default_button(Gtk.STOCK_OK, Gtk.ResponseType.OK)
        self.connect("response", self.on_response)

        self.set_size_request(320, 120)
        vbox = Gtk.Box.new(Gtk.Orientation.VERTICAL, 6)
        self.get_content_area().add(vbox)
        play_button = Gtk.RadioButton.new_with_label_from_widget(None, _("Launch game"))
        play_button.connect("toggled", self.on_button_toggled, "play")
        vbox.pack_start(play_button, False, False, 0)
        install_button = Gtk.RadioButton.new_from_widget(play_button)
        install_button.set_label(_("Install the game again"))
        install_button.connect("toggled", self.on_button_toggled, "install")
        vbox.pack_start(install_button, False, False, 0)

        self.show_all()
        self.run()

    def on_button_toggled(self, _button, action):
        logger.debug("Action set to %s", action)
        self.action = action

    def on_response(self, _widget, response):
        logger.debug("Dialog response %s", response)
        if response == Gtk.ResponseType.CANCEL:
            self.action = None
        self.destroy()


class LaunchConfigSelectDialog(ModalDialog):
    def __init__(self, game, configs, title, parent=None, has_dont_show_again=False):
        super().__init__(title=title, parent=parent, border_width=10)
        self.config_index = 0
        self.dont_show_again = False
        self.confirmed = False

        self.add_button(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL)
        self.add_default_button(Gtk.STOCK_OK, Gtk.ResponseType.OK)
        self.connect("response", self.on_response)

        self.set_size_request(320, 120)
        vbox = Gtk.Box.new(Gtk.Orientation.VERTICAL, 6)
        self.get_content_area().add(vbox)

        primary_game_radio = Gtk.RadioButton.new_with_label_from_widget(None, game.name)
        primary_game_radio.connect("toggled", self.on_button_toggled, 0)
        vbox.pack_start(primary_game_radio, False, False, 0)
        for i, config in enumerate(configs):
            _button = Gtk.RadioButton.new_from_widget(primary_game_radio)
            _button.set_label(config["name"])
            _button.connect("toggled", self.on_button_toggled, i + 1)
            vbox.pack_start(_button, False, False, 0)

        if has_dont_show_again:
            dont_show_checkbutton = Gtk.CheckButton(_("Do not ask again for this game."))
            dont_show_checkbutton.connect("toggled", self.on_dont_show_checkbutton_toggled)
            vbox.pack_end(dont_show_checkbutton, False, False, 6)

        self.show_all()
        self.run()

    def on_button_toggled(self, _button, index):
        self.config_index = index

    def on_dont_show_checkbutton_toggled(self, _button):
        self.dont_show_again = _button.get_active()

    def on_response(self, _widget, response):
        self.confirmed = response == Gtk.ResponseType.OK
        self.destroy()


class ClientLoginDialog(GtkBuilderDialog):
    glade_file = "dialog-lutris-login.ui"
    dialog_object = "lutris-login"
    __gsignals__ = {
        "connected": (GObject.SignalFlags.RUN_LAST, None, (GObject.TYPE_PYOBJECT,)),
        "cancel": (GObject.SignalFlags.RUN_LAST, None, (GObject.TYPE_PYOBJECT,)),
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
            NoticeDialog(_("Login failed"), parent=self.parent)
        else:
            self.emit("connected", username)
            self.dialog.destroy()


class InstallerSourceDialog(ModelessDialog):
    """Show install script source"""

    def __init__(self, code, name, parent):
        super().__init__(title=_("Install script for {}").format(name), parent=parent, border_width=0)
        self.set_size_request(500, 350)

        ok_button = self.add_default_button(Gtk.STOCK_OK, Gtk.ResponseType.OK)
        ok_button.set_border_width(10)
        self.connect("response", self.on_response)

        self.scrolled_window = Gtk.ScrolledWindow()
        self.scrolled_window.set_hexpand(True)
        self.scrolled_window.set_vexpand(True)

        source_buffer = Gtk.TextBuffer()
        source_buffer.set_text(code)

        source_box = LogTextView(source_buffer, autoscroll=False)

        self.get_content_area().set_border_width(0)
        self.get_content_area().add(self.scrolled_window)
        self.scrolled_window.add(source_box)

        self.show_all()

    def on_response(self, *args):
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
        cancellable=False
    ):
        # pylint: disable=no-member
        if settings.read_setting(setting) == "True":
            logger.info("Dialog %s dismissed by user", setting)
            self.result = Gtk.ResponseType.OK
            return

        buttons = Gtk.ButtonsType.OK_CANCEL if cancellable else Gtk.ButtonsType.OK

        super().__init__(type=Gtk.MessageType.WARNING, buttons=buttons, parent=parent)

        self.set_default_response(Gtk.ResponseType.OK)
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
        self.result = self.run()
        if self.result == Gtk.ResponseType.OK and dont_show_checkbutton.get_active():
            settings.write_setting(setting, True)
        self.destroy()


class WineNotInstalledWarning(DontShowAgainDialog):
    """Display a warning if Wine is not detected on the system"""

    def __init__(self, parent=None, cancellable=False):
        super().__init__(
            "hide-wine-systemwide-install-warning",
            _("Wine is not installed on your system."),
            secondary_message=_(
                "Having Wine installed on your system guarantees that "
                "Wine builds from Lutris will have all required dependencies.\n\nPlease "
                "follow the instructions given in the <a "
                "href='https://github.com/lutris/docs/blob/master/WineDependencies.md'>Lutris Wiki</a> to "
                "install Wine."
            ),
            parent=parent,
            cancellable=cancellable
        )


class MoveDialog(ModelessDialog):
    __gsignals__ = {
        "game-moved": (GObject.SIGNAL_RUN_FIRST, None, ()),
    }

    def __init__(self, game, destination, parent=None):
        super().__init__(parent=parent, border_width=24)

        self.game = game
        self.destination = destination
        self.new_directory = None

        self.set_size_request(320, 60)
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
            ErrorDialog(str(error), parent=self)
        self.emit("game-moved")
        self.destroy()


class HumbleBundleCookiesDialog(ModalDialog):
    def __init__(self, parent=None):
        super().__init__(_("Humble Bundle Cookie Authentication"), parent)
        self.cookies_content = None
        self.add_button(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL)
        self.add_default_button(Gtk.STOCK_OK, Gtk.ResponseType.OK)
        self.connect("response", self.on_response)

        self.set_size_request(640, 512)

        vbox = Gtk.Box.new(Gtk.Orientation.VERTICAL, 6)
        self.get_content_area().add(vbox)
        label = Gtk.Label()
        label.set_markup(_(
            "<b>Humble Bundle Authentication via cookie import</b>\n"
            "\n"
            "<b>In Firefox</b>\n"
            "- Install the follwing extension: "
            "<a href='https://addons.mozilla.org/en-US/firefox/addon/export-cookies-txt/'>"
            "https://addons.mozilla.org/en-US/firefox/addon/export-cookies-txt/"
            "</a>\n"
            "- Open a tab to humblebundle.com and make sure you are logged in.\n"
            "- Click the cookie icon in the top right corner, next to the settings menu\n"
            "- Check 'Prefix HttpOnly cookies' and click 'humblebundle.com'\n"
            "- Open the generated file and paste the contents below. Click OK to finish.\n"
            "- You can delete the cookies file generated by Firefox\n"
            "- Optionally, <a href='https://support.humblebundle.com/hc/en-us/requests/new'>"
            "open a support ticket</a> to ask Humble Bundle to fix their configuration."
        ))
        vbox.pack_start(label, False, False, 24)
        self.textview = Gtk.TextView()
        self.textview.set_left_margin(12)
        self.textview.set_right_margin(12)
        scrolledwindow = Gtk.ScrolledWindow()
        scrolledwindow.set_hexpand(True)
        scrolledwindow.set_vexpand(True)
        scrolledwindow.add(self.textview)
        vbox.pack_start(scrolledwindow, True, True, 24)
        self.show_all()
        self.run()

    def on_response(self, _widget, response):
        if response == Gtk.ResponseType.CANCEL:
            self.cookies_content = None
        else:
            buffer = self.textview.get_buffer()
            self.cookies_content = buffer.get_text(buffer.get_start_iter(), buffer.get_end_iter(), True)
        self.destroy()
