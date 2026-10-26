import urllib.request
from http.cookiejar import CookieJar
from unittest import TestCase
from unittest.mock import patch

from gi.repository import GLib

from lutris.util import http


class FakeProxyResolver:
    """Stands in for Gio.ProxyResolver in the tests."""

    def __init__(self, proxies=None, error=None):
        self.proxies = proxies if proxies is not None else []
        self.error = error

    def lookup(self, url, cancellable=None):
        if self.error:
            raise self.error
        return self.proxies


def _opener_handlers(opener):
    return list(opener.handlers)


class TestGetSystemProxy(TestCase):
    def _get_proxy(self, resolver, url="https://lutris.net/api/runners/wine"):
        with (
            patch.object(http.urllib.request, "getproxies", return_value={}),
            patch.object(http.Gio.ProxyResolver, "get_default", return_value=resolver),
        ):
            return http.get_system_proxy(url)

    def test_returns_the_proxy_from_the_desktop_settings(self):
        resolver = FakeProxyResolver(["http://127.0.0.1:8080"])

        self.assertEqual(self._get_proxy(resolver), "http://127.0.0.1:8080")

    def test_returns_none_when_the_desktop_uses_a_direct_connection(self):
        self.assertIsNone(self._get_proxy(FakeProxyResolver(["direct://"])))

    def test_returns_none_without_a_resolver(self):
        self.assertIsNone(self._get_proxy(None))

    def test_skips_socks_proxies(self):
        resolver = FakeProxyResolver(["socks5://127.0.0.1:1080", "http://127.0.0.1:8080"])

        self.assertEqual(self._get_proxy(resolver), "http://127.0.0.1:8080")

    def test_returns_none_when_the_lookup_fails(self):
        resolver = FakeProxyResolver(error=GLib.Error("proxy lookup failed"))

        self.assertIsNone(self._get_proxy(resolver))

    def test_leaves_environment_proxies_to_urllib(self):
        resolver = FakeProxyResolver(["http://127.0.0.1:8080"])

        with (
            patch.object(http.urllib.request, "getproxies", return_value={"http": "http://proxy:3128"}),
            patch.object(http.Gio.ProxyResolver, "get_default", return_value=resolver),
        ):
            self.assertIsNone(http.get_system_proxy("https://lutris.net/"))


class TestProxyHandler(TestCase):
    def test_handler_targets_the_url_scheme(self):
        with patch.object(http, "get_system_proxy", return_value="http://127.0.0.1:8080"):
            handler = http.get_proxy_handler("https://lutris.net/api/runners/wine")

        self.assertIsInstance(handler, urllib.request.ProxyHandler)
        self.assertEqual(handler.proxies, {"https": "http://127.0.0.1:8080"})

    def test_no_handler_without_a_proxy(self):
        with patch.object(http, "get_system_proxy", return_value=None):
            self.assertIsNone(http.get_proxy_handler("https://lutris.net/"))

    def test_request_uses_the_proxy_handler(self):
        with patch.object(http, "get_system_proxy", return_value="http://127.0.0.1:8080"):
            request = http.Request("https://lutris.net/api/runners/wine")

        proxy_handlers = [h for h in _opener_handlers(request.opener) if isinstance(h, urllib.request.ProxyHandler)]
        self.assertEqual(len(proxy_handlers), 1)
        self.assertEqual(proxy_handlers[0].proxies, {"https": "http://127.0.0.1:8080"})

    def test_request_without_a_proxy_keeps_the_default_opener(self):
        with patch.object(http, "get_system_proxy", return_value=None):
            request = http.Request("https://lutris.net/api/runners/wine")

        self.assertIsNone(request.opener)


class TestGetOpener(TestCase):
    def test_returns_an_opener_with_the_proxy_handler(self):
        with patch.object(http, "get_system_proxy", return_value="http://127.0.0.1:8080"):
            opener = http.get_opener("https://lutris.net/")

        proxy_handlers = [h for h in _opener_handlers(opener) if isinstance(h, urllib.request.ProxyHandler)]
        self.assertEqual(len(proxy_handlers), 1)
        self.assertEqual(proxy_handlers[0].proxies, {"https": "http://127.0.0.1:8080"})

    def test_returns_none_without_a_proxy_or_handlers(self):
        with patch.object(http, "get_system_proxy", return_value=None):
            self.assertIsNone(http.get_opener("https://lutris.net/"))

    def test_passes_extra_handlers_through(self):
        cookie_processor = urllib.request.HTTPCookieProcessor(CookieJar())

        with patch.object(http, "get_system_proxy", return_value=None):
            opener = http.get_opener("https://lutris.net/", cookie_processor)

        self.assertIn(cookie_processor, _opener_handlers(opener))


class TestGetRequestProxies(TestCase):
    def test_returns_a_mapping_for_both_schemes(self):
        with patch.object(http, "get_system_proxy", return_value="http://127.0.0.1:8080"):
            self.assertEqual(
                http.get_request_proxies("https://lutris.net/"),
                {"http": "http://127.0.0.1:8080", "https": "http://127.0.0.1:8080"},
            )

    def test_returns_an_empty_mapping_without_a_proxy(self):
        with patch.object(http, "get_system_proxy", return_value=None):
            self.assertEqual(http.get_request_proxies("https://lutris.net/"), {})
