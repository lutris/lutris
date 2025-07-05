"""Commonly used dialogs"""

import builtins
import inspect
import os
import traceback
from gettext import gettext as _
from typing import Any, Callable, Dict, Optional, Type, TypeVar, Union, cast

import gi

from lutris.exceptions import LutrisError

gi.require_version("Gdk", "3.0")
gi.require_version("Gtk", "3.0")

from gi.repository import Gdk, GObject, Gtk

from lutris import api, settings
from lutris.gui.widgets.log_text_view import LogTextView
from lutris.gui.widgets.utils import get_widget_children, get_widget_window
from lutris.util import datapath
from lutris.util.jobs import schedule_at_idle
from lutris.util.log import get_log_contents, logger
from lutris.util.strings import gtk_safe


class Dialog(Gtk.Dialog):
    """A base class for dialogs that provides handling for the response signal;
    you can override its on_response() methods, but that method will record
    the response for you via 'response_type' or 'confirmed' and destory this
    dialog if it isn't NONE."""

    def __init__(
        self,
        title: str = None,
        parent: Gtk.Widget = None,
        flags: Gtk.DialogFlags = 0,
        buttons: Gtk.ButtonsType = None,
        **kwargs,
    ):
        # MyPy can't see it, but __init__ can handle the new_with_buttons arguments for us
        super().__init__(title, parent, flags, buttons, **kwargs)  # type:ignore
        self._response_type = Gtk.ResponseType.NONE
        self.connect("response", self.on_response)

    @property
    def response_type(self) -> Gtk.ResponseType:
        """The response type of the response that occurred; initially this is NONE.
        Use the GTK response() method to artificially generate a response, rather than
        setting this."""
        return self._response_type

    @property
    def confirmed(self) -> bool:
        """True if 'response_type' is OK or YES."""
        return self.response_type in (Gtk.ResponseType.OK, Gtk.ResponseType.YES)

    def on_response(self, _dialog, response: Gtk.ResponseType) -> None:
        """Handles the dialog response; you can override this but by default
        this records the response for 'response_type'."""
        self._response_type = response

    def destroy_at_idle(self, condition: Optional[Callable] = None):
        """Adds as idle task to destroy this window at idle time;
        it can do so conditionally if you provide a callable to check,
        but it checks only once. You can still explicitly destroy the
        dialog after calling this. This is used to ensure destruction of
        ModalDialog after run()."""

        def idle_destroy():
            if not condition or condition():
                self.destroy()

        def on_destroy(*_args):
            self.disconnect(on_destroy_id)
            idle_destroy_task.unschedule()

        self.hide()
        idle_destroy_task = schedule_at_idle(idle_destroy)
        on_destroy_id = self.connect("destroy", on_destroy)

    def add_styled_button(self, button_text: str, response_id: Gtk.ResponseType, css_class: str):
        button = self.add_button(button_text, response_id)
        if css_class:
            style_context = button.get_style_context()
            style_context.add_class(css_class)
        return button

    def add_default_button(self, button_text: str, response_id: Gtk.ResponseType, css_class: str = "suggested-action"):
        """Adds a button to the dialog with a particular response id, but
        also makes it the default and styles it as the suggested action."""
        button = self.add_styled_button(button_text, response_id, css_class)
        self.set_default_response(response_id)
        return button


class ModalDialog(Dialog):
    """A base class of modal dialogs, which sets the flag for you.

    Unlike plain Gtk.Dialog, these destroy themselves (at idle-time) after
    you call run(), even if you forget to. They aren't meant to be reused."""

    def __init__(
        self,
        title: str = None,
        parent: Gtk.Widget = None,
        flags: Gtk.DialogFlags = 0,
        buttons: Gtk.ButtonsType = None,
        **kwargs,
    ):
        super().__init__(title, parent, flags | Gtk.DialogFlags.MODAL, buttons, **kwargs)
        self.set_destroy_with_parent(True)

    def on_response(self, dialog, response: Gtk.ResponseType) -> None:
        super().on_response(dialog, response)
        # Model dialogs do return from run() in response from respose() but the
        # dialog is visible and locks out its parent. So we hide it. Watch out-
        # self.destroy() changes the run() result to NONE.
        if response != Gtk.ResponseType.NONE:
            self.hide()
            self.destroy_at_idle(condition=lambda: not self.get_visible())


class ModelessDialog(Dialog):
    """A base class for modeless dialogs. They have a parent only temporarily, so
    they can be centered over it during creation. But each modeless dialog gets
    its own window group, so it treats its own modal dialogs separately, and it resets
    its transient-for after being created."""

    def __init__(
        self,
        title: str = None,
        parent: Gtk.Widget = None,
        flags: Gtk.DialogFlags = 0,
        buttons: Gtk.ButtonsType = None,
        **kwargs,
    ):
        super().__init__(title, parent, flags, buttons, **kwargs)
        # These are not stuck above the 'main' window, but can be
        # re-ordered freely.
        self.set_type_hint(Gdk.WindowTypeHint.NORMAL)

        # These are independent windows, but start centered over
        # a parent like a dialog. Not modal, not really transient,
        # and does not share modality with other windows - so it
        # needs its own window group.
        Gtk.WindowGroup().add_window(self)
        schedule_at_idle(self._clear_transient_for)

    def _clear_transient_for(self) -> None:
        # we need the parent set to be centered over the parent, but
        # we don't want to be transient really - we want other windows
        # able to come to the front.
        self.set_transient_for(None)

    def on_response(self, dialog, response: Gtk.ResponseType) -> None:
        super().on_response(dialog, response)
        # Modal dialogs self-destruct, but modeless ones must commit
        # suicide more explicitly.
        if response != Gtk.ResponseType.NONE:
            self.destroy()


class SavableModelessDialog(ModelessDialog):
    """This is a modeless dialog that has a Cancel and a Save button in the header-bar,
    with a ctrl-S keyboard shortcut to save."""

    def __init__(self, title: str, parent: Gtk.Widget = None, **kwargs):
        super().__init__(title, parent=parent, use_header_bar=True, **kwargs)

        self.cancel_button = self.add_button(_("Cancel"), Gtk.ResponseType.CANCEL)
        self.cancel_button.set_valign(Gtk.Align.CENTER)

        self.save_button = self.add_styled_button(_("Save"), Gtk.ResponseType.NONE, css_class="suggested-action")
        self.save_button.set_valign(Gtk.Align.CENTER)
        self.save_button.connect("clicked", self.on_save)

        self.accelerators = Gtk.AccelGroup()
        self.add_accel_group(self.accelerators)
        key, mod = Gtk.accelerator_parse("<Primary>s")
        self.save_button.add_accelerator("clicked", self.accelerators, key, mod, Gtk.AccelFlags.VISIBLE)

    def on_save(self, _button):
        pass


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

    def __init__(self, message_markup: str, secondary: Optional[str] = None, parent: Optional[Gtk.Widget] = None):
        parent: Gtk.Window = get_widget_window(parent)
        super().__init__(message_type=Gtk.MessageType.INFO, buttons=Gtk.ButtonsType.OK, parent=parent)
        self.set_markup(message_markup)
        if secondary:
            self.format_secondary_text(secondary[:256])

        # So you can copy warning text
        for child in get_widget_children(self.get_message_area(), child_type=Gtk.Label):
            child.set_selectable(True)

        self.run()
        self.destroy()


class WarningDialog(Gtk.MessageDialog):
    """Display a warning to the user, who responds with whether to proceed, like
    a QuestionDialog."""

    def __init__(self, message_markup: str, secondary: Optional[str] = None, parent: Optional[Gtk.Widget] = None):
        parent: Gtk.Window = get_widget_window(parent)
        super().__init__(message_type=Gtk.MessageType.WARNING, buttons=Gtk.ButtonsType.OK_CANCEL, parent=parent)
        self.set_markup(message_markup)
        if secondary:
            self.format_secondary_text(secondary[:256])

        # So you can copy warning text
        for child in get_widget_children(self.get_message_area(), child_type=Gtk.Label):
            child.set_selectable(True)

        self.result = self.run()
        self.destroy()


class ErrorDialog(Gtk.MessageDialog):
    """Display an error message."""

    def __init__(
        self,
        error: Union[str, builtins.BaseException],
        message_markup: Optional[str] = None,
        secondary_markup: Optional[str] = None,
        parent: Optional[Gtk.Widget] = None,
    ):
        parent: Gtk.Window = get_widget_window(parent)
        super().__init__(message_type=Gtk.MessageType.ERROR, buttons=Gtk.ButtonsType.OK, parent=parent)

        def get_message_markup(err: Union[BaseException, str]) -> str:
            if isinstance(err, LutrisError):
                return err.message_markup or gtk_safe(str(err))
            else:
                return gtk_safe(str(err))

        if isinstance(error, builtins.BaseException):
            if secondary_markup:
                # Some errors contain < and > and look like markup, but aren't-
                # we'll need to protect the message dialog against this. To use markup,
                # you must pass the message itself directly.
                message_markup = message_markup or get_message_markup(error)
            elif not message_markup:
                message_markup = "<span weight='bold'>%s</span>" % _("Lutris has encountered an error")
                secondary_markup = get_message_markup(error)
        elif not message_markup:
            message_markup = get_message_markup(error)

        # Gtk doesn't wrap long labels containing no space correctly
        # the length of the message is limited to avoid display issues

        if message_markup:
            self.set_markup(message_markup[:256])

        if secondary_markup:
            self.format_secondary_markup(secondary_markup[:256])

        # So you can copy error text
        for child in get_widget_children(self.get_message_area(), child_type=Gtk.Label):
            child.set_selectable(True)

        if isinstance(error, BaseException):
            content_area = self.get_content_area()
            spacing = content_area.get_spacing()
            content_area.set_spacing(0)

            details_expander = self.get_details_expander(error)
            details_expander.set_margin_top(spacing)
            content_area.pack_end(details_expander, False, False, 0)

            action_area = cast(Gtk.ButtonBox, self.get_action_area())
            copy_button = Gtk.Button(label=_("Copy Details to Clipboard"), visible=True)
            action_area.pack_start(copy_button, False, True, 0)
            action_area.set_child_secondary(copy_button, True)
            copy_button.connect("clicked", self.on_copy_clicked, error)

        self.run()
        self.destroy()

    def on_copy_clicked(self, _button, error: BaseException):
        details = self.format_error(error)
        clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
        clipboard.set_text(details, -1)

    def get_details_expander(self, error: BaseException) -> Gtk.Widget:
        details = self.format_error(error, include_message=False)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        label = Gtk.Label(xalign=0.0, wrap=True, margin_left=6, margin_right=6, margin_bottom=6)
        label.set_markup(
            _(
                "You can get support from "
                "<a href='https://github.com/lutris/lutris'>GitHub</a> or "
                "<a href='https://discordapp.com/invite/Pnt5CuY'>Discord</a>. "
                "Make sure to provide the error details;\n"
                "use the 'Copy Details to Clipboard' button to get them."
            )
        )
        box.pack_start(label, False, False, 0)

        expander = Gtk.Expander.new(_("Error details"))

        details_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        details_box.pack_start(Gtk.Separator(), False, False, 0)

        details_textview = Gtk.TextView(editable=False)
        details_textview.get_buffer().set_text(details)

        details_scrolledwindow = Gtk.ScrolledWindow(width_request=800, height_request=400)
        details_scrolledwindow.add(details_textview)
        details_box.pack_start(details_scrolledwindow, False, False, 0)
        expander.add(details_box)

        box.pack_start(expander, True, True, 0)
        box.show_all()
        return box

    @staticmethod
    def format_error(error: BaseException, include_message: bool = True):
        formatted = traceback.format_exception(type(error), error, error.__traceback__)
        if include_message:
            formatted = [str(error), ""] + formatted
        text = "\n".join(formatted).strip()
        log = get_log_contents()

        if log:
            text = f"{text}\n\nLutris log:\n{log}".strip()

        return text


class QuestionDialog(Gtk.MessageDialog):
    """Ask the user a yes or no question."""

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


class InputDialog(ModalDialog):
    """Ask the user for a text input"""

    def __init__(self, dialog_settings):
        super().__init__(parent=dialog_settings["parent"])
        self.set_border_width(12)
        self.user_value = ""
        self.add_button(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL)
        self.ok_button = self.add_default_button(Gtk.STOCK_OK, Gtk.ResponseType.OK)
        self.set_default_response(Gtk.ResponseType.OK)
        self.ok_button.set_sensitive(False)
        self.set_title(dialog_settings["title"])
        label = Gtk.Label(visible=True)
        label.set_markup(dialog_settings["question"])
        self.get_content_area().pack_start(label, True, True, 12)
        self.entry = Gtk.Entry(visible=True, activates_default=True)
        self.entry.connect("changed", self.on_entry_changed)
        self.get_content_area().pack_start(self.entry, True, True, 12)
        self.entry.set_text(dialog_settings.get("initial_value") or "")

    def on_entry_changed(self, widget):
        self.user_value = widget.get_text()
        self.ok_button.set_sensitive(bool(self.user_value))


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


class InstallOrPlayDialog(ModalDialog):
    def __init__(self, game_name, parent=None):
        super().__init__(title=_("%s is already installed") % game_name, parent=parent, border_width=10)
        self.action = "play"
        self.action_confirmed = False

        self.add_button(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL)
        self.add_default_button(Gtk.STOCK_OK, Gtk.ResponseType.OK)

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
        if response == Gtk.ResponseType.CANCEL:
            self.action = None
        super().on_response(_widget, response)


class LaunchConfigSelectDialog(ModalDialog):
    def __init__(self, game, configs, title, parent=None):
        super().__init__(title=title, parent=parent, border_width=10)
        self.config_index = 0
        self.dont_show_again = False

        self.add_button(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL)
        self.add_default_button(Gtk.STOCK_OK, Gtk.ResponseType.OK)

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

        dont_show_checkbutton = Gtk.CheckButton(_("Do not ask again for this game."))
        dont_show_checkbutton.connect("toggled", self.on_dont_show_checkbutton_toggled)
        vbox.pack_end(dont_show_checkbutton, False, False, 6)

        self.show_all()
        self.run()

    def on_button_toggled(self, _button, index):
        self.config_index = index

    def on_dont_show_checkbutton_toggled(self, _button):
        self.dont_show_again = _button.get_active()


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
            self.dialog.destroy()
            self.emit("connected", username)


class InstallerSourceDialog(ModelessDialog):
    """Show install script source"""

    def __init__(self, code, name, parent):
        super().__init__(title=_("Install script for {}").format(name), parent=parent, border_width=0)
        self.set_default_size(800, 750)

        ok_button = self.add_default_button(Gtk.STOCK_OK, Gtk.ResponseType.OK)
        ok_button.set_border_width(10)

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


class HumbleBundleCookiesDialog(ModalDialog):
    def __init__(self, parent=None):
        super().__init__(_("Humble Bundle Cookie Authentication"), parent)
        self.cookies_content = None
        self.add_button(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL)
        self.add_default_button(Gtk.STOCK_OK, Gtk.ResponseType.OK)

        self.set_size_request(640, 512)

        vbox = Gtk.Box.new(Gtk.Orientation.VERTICAL, 6)
        self.get_content_area().add(vbox)
        label = Gtk.Label()
        label.set_markup(
            _(
                "<b>Humble Bundle Authentication via cookie import</b>\n"
                "\n"
                "<b>In Firefox</b>\n"
                "- Install the following extension: "
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
            )
        )
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

    def on_response(self, dialog, response):
        if response == Gtk.ResponseType.CANCEL:
            self.cookies_content = None
        else:
            buffer = self.textview.get_buffer()
            self.cookies_content = buffer.get_text(buffer.get_start_iter(), buffer.get_end_iter(), True)

        super().on_response(dialog, response)


_error_handlers: Dict[Type[BaseException], Callable[[BaseException, Gtk.Window], Any]] = {}
TError = TypeVar("TError", bound=BaseException)


def display_error(error: BaseException, parent: Gtk.Widget) -> None:
    """Displays an error in a modal dialog. This can be customized via
    register_error_handler(), but displays an ErrorDialog by default.

    This allows custom error handling to be invoked anywhere that can show an
    ErrorDialog, instead of having to bounce exceptions off the backstop."""
    handler = get_error_handler(type(error))

    if isinstance(parent, Gtk.Window):
        handler(error, parent)
    else:
        handler(error, cast(Gtk.Window, parent.get_toplevel()))


def register_error_handler(error_class: Type[TError], handler: Callable[[TError, Gtk.Window], Any]) -> None:
    """Records a function to call to handle errors of a particular class or its subclasses. The
    function is given the error and a parent window, and can display a modal dialog."""
    _error_handlers[error_class] = handler


def get_error_handler(error_class: Type[TError]) -> Callable[[TError, Gtk.Window], Any]:
    """Returns the register error handler for an exception class. If none is registered,
    this returns a default handler that shows an ErrorDialog."""
    if not isinstance(error_class, type):
        if isinstance(error_class, BaseException):
            logger.debug("An error was passed where an error class should be passed.")
            error_class = type(error_class)
        else:
            raise ValueError(f"'{error_class}' was passed to get_error_handler, but an error class is required here.")

    if error_class in _error_handlers:
        return _error_handlers[error_class]

    for base_class in inspect.getmro(error_class):
        if base_class in _error_handlers:
            return _error_handlers[base_class]

    return lambda e, p: ErrorDialog(e, parent=p)


def _handle_keyerror(error: KeyError, parent: Gtk.Window) -> None:
    message = _("The key '%s' could not be found.") % error.args[0]
    ErrorDialog(error, message_markup=gtk_safe(message), parent=parent)


register_error_handler(KeyError, _handle_keyerror)
