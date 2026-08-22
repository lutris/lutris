"""Tests for the proxy configuration module."""

import os
from unittest import TestCase
from unittest.mock import patch

from lutris.util import proxy


class ProxyTestCase(TestCase):
    """Base class that isolates each test from the real settings and environment."""

    def setUp(self):
        self.settings = {}
        patcher = patch.object(proxy, "read_setting", lambda key, default="": self.settings.get(key, default))
        patcher.start()
        self.addCleanup(patcher.stop)

        environ = {name: "" for name in proxy.PROXY_ENVIRONMENT_VARIABLES}
        patcher = patch.dict(os.environ, environ)
        patcher.start()
        self.addCleanup(patcher.stop)
        for name in proxy.PROXY_ENVIRONMENT_VARIABLES:
            del os.environ[name]


class TestGetProxyUrl(ProxyTestCase):
    def test_unset_proxy_is_empty(self):
        self.assertEqual(proxy.get_proxy_url(), "")

    def test_blank_proxy_is_empty(self):
        self.settings["proxy_url"] = "   "
        self.assertEqual(proxy.get_proxy_url(), "")

    def test_bare_host_and_port_gets_a_scheme(self):
        self.settings["proxy_url"] = "proxy.example.com:8080"
        self.assertEqual(proxy.get_proxy_url(), "http://proxy.example.com:8080")

    def test_full_url_is_left_alone(self):
        self.settings["proxy_url"] = "  socks5://proxy.example.com:1080  "
        self.assertEqual(proxy.get_proxy_url(), "socks5://proxy.example.com:1080")


class TestGetIgnoredHostList(ProxyTestCase):
    def test_unset_list_is_empty(self):
        self.assertEqual(proxy.get_ignored_host_list(), [])

    def test_entries_are_split_and_stripped(self):
        self.settings["proxy_ignore_hosts"] = "localhost, 127.0.0.1 , .example.com,"
        self.assertEqual(proxy.get_ignored_host_list(), ["localhost", "127.0.0.1", ".example.com"])


class TestApplyToEnvironment(ProxyTestCase):
    def test_configured_proxy_is_applied(self):
        self.settings["proxy_url"] = "proxy.example.com:8080"
        self.settings["proxy_ignore_hosts"] = "localhost"
        proxy.apply_to_environment()
        self.assertEqual(os.environ["http_proxy"], "http://proxy.example.com:8080")
        self.assertEqual(os.environ["https_proxy"], "http://proxy.example.com:8080")
        self.assertEqual(os.environ["no_proxy"], "localhost")

    def test_configured_proxy_clears_upper_case_variables(self):
        os.environ["HTTP_PROXY"] = "http://inherited.example.com:3128"
        self.settings["proxy_url"] = "http://proxy.example.com:8080"
        proxy.apply_to_environment()
        self.assertNotIn("HTTP_PROXY", os.environ)
        self.assertEqual(os.environ["http_proxy"], "http://proxy.example.com:8080")

    def test_empty_ignore_list_leaves_no_proxy_unset(self):
        self.settings["proxy_url"] = "http://proxy.example.com:8080"
        proxy.apply_to_environment()
        self.assertNotIn("no_proxy", os.environ)

    def test_unset_proxy_restores_the_inherited_environment(self):
        with patch.object(proxy, "_INHERITED_ENVIRONMENT", {"http_proxy": "http://inherited.example.com:3128"}):
            self.settings["proxy_url"] = "http://proxy.example.com:8080"
            proxy.apply_to_environment()
            self.assertEqual(os.environ["http_proxy"], "http://proxy.example.com:8080")

            self.settings["proxy_url"] = ""
            proxy.apply_to_environment()
            self.assertEqual(os.environ["http_proxy"], "http://inherited.example.com:3128")
            self.assertNotIn("https_proxy", os.environ)


class TestRedactCredentials(TestCase):
    def test_url_without_credentials_is_unchanged(self):
        self.assertEqual(proxy.redact_credentials("http://proxy.example.com:8080"), "http://proxy.example.com:8080")

    def test_credentials_are_replaced(self):
        self.assertEqual(
            proxy.redact_credentials("http://user:hunter2@proxy.example.com:8080"),
            "http://REDACTED@proxy.example.com:8080",
        )

    def test_port_is_optional(self):
        self.assertEqual(
            proxy.redact_credentials("http://user:hunter2@proxy.example.com"),
            "http://REDACTED@proxy.example.com",
        )
