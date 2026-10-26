"""HTTP utilities"""

import json
import os
import socket
import ssl
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Collection, Generator
from ssl import CertificateError
from typing import TYPE_CHECKING, Any

import certifi
from gi.repository import Gio, GLib

from lutris.settings import PROJECT, SITE_URL, VERSION, read_setting
from lutris.util import system
from lutris.util.log import logger

if TYPE_CHECKING:
    import threading
    from http.client import HTTPResponse
    from http.cookiejar import CookieJar

DEFAULT_TIMEOUT = read_setting("default_http_timeout") or 30


def _create_ssl_context() -> ssl.SSLContext:
    return ssl.create_default_context(cafile=certifi.where())


ssl._create_default_https_context = _create_ssl_context


def get_system_proxy(url: str) -> str | None:
    """Return the proxy URI the desktop environment would use for 'url', if any.

    GLib's proxy resolver goes through libproxy when it is installed, which reads the
    KDE and GNOME proxy settings as well as PAC and WPAD configuration. Without
    libproxy it only reports the proxy environment variables, which urllib already
    honours by itself; those are left alone so that 'no_proxy' keeps its meaning.
    """
    if urllib.request.getproxies():
        return None

    resolver = Gio.ProxyResolver.get_default()
    if not resolver:
        return None

    try:
        proxies = resolver.lookup(url, None)
    except GLib.Error as ex:
        logger.debug("Could not resolve a proxy for %s: %s", url, ex)
        return None

    for proxy in proxies or []:
        if not proxy or proxy == "direct://":
            continue
        scheme = urllib.parse.urlparse(proxy).scheme
        if scheme.startswith("socks"):
            # urllib needs PySocks for SOCKS proxies, which Lutris does not depend on.
            logger.debug("Ignoring %s proxy %s for %s", scheme, proxy, url)
            continue
        return proxy
    return None


def get_proxy_handler(url: str) -> urllib.request.ProxyHandler | None:
    """Return a urllib proxy handler for 'url', honouring the desktop proxy settings."""
    proxy = get_system_proxy(url)
    if not proxy:
        return None
    scheme = urllib.parse.urlparse(url).scheme or "https"
    logger.debug("Using proxy %s for %s", proxy, url)
    return urllib.request.ProxyHandler({scheme: proxy})


def get_opener(url: str, *handlers: urllib.request.BaseHandler) -> urllib.request.OpenerDirector | None:
    """Return an url opener that honours the desktop proxy settings for 'url'.

    Returns None when there is nothing to add to urllib's default opener.
    """
    proxy_handler = get_proxy_handler(url)
    if proxy_handler:
        handlers = (*handlers, proxy_handler)
    if not handlers:
        return None
    return urllib.request.build_opener(*handlers)


def get_request_proxies(url: str) -> dict[str, str]:
    """Return a 'proxies' mapping for requests, from the desktop proxy settings."""
    proxy = get_system_proxy(url)
    if not proxy:
        return {}
    return {"http": proxy, "https": proxy}


class HTTPError(Exception):
    """Exception raised on request failures"""

    def __init__(self, message: str, code: int | None = None):
        super().__init__(message)
        self.code = code


class UnauthorizedAccessError(Exception):
    """Exception raised for 401 HTTP errors"""


class Request:
    def __init__(
        self,
        url: str,
        timeout: int = DEFAULT_TIMEOUT,
        stop_request: "threading.Event | None" = None,
        headers: dict[str, str] | None = None,
        cookies: "CookieJar | None" = None,
        redacted_query_parameters: Collection[str] | None = None,
    ):
        self.url = self._clean_url(url)
        self.status_code: int | None = None
        self.content = b""
        self.timeout = timeout
        self.stop_request = stop_request
        self.buffer_size = 1024 * 1024  # Bytes
        self.total_size = None
        self.downloaded_size = 0
        self.headers = {"User-Agent": self.user_agent}
        self.response_headers = None
        self.info = None
        self.redacted_query_parameters = redacted_query_parameters
        if headers is None:
            headers = {}
        if not isinstance(headers, dict):
            raise TypeError("HTTP headers needs to be a dict ({})".format(headers))
        self.headers.update(headers)
        handlers = (urllib.request.HTTPCookieProcessor(cookies),) if cookies else ()
        self.opener = get_opener(self.url, *handlers)

    @staticmethod
    def _clean_url(url: str) -> str:
        """Checks that a given URL is valid and return a usable version"""
        if not url:
            raise ValueError("An URL is required!")
        if url == "None":
            raise ValueError("You'd better stop that right now.")
        if url.startswith("//"):
            url = "https:" + url
        if url.startswith("/"):
            logger.error("Stop using relative URLs!: %s", url)
            url = SITE_URL + url
        # That's for a single URL in EGS... not sure if we need more escaping
        # The url received should already be receiving an escaped string
        url = url.replace(" ", "%20")
        return url

    @property
    def user_agent(self) -> str:
        return "{} {}".format(PROJECT, VERSION)

    @property
    def redacted_url(self) -> str:
        """A version of the ULR with specified query string parameters
        replaced with REDACTED for security. We log these."""
        if self.redacted_query_parameters:
            parsed = urllib.parse.urlparse(self.url)
            query_items = urllib.parse.parse_qsl(parsed.query)
            new_query_items = []
            redacted_any = False
            for key, value in query_items:
                if key in self.redacted_query_parameters:
                    redacted_any = True
                    value = "REDACTED"
                new_query_items.append((key, value))

            if redacted_any:
                parsed_parts = list(parsed)
                parsed_parts[4] = urllib.parse.urlencode(new_query_items)
                parsed = tuple(parsed_parts)
                return urllib.parse.urlunparse(parsed)

        return self.url

    def _request(self, method: str, data: bytes | None = None) -> "Request":
        logger.debug("%s %s", method, self.redacted_url)
        try:
            req = urllib.request.Request(url=self.url, data=data, headers=self.headers, method=method)
        except ValueError as ex:
            raise HTTPError("Failed to create HTTP request to %s: %s" % (self.url, ex)) from ex
        try:
            if self.opener:
                request = self.opener.open(req, timeout=self.timeout)
            else:
                request = urllib.request.urlopen(req, timeout=self.timeout)  # pylint: disable=consider-using-with
        except urllib.error.HTTPError as error:
            if error.code == 401:
                raise UnauthorizedAccessError("Access to %s denied" % self.url) from error
            raise HTTPError("%s" % error, code=error.code) from error
        except CertificateError as error:
            raise HTTPError("%s" % error, code=0) from error
        except (socket.timeout, urllib.error.URLError) as error:
            raise HTTPError("Unable to connect to server %s: %s" % (self.url, error)) from error

        self.response_headers = request.getheaders()
        self.status_code = request.getcode()
        if self.status_code > 299:
            logger.warning("Request responded with code %s", self.status_code)

        try:
            self.total_size = int(request.info().get("Content-Length").strip())
        except AttributeError:
            self.total_size = 0

        self.content = b"".join(self._iter_chunks(request))
        self.info = request.info()
        request.close()
        return self

    def _iter_chunks(self, request: "HTTPResponse") -> Generator[bytes, None, bytes]:
        while 1:
            if self.stop_request and self.stop_request.is_set():
                self.content = b""
                return b""
            try:
                chunk = request.read(self.buffer_size)
            except (socket.timeout, ConnectionResetError) as err:
                raise HTTPError("Request timed out") from err
            self.downloaded_size += len(chunk)
            if not chunk:
                return b""
            yield chunk

    def get(self, data: bytes | None = None) -> "Request":
        return self._request("GET", data)

    def post(self, data: bytes | None = None) -> "Request":
        return self._request("POST", data)

    def delete(self, data: bytes | None = None) -> "Request":
        return self._request("DELETE", data)

    def write_to_file(self, path: str) -> None:
        content = self.content
        logger.debug("Writing to %s", path)
        if not content:
            logger.warning("No content to write")
            return
        dirname = os.path.dirname(path)
        if not system.path_exists(dirname):
            os.makedirs(dirname)
        with open(path, "wb") as dest_file:
            dest_file.write(content)

    @property
    def json(self) -> Any:
        _raw_json = self.text
        if _raw_json:
            try:
                return json.loads(_raw_json)
            except json.decoder.JSONDecodeError as err:
                raise ValueError(f"JSON response from {self.url} could not be decoded: '{_raw_json[:80]}'") from err
        return {}

    @property
    def text(self) -> str:
        if self.content:
            return self.content.decode()
        return ""


def download_file(url: str, dest: str, overwrite: bool = False, raise_errors: bool = False) -> str | None:
    """Save a remote resource locally"""
    if system.path_exists(dest):
        if overwrite:
            os.remove(dest)
        else:
            return dest
    if not url:
        return None
    try:
        request = Request(url).get()
    except HTTPError as ex:
        if raise_errors:
            raise
        logger.error("Failed to get url %s: %s", url, ex)
        return None
    request.write_to_file(dest)
    return dest
