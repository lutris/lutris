"""Commonly used dialogs"""

import builtins
import inspect
import os
import traceback
from collections.abc import Callable
from gettext import gettext as _
from typing import Any, TypeVar, cast

from gi.repository import Gio, GLib, GObject, Gtk

from lutris import api, settings
from lutris.exceptions import LutrisError
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

    vbox: Gtk.Box

    def __init__(
        self,
        title: str | None = None,
        parent: Gtk.Widget | None = None,
        flags: Gtk.DialogFlags = 0,
        buttons: Gtk.ButtonsType | None = None,
        **kwargs,
    ):
        # border_width was removed in GTK 4; convert to margins on content area
        border_width = kwargs.pop("border_width", None)
        super().__init__(**kwargs)
        self.vbox = self.get_content_area()  # GTK 3 compat alias
        if title:
            self.set_title(title)
        if parent:
            if isinstance(parent, Gtk.Window):
                self.set_transient_for(parent)
            elif isinstance(parent, Gtk.Widget):
                root = parent.get_root()
                if isinstance(root, Gtk.Window):
                    self.set_transient_for(root)
        if flags & Gtk.DialogFlags.MODAL:
            self.set_modal(True)
        if flags & Gtk.DialogFlags.DESTROY_WITH_PARENT:
            self.set_destroy_with_parent(True)
        if border_width:
            content = self.get_content_area()
            content.set_margin_top(border_width)
            content.set_margin_bottom(border_width)
            content.set_margin_start(border_width)
            content.set_margin_end(border_width)
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

    def run(self) -> Gtk.ResponseType:
        """Compatibility method for Gtk.Dialog.run() which was removed in GTK 4.
        Runs a nested main loop until the dialog emits a response.
        Returns the response type."""
        loop = GLib.MainLoop()
        response = [Gtk.ResponseType.NONE]

        def on_run_response(_dialog, resp):
            response[0] = resp
            loop.quit()

        def on_run_close(_dialog):
            response[0] = Gtk.ResponseType.DELETE_EVENT
            loop.quit()

        handler_id = self.connect("response", on_run_response)
        close_id = self.connect("close-request", on_run_close)
        self.set_modal(True)
        self.present()
        loop.run()
        self.disconnect(handler_id)
        self.disconnect(close_id)
        return response[0]

    def destroy_at_idle(self, condition: Callable | None = None):
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

        self.set_visible(False)
        idle_destroy_task = schedule_at_idle(idle_destroy)
        on_destroy_id = self.connect("destroy", on_destroy)

    def add_styled_button(self, button_text: str, response_id: Gtk.ResponseType, css_class: str):
        button = self.add_button(button_text, response_id)
        if css_class:
            button.add_css_class(css_class)
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
        title: str | None = None,
        parent: Gtk.Widget | None = None,
        flags: Gtk.DialogFlags = 0,
        buttons: Gtk.ButtonsType | None = None,
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
            self.set_visible(False)
            self.destroy_at_idle(condition=lambda: not self.get_visible())


class ModelessDialog(Dialog):
    """A base class for modeless dialogs. They have a parent only temporarily, so
    they can be centered over it during creation. But each modeless dialog gets
    its own window group, so it treats its own modal dialogs separately, and it resets
    its transient-for after being created."""

    def __init__(
        self,
        title: str | None = None,
        parent: Gtk.Widget | None = None,
        flags: Gtk.DialogFlags = 0,
        buttons: Gtk.ButtonsType | None = None,
        **kwargs,
    ):
        super().__init__(title, parent, flags, buttons, **kwargs)
        self._window_group = Gtk.WindowGroup()
        self._window_group.add_window(self)
        self.connect("close-request", self._on_close_request)

    def _on_close_request(self, _window):
        """Handle close-request (ESC key, window close button) by destroying
        properly. In GTK 4, Gtk.Dialog may not reliably convert close-request
        into response(DELETE_EVENT), so we handle it explicitly."""
        if not getattr(self, "_closing", False):
            self._closing = True
            self.set_visible(False)
            GLib.idle_add(self.destroy)
        return True  # prevent default close handling

    def _remove_from_app_windows(self):
        """Remove this dialog from the application's window cache so
        show_window() won't reuse a destroyed instance. In GTK 4,
        Gtk.Dialog's destroy signal is unreliable for this cleanup."""
        app = self.get_application()
        if app and hasattr(app, "app_windows"):
            keys_to_remove = [k for k, v in app.app_windows.items() if v is self]
            for k in keys_to_remove:
                del app.app_windows[k]

    def destroy(self):
        self._remove_from_app_windows()
        super().destroy()

    def on_response(self, dialog, response: Gtk.ResponseType) -> None:
        super().on_response(dialog, response)
        # Modal dialogs self-destruct, but modeless ones must commit
        # suicide more explicitly.
        if response != Gtk.ResponseType.NONE and not getattr(self, "_closing", False):
            self._closing = True
            self.set_visible(False)
            GLib.idle_add(self.destroy)


class SavableModelessDialog(ModelessDialog):
    """This is a modeless dialog that has a Cancel and a Save button in the header-bar,
    with a ctrl-S keyboard shortcut to save.

    In GTK 4, Gtk.Dialog with use_header_bar is deprecated and broken, so we
    manually create a Gtk.HeaderBar with buttons instead."""

    def __init__(self, title: str, parent: Gtk.Widget | None = None, **kwargs):
        super().__init__(title, parent=parent, **kwargs)

        self._header_bar = Gtk.HeaderBar()
        self.set_titlebar(self._header_bar)

        self.cancel_button = Gtk.Button(label=_("Cancel"))
        self.cancel_button.set_valign(Gtk.Align.CENTER)
        self.cancel_button.connect("clicked", lambda _b: self.response(Gtk.ResponseType.CANCEL))
        self._header_bar.pack_start(self.cancel_button)

        self.save_button = Gtk.Button(label=_("Save"))
        self.save_button.set_valign(Gtk.Align.CENTER)
        self.save_button.add_css_class("suggested-action")
        self.save_button.connect("clicked", self.on_save)
        self._header_bar.pack_end(self.save_button)

        # Ctrl+S shortcut for save
        controller = Gtk.ShortcutController()
        controller.set_scope(Gtk.ShortcutScope.LOCAL)
        trigger = Gtk.ShortcutTrigger.parse_string("<Primary>s")
        action = Gtk.CallbackAction.new(lambda _widget, _args: self.save_button.activate())
        controller.add_shortcut(Gtk.Shortcut(trigger=trigger, action=action))
        self.add_controller(controller)

    def get_header_bar(self):
        return self._header_bar

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
        if parent:
            self.dialog.set_transient_for(parent)
        self.dialog.connect("close-request", self.on_close)
        self.initialize(**kwargs)
        self.dialog.present()

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
                self.dialog.set_visible(False)
            except AttributeError:
                pass


class AboutDialog(GtkBuilderDialog):
    glade_file = "about-dialog.ui"
    dialog_object = "about_dialog"

    def initialize(self):  # pylint: disable=arguments-differ
        self.dialog.set_version(settings.VERSION)


class NoticeDialog(Gtk.MessageDialog):
    """Display a message to the user."""

    def __init__(self, message_markup: str, secondary: str | None = None, parent: Gtk.Widget | None = None):
        parent_window: Gtk.Window = get_widget_window(parent)
        super().__init__(message_type=Gtk.MessageType.INFO, buttons=Gtk.ButtonsType.OK)
        if parent_window:
            self.set_transient_for(parent_window)
        self.set_modal(True)
        markup = message_markup
        if secondary:
            markup += "\n\n" + secondary[:256]
        self.set_markup(markup)

        self.connect("response", lambda d, r: d.destroy())
        self.present()


class WarningDialog(Gtk.MessageDialog):
    """Display a warning to the user, who responds with whether to proceed, like
    a QuestionDialog."""

    def __init__(self, message_markup: str, secondary: str | None = None, parent: Gtk.Widget | None = None):
        parent_window: Gtk.Window = get_widget_window(parent)
        super().__init__(message_type=Gtk.MessageType.WARNING, buttons=Gtk.ButtonsType.OK_CANCEL)
        if parent_window:
            self.set_transient_for(parent_window)
        markup = message_markup
        if secondary:
            markup += "\n\n" + secondary[:256]
        self.set_markup(markup)
        self.result = _dialog_run(self)
        self.destroy()


class ErrorDialog(Gtk.MessageDialog):
    """Display an error message."""

    def __init__(
        self,
        error: str | builtins.BaseException,
        message_markup: str | None = None,
        secondary_markup: str | None = None,
        parent: Gtk.Widget | None = None,
    ):
        parent_window: Gtk.Window = get_widget_window(parent)
        super().__init__(message_type=Gtk.MessageType.ERROR, buttons=Gtk.ButtonsType.OK)
        if parent_window:
            self.set_transient_for(parent_window)

        def get_message_markup(err: BaseException | str) -> str:
            if isinstance(err, LutrisError):
                return err.message_markup or gtk_safe(str(err))
            else:
                return gtk_safe(str(err))

        if isinstance(error, builtins.BaseException):
            if secondary_markup:
                message_markup = message_markup or get_message_markup(error)
            elif not message_markup:
                message_markup = "<span weight='bold'>%s</span>" % _("Lutris has encountered an error")
                secondary_markup = get_message_markup(error)
        elif not message_markup:
            message_markup = get_message_markup(error)

        # Gtk doesn't wrap long labels containing no space correctly
        # the length of the message is limited to avoid display issues
        full_markup = ""
        if message_markup:
            full_markup = message_markup[:256]
        if secondary_markup:
            if full_markup:
                full_markup += "\n\n" + secondary_markup[:256]
            else:
                full_markup = secondary_markup[:256]
        if full_markup:
            self.set_markup(full_markup)

        # So you can copy error text
        for child in get_widget_children(self.get_message_area(), child_type=Gtk.Label):
            child.set_selectable(True)

        if isinstance(error, BaseException):
            content_area = self.get_content_area()
            spacing = content_area.get_spacing()
            content_area.set_spacing(0)

            details_expander = self.get_details_expander(error)
            details_expander.set_margin_top(spacing)
            content_area.append(details_expander)

            copy_button = Gtk.Button(label=_("Copy Details to Clipboard"))
            copy_button.connect("clicked", self.on_copy_clicked, error)
            content_area.append(copy_button)

        self.connect("response", lambda d, r: d.destroy())
        self.present()

    def on_copy_clicked(self, _button, error: BaseException):
        details = self.format_error(error)
        self.get_clipboard().set(details)

    def get_details_expander(self, error: BaseException) -> Gtk.Widget:
        details = self.format_error(error, include_message=False)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        label = Gtk.Label(xalign=0.0, wrap=True, margin_start=6, margin_end=6, margin_bottom=6)
        label.set_markup(
            _(
                "You can get support from "
                "<a href='https://github.com/lutris/lutris'>GitHub</a> or "
                "<a href='https://discordapp.com/invite/Pnt5CuY'>Discord</a>. "
                "Make sure to provide the error details;\n"
                "use the 'Copy Details to Clipboard' button to get them."
            )
        )
        box.append(label)

        expander = Gtk.Expander.new(_("Error details"))

        details_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        details_box.append(Gtk.Separator())

        details_textview = Gtk.TextView(editable=False)
        details_textview.get_buffer().set_text(details)

        details_scrolledwindow = Gtk.ScrolledWindow(width_request=800, height_request=400)
        details_scrolledwindow.set_child(details_textview)
        details_box.append(details_scrolledwindow)
        expander.set_child(details_box)

        expander.set_hexpand(True)
        expander.set_vexpand(True)
        box.append(expander)
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


def _dialog_run(dialog):
    """Run a dialog synchronously using a nested GLib.MainLoop.
    Works with any dialog that emits 'response' (Gtk.Dialog, Gtk.MessageDialog, etc.).
    Returns the Gtk.ResponseType."""
    loop = GLib.MainLoop()
    response = [Gtk.ResponseType.NONE]

    def on_response(_dialog, resp):
        response[0] = resp
        loop.quit()

    def on_close(_dialog):
        response[0] = Gtk.ResponseType.DELETE_EVENT
        if loop.is_running():
            loop.quit()
        return False

    handler_id = dialog.connect("response", on_response)
    close_id = dialog.connect("close-request", on_close)
    dialog.set_modal(True)
    dialog.present()
    loop.run()
    dialog.disconnect(handler_id)
    dialog.disconnect(close_id)
    return response[0]


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
                self.get_message_area().append(widget)
        self.result = _dialog_run(self)
        self.destroy()


class InputDialog(ModalDialog):
    """Ask the user for a text input"""

    def __init__(self, dialog_settings):
        super().__init__(parent=dialog_settings["parent"])
        self.user_value = ""
        cancel_button = self.add_button(_("_Cancel"), Gtk.ResponseType.CANCEL)
        cancel_button.set_size_request(100, -1)
        self.ok_button = self.add_default_button(_("_OK"), Gtk.ResponseType.OK)
        self.ok_button.set_size_request(100, -1)
        self.set_default_response(Gtk.ResponseType.OK)
        self.ok_button.set_sensitive(False)

        action_area = cancel_button.get_parent()
        action_area.set_spacing(6)
        action_area.set_margin_top(6)
        action_area.set_margin_bottom(6)
        action_area.set_margin_start(12)
        action_area.set_margin_end(12)
        self.set_title(dialog_settings["title"])

        content = self.get_content_area()
        content.set_margin_top(12)
        content.set_margin_bottom(12)
        content.set_margin_start(12)
        content.set_margin_end(12)
        content.set_spacing(12)

        label = Gtk.Label()
        label.set_markup(dialog_settings["question"])
        label.set_hexpand(True)
        content.append(label)

        self.entry = Gtk.Entry(activates_default=True)
        self.entry.connect("changed", self.on_entry_changed)
        self.entry.set_hexpand(True)
        content.append(self.entry)
        self.entry.set_text(dialog_settings.get("initial_value") or "")

    def on_entry_changed(self, widget):
        self.user_value = widget.get_text()
        self.ok_button.set_sensitive(bool(self.user_value))


def _file_dialog_run_sync(dialog_method, parent, initial_folder=None, filters=None):
    """Run a Gtk.FileDialog method synchronously using a nested GLib.MainLoop.
    dialog_method should be a bound method like file_dialog.select_folder or file_dialog.open.
    Returns a Gio.File or None."""
    loop = GLib.MainLoop()
    result = [None]

    def on_finish(_dialog, async_result):
        try:
            # The finish method name matches the start method
            finish_name = dialog_method.__name__ + "_finish"
            finish_func = getattr(_dialog, finish_name)
            result[0] = finish_func(async_result)
        except GLib.Error:
            pass
        loop.quit()

    dialog_method(parent, None, on_finish)
    loop.run()
    return result[0]


class DirectoryDialog:
    """Ask the user to select a directory."""

    def __init__(self, message, default_path=None, parent=None):
        self.folder = None
        dialog = Gtk.FileDialog()
        dialog.set_title(message)
        if default_path:
            folder_file = Gio.File.new_for_path(default_path)
            dialog.set_initial_folder(folder_file)

        gfile = _file_dialog_run_sync(dialog.select_folder, parent)
        if gfile:
            self.folder = gfile.get_path()
            self.result = Gtk.ResponseType.ACCEPT
        else:
            self.result = Gtk.ResponseType.CANCEL


class FileDialog:
    """Ask the user to select a file."""

    def __init__(self, message=None, default_path=None, mode="open", parent=None):
        self.filename = None
        if not message:
            message = _("Please choose a file")
        dialog = Gtk.FileDialog()
        dialog.set_title(message)
        if default_path and os.path.exists(default_path):
            folder_file = Gio.File.new_for_path(default_path)
            dialog.set_initial_folder(folder_file)

        if mode == "save":
            gfile = _file_dialog_run_sync(dialog.save, parent)
        else:
            gfile = _file_dialog_run_sync(dialog.open, parent)
        if gfile:
            self.filename = gfile.get_path()


class InstallOrPlayDialog(ModalDialog):
    def __init__(self, game_name, parent=None):
        super().__init__(title=_("%s is already installed") % game_name, parent=parent, border_width=10)
        self.action = "play"
        self.action_confirmed = False

        self.add_button(_("_Cancel"), Gtk.ResponseType.CANCEL)
        self.add_default_button(_("_OK"), Gtk.ResponseType.OK)

        self.set_size_request(320, 120)
        vbox = Gtk.Box.new(Gtk.Orientation.VERTICAL, 6)
        self.get_content_area().append(vbox)
        play_button = Gtk.CheckButton(label=_("Launch game"))
        play_button.set_active(True)
        play_button.connect("toggled", self.on_button_toggled, "play")
        vbox.append(play_button)
        install_button = Gtk.CheckButton(label=_("Install the game again"))
        install_button.set_group(play_button)
        install_button.connect("toggled", self.on_button_toggled, "install")
        vbox.append(install_button)

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

        self.add_button(_("_Cancel"), Gtk.ResponseType.CANCEL)
        self.add_default_button(_("_OK"), Gtk.ResponseType.OK)

        self.set_size_request(320, 120)
        vbox = Gtk.Box.new(Gtk.Orientation.VERTICAL, 6)
        self.get_content_area().append(vbox)

        primary_game_radio = Gtk.CheckButton(label=game.name)
        primary_game_radio.set_active(True)
        primary_game_radio.connect("toggled", self.on_button_toggled, 0)
        vbox.append(primary_game_radio)
        for i, config in enumerate(configs):
            _button = Gtk.CheckButton(label=config["name"])
            _button.set_group(primary_game_radio)
            _button.connect("toggled", self.on_button_toggled, i + 1)
            vbox.append(_button)

        dont_show_checkbutton = Gtk.CheckButton(label=_("Do not ask again for this game."))
        dont_show_checkbutton.connect("toggled", self.on_dont_show_checkbutton_toggled)
        dont_show_checkbutton.set_margin_top(6)
        dont_show_checkbutton.set_margin_bottom(6)
        vbox.append(dont_show_checkbutton)

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

        self.username_entry.connect("activate", self.on_username_entry_activate)
        self.password_entry.connect("activate", self.on_password_entry_activate)

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

        ok_button = self.add_default_button(_("_OK"), Gtk.ResponseType.OK)
        ok_button.set_margin_top(10)
        ok_button.set_margin_bottom(10)
        ok_button.set_margin_start(10)
        ok_button.set_margin_end(10)

        self.scrolled_window = Gtk.ScrolledWindow()
        self.scrolled_window.set_hexpand(True)
        self.scrolled_window.set_vexpand(True)

        source_buffer = Gtk.TextBuffer()
        source_buffer.set_text(code)

        source_box = LogTextView(source_buffer, autoscroll=False)

        self.get_content_area().append(self.scrolled_window)
        self.scrolled_window.set_child(source_box)


class HumbleBundleCookiesDialog(ModalDialog):
    def __init__(self, parent=None):
        super().__init__(_("Humble Bundle Cookie Authentication"), parent)
        self.cookies_content = None
        self.add_button(_("_Cancel"), Gtk.ResponseType.CANCEL)
        self.add_default_button(_("_OK"), Gtk.ResponseType.OK)

        self.set_size_request(640, 512)

        vbox = Gtk.Box.new(Gtk.Orientation.VERTICAL, 6)
        self.get_content_area().append(vbox)
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
        label.set_margin_top(24)
        label.set_margin_bottom(24)
        vbox.append(label)
        self.textview = Gtk.TextView()
        self.textview.set_left_margin(12)
        self.textview.set_right_margin(12)
        scrolledwindow = Gtk.ScrolledWindow()
        scrolledwindow.set_hexpand(True)
        scrolledwindow.set_vexpand(True)
        scrolledwindow.set_child(self.textview)
        scrolledwindow.set_margin_top(24)
        scrolledwindow.set_margin_bottom(24)
        vbox.append(scrolledwindow)
        self.run()

    def on_response(self, dialog, response):
        if response == Gtk.ResponseType.CANCEL:
            self.cookies_content = None
        else:
            buffer = self.textview.get_buffer()
            self.cookies_content = buffer.get_text(buffer.get_start_iter(), buffer.get_end_iter(), True)

        super().on_response(dialog, response)


def _call_when_destroyed(self: Gtk.Widget, callback: Callable[[], None]) -> Callable[[], None]:
    handler_id = self.connect("destroy", lambda *x: callback())
    return lambda: self.disconnect(handler_id)


# call_when_destroyed is a utility that hooks up the 'destroy' signal to call your callback,
# and returns a callable that unhooks it. This is used by AsyncJob to avoid sending a callback
# to a destroyed widget.
Gtk.Widget.call_when_destroyed = _call_when_destroyed  # type: ignore[attr-defined]

_error_handlers: dict[type[BaseException], Callable[[BaseException, Gtk.Window], Any]] = {}
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
        handler(error, cast(Gtk.Window, parent.get_root()))


def register_error_handler(error_class: type[TError], handler: Callable[[TError, Gtk.Window], Any]) -> None:
    """Records a function to call to handle errors of a particular class or its subclasses. The
    function is given the error and a parent window, and can display a modal dialog."""
    _error_handlers[error_class] = handler


def get_error_handler(error_class: type[TError]) -> Callable[[TError, Gtk.Window], Any]:
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
