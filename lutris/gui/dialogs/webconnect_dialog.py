"""isort:skip_file"""

import os
from gettext import gettext as _
from typing import TYPE_CHECKING

import gi

if TYPE_CHECKING:
    from lutris.services.base import OnlineService

gi.require_version("WebKit", "6.0")
from gi.repository import WebKit  # type: ignore[attr-defined]

from lutris.config import LutrisConfig
from lutris.gui.dialogs import ModalDialog
from lutris.util.log import logger


class WebConnectDialog(ModalDialog):
    """Login form for external services"""

    def __init__(self, service: "OnlineService", parent=None):
        if service.is_login_in_progress:
            # If the previous login was abandoned, remove any
            # credentials that may have been left over for a clean start-
            # this helps if the service thinks we are logged in (ie, credenial
            # cookiers remain), but Lutris does not.
            service.wipe_game_cache()

        service.is_login_in_progress = True

        # In WebKitGTK 6.0, WebContext is replaced by NetworkSession
        self.network_session: WebKit.NetworkSession = WebKit.NetworkSession.new(
            os.path.join(os.environ.get("XDG_DATA_HOME", os.path.expanduser("~/.local/share")), "lutris", "webkitgtk"),
            os.path.join(os.environ.get("XDG_CACHE_HOME", os.path.expanduser("~/.cache")), "lutris", "webkitgtk"),
        )

        # Set locale
        # Locale fallback routine:
        # Lutris locale -> System environment locale -> US English
        webview_locales = ["en_US"]
        lutris_config = LutrisConfig()
        environment_locale_lang = os.environ.get("LANG")
        if environment_locale_lang:
            webview_locales = [environment_locale_lang.split(".")[0]] + webview_locales
        lutris_locale = lutris_config.system_config.get("locale")
        if lutris_locale:
            webview_locales = [lutris_locale.split(".")[0]] + webview_locales
        logger.debug(
            f"Webview locale fallback order: "
            f"[Lutris locale]: '{lutris_locale}' -> "
            f"[env: LANG]: '{environment_locale_lang}' -> "
            f"[Default]: '{webview_locales[-1]}'"
        )

        if "http_proxy" in os.environ:
            proxy = WebKit.NetworkProxySettings.new(os.environ["http_proxy"])
            self.network_session.set_proxy_settings(WebKit.NetworkProxyMode.CUSTOM, proxy)
        cookie_manager = self.network_session.get_cookie_manager()
        cookie_manager.set_persistent_storage(
            service.cookies_path,
            WebKit.CookiePersistentStorage(0),
        )
        self.service = service

        super().__init__(title=service.name, parent=parent)

        content_area = self.get_content_area()

        self.set_default_size(self.service.login_window_width, self.service.login_window_height)

        self.webview = WebKit.WebView(network_session=self.network_session)
        self.webview.load_uri(service.login_url)
        self.webview.connect("load-changed", self.on_navigation)
        self.webview.connect("create", self.on_webview_popup)
        self.webview.connect("decide-policy", self.on_decide_policy)
        self.webview.set_hexpand(True)
        self.webview.set_vexpand(True)
        content_area.append(self.webview)
        self.connect("destroy", self.on_destroy)

        webkit_settings = self.webview.get_settings()

        # Set a User Agent
        webkit_settings.set_user_agent(service.login_user_agent)

        # Set preferred languages on the WebView
        webkit_settings.set_property("accept-language-list", ",".join(webview_locales))

        # Enable developer options for troubleshooting (Can be disabled in
        # releases)
        # webkit_settings.set_enable_write_console_messages_to_stdout(True)
        # webkit_settings.set_javascript_can_open_windows_automatically(True)
        webkit_settings.set_enable_developer_extras(True)
        webkit_settings.set_enable_webgl(False)
        # self.enable_inspector()

    def on_destroy(self, _widget):
        self.service.is_login_in_progress = False

    def enable_inspector(self):
        """If you want a full blown Webkit inspector, call this"""
        # WARNING: For some reason this doesn't work as intended.
        # The inspector shows ups but it's impossible to interact with it
        # All inputs are blocked by the the webkit dialog.
        inspector = self.webview.get_inspector()
        inspector.show()

    def on_decide_policy(self, webview, decision, decision_type):
        if decision_type == WebKit.PolicyDecisionType.NAVIGATION_ACTION:
            decision.use()
        return True

    def on_navigation(self, widget, load_event):
        if load_event == WebKit.LoadEvent.FINISHED:
            url = widget.get_uri()
            if url in self.service.scripts:
                script = self.service.scripts[url]
                widget.run_javascript(script, None, None)
                return True
            if self.service.is_login_complete(url):
                if self.service.requires_login_page:
                    resource = widget.get_main_resource()
                    resource.get_data(None, self._get_response_data_finish, None)
                else:
                    self.service.is_login_in_progress = False
                    self.service.login_callback(url)
                    self.destroy()
        return True

    def _get_response_data_finish(self, resource, result, user_data=None):
        html_response = resource.get_data_finish(result)
        self.service.is_login_in_progress = False
        self.service.login_callback(html_response)
        self.destroy()

    def on_webview_popup(self, widget, navigation_action):
        """Handles web popups created by this dialog's webview"""
        uri = navigation_action.get_request().get_uri()
        view = WebKit.WebView.new_with_related_view(widget)
        popup_dialog = WebPopupDialog(view, uri, parent=self)
        popup_dialog.show()
        return view


class WebPopupDialog(ModalDialog):
    """Dialog for handling web popups"""

    def __init__(self, webview, uri, parent=None):
        # pylint: disable=no-member
        self.parent = parent
        super().__init__(title=_("Loading..."), parent=parent)
        self.webview = webview
        self.webview.connect("ready-to-show", self.on_ready_webview)
        self.webview.connect("notify::title", self.on_available_webview_title)
        self.webview.connect("create", self.on_new_webview_popup)
        self.webview.connect("close", self.on_webview_close)
        self.webview.load_uri(uri)
        self.webview.set_hexpand(True)
        self.webview.set_vexpand(True)
        self.vbox.append(self.webview)
        self.set_default_size(390, 500)

    def on_ready_webview(self, webview):
        pass

    def on_available_webview_title(self, webview, gparamstring):
        self.set_title(webview.get_title())

    def on_new_webview_popup(self, webview, navigation_action):
        """Handles web popups created by this dialog's webview"""
        uri = navigation_action.get_request().get_uri()
        view = WebKit.WebView.new_with_related_view(webview)
        view.load_uri(uri)
        dialog = WebPopupDialog(view, uri, parent=self)
        dialog.show()
        return view

    def on_webview_close(self, webview):
        self.close()
        return True
