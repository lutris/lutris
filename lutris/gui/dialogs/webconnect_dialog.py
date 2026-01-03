"""isort:skip_file"""

import os
from gettext import gettext as _
from typing import TYPE_CHECKING

import gi

if TYPE_CHECKING:
    from lutris.services.base import OnlineService

try:
    gi.require_version("WebKit2", "4.1")
except ValueError:
    gi.require_version("WebKit2", "4.0")
from gi.repository import WebKit2  # type: ignore[attr-defined]

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

        self.context: WebKit2.WebContext = WebKit2.WebContext.new()

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
        self.context.set_preferred_languages(webview_locales)

        if "http_proxy" in os.environ:
            proxy = WebKit2.NetworkProxySettings.new(os.environ["http_proxy"])
            self.context.set_network_proxy_settings(WebKit2.NetworkProxyMode.CUSTOM, proxy)
        WebKit2.CookieManager.set_persistent_storage(
            self.context.get_cookie_manager(),
            service.cookies_path,
            WebKit2.CookiePersistentStorage(0),
        )
        self.service = service

        super().__init__(title=service.name, parent=parent)

        content_area = self.get_content_area()

        self.set_default_size(self.service.login_window_width, self.service.login_window_height)

        self.webview = WebKit2.WebView.new_with_context(self.context)
        self.webview.load_uri(service.login_url)
        self.webview.connect("load-changed", self.on_navigation)
        self.webview.connect("create", self.on_webview_popup)
        self.webview.connect("decide-policy", self.on_decide_policy)
        content_area.set_border_width(0)
        content_area.pack_start(self.webview, True, True, 0)

        webkit_settings = self.webview.get_settings()

        # Set a User Agent
        webkit_settings.set_user_agent(service.login_user_agent)

        # Allow popups (Doesn't work...)
        webkit_settings.set_allow_modal_dialogs(True)

        # Enable developer options for troubleshooting (Can be disabled in
        # releases)
        # webkit_settings.set_enable_write_console_messages_to_stdout(True)
        # webkit_settings.set_javascript_can_open_windows_automatically(True)
        webkit_settings.set_enable_developer_extras(True)
        webkit_settings.set_enable_webgl(False)
        # self.enable_inspector()
        self.show_all()

    def enable_inspector(self):
        """If you want a full blown Webkit inspector, call this"""
        # WARNING: For some reason this doesn't work as intended.
        # The inspector shows ups but it's impossible to interact with it
        # All inputs are blocked by the the webkit dialog.
        inspector = self.webview.get_inspector()
        inspector.show()

    def on_decide_policy(self, webview, decision, decision_type):
        if decision_type == WebKit2.PolicyDecisionType.NAVIGATION_ACTION:
            decision.use()
        return True

    def on_navigation(self, widget, load_event):
        if load_event == WebKit2.LoadEvent.FINISHED:
            url = widget.get_uri()
            if url in self.service.scripts:
                script = self.service.scripts[url]
                widget.run_javascript(script, None, None)
                return True
            if any(url.startswith(r) for r in self.service.redirect_uris):
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
        view = WebKit2.WebView.new_with_related_view(widget)
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
        self.vbox.pack_start(self.webview, True, True, 0)
        self.vbox.set_border_width(0)
        self.set_default_size(390, 500)

    def on_ready_webview(self, webview):
        self.show_all()

    def on_available_webview_title(self, webview, gparamstring):
        self.set_title(webview.get_title())

    def on_new_webview_popup(self, webview, navigation_action):
        """Handles web popups created by this dialog's webview"""
        uri = navigation_action.get_request().get_uri()
        view = WebKit2.WebView.new_with_related_view(webview)
        view.load_uri(uri)
        dialog = WebPopupDialog(view, uri, parent=self)
        dialog.show()
        return view

    def on_webview_close(self, webview):
        self.close()
        return True
