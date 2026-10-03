"""Notifications shown by the main window, and the account/service signals that drive them.

These are grouped into a mixin so that LutrisWindow keeps the template callbacks bound to
itself while the notification logic lives apart from the view lifecycle.
"""

from gettext import gettext as _

from gi.repository import Gtk

from lutris import settings
from lutris.api import get_runtime_versions, read_api_key
from lutris.gui import dialogs
from lutris.gui.widgets.gi_composites import GtkTemplate


class NotificationMixin:
    """Shows the login and unsupported-version notifications, and reacts to account changes."""

    def update_notification(self):
        show_notification = (
            self.is_showing_splash()
            and not read_api_key()
            and not settings.read_bool_setting("dismissed_login_notification")
        )
        if show_notification:
            self.lutris_log_in_label.show()
        self.login_notification_revealer.set_reveal_child(show_notification)

    @GtkTemplate.Callback
    def on_lutris_log_in_label_activate_link(self, _label, _url):
        def on_connect_success(widget, _username):
            self.sync_library(force=True)

        self.login_notification_revealer.set_reveal_child(False)
        login_dialog = dialogs.ClientLoginDialog(parent=self)
        login_dialog.connect("connected", on_connect_success)

    def on_login_notification_close_button_clicked(self, _button):
        settings.write_setting("dismissed_login_notification", True)
        self.login_notification_revealer.set_reveal_child(False)

    def on_version_notification_close_button_clicked(self, _button):
        dialog = dialogs.QuestionDialog(
            {
                "title": _("Unsupported Lutris Version"),
                "question": _(
                    "This version of Lutris will no longer receive support on Github and Discord, "
                    "and may not interoperate properly with Lutris.net. Do you want to use it anyway?"
                ),
                "parent": self,
            }
        )

        if dialog.result == Gtk.ResponseType.YES:
            self.version_notification_revealer.set_reveal_child(False)
            runtime_versions = get_runtime_versions()
            if runtime_versions:
                client_version = runtime_versions.get("client_version")
                settings.write_setting("ignored_supported_lutris_version", client_version or "")

    def on_service_login(self, service):
        self.update_notification()
        service.start_reload(self._service_reloaded_cb)
        return True

    def _service_reloaded_cb(self, error):
        if error:
            dialogs.display_error(error, parent=self)

    def on_service_logout(self, service):
        self.update_notification()
        if self.service and service.id == self.service.id:
            self.update_store()
        return True

    def on_lutris_account_connected(self):
        self.update_notification()
        self.sync_library(force=True)

    def on_lutris_account_disconnected(self):
        self.update_notification()
