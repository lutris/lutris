"""HTTP utilities"""
import json
import os
import socket
import urllib.error
import urllib.parse
import urllib.request
from ssl import CertificateError

from lutris.settings import PROJECT, SITE_URL, VERSION, read_setting
from lutris.util import system
from lutris.util.log import logger

DEFAULT_TIMEOUT = read_setting("default_http_timeout") or 30


class HTTPError(Exception):
    """Exception raised on request failures"""

    def __init__(self, message, code=None):
        super().__init__(message)
        self.code = code


class UnauthorizedAccess(Exception):
    """Exception raised for 401 HTTP errors"""


class Request:

    def __init__(
        self,
        url,
        timeout=DEFAULT_TIMEOUT,
        stop_request=None,
        headers=None,
        cookies=None,
    ):
        self.url = self._clean_url(url)
        self.status_code = None
        self.content = b""
        self.timeout = timeout
        self.stop_request = stop_request
        self.buffer_size = 1024 * 1024  # Bytes
        self.total_size = None
        self.downloaded_size = 0
        self.headers = {"User-Agent": self.user_agent}
        self.response_headers = None
        self.info = None
        if headers is None:
            headers = {}
        if not isinstance(headers, dict):
            raise TypeError("HTTP headers needs to be a dict ({})".format(headers))
        self.headers.update(headers)
        if cookies:
            cookie_processor = urllib.request.HTTPCookieProcessor(cookies)
            self.opener = urllib.request.build_opener(cookie_processor)
        else:
            self.opener = None

    @staticmethod
    def _clean_url(url):
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
    def user_agent(self):
        return "{} {}".format(PROJECT, VERSION)

    def get(self, data=None):
        logger.debug("GET %s", self.url)
        try:
            req = urllib.request.Request(url=self.url, data=data, headers=self.headers)
        except ValueError as ex:
            raise HTTPError("Failed to create HTTP request to %s: %s" % (self.url, ex)) from ex
        try:
            if self.opener:
                request = self.opener.open(req, timeout=self.timeout)
            else:
                request = urllib.request.urlopen(req, timeout=self.timeout)  # pylint: disable=consider-using-with
        except (urllib.error.HTTPError, CertificateError) as error:
            if error.code == 401:
                raise UnauthorizedAccess("Access to %s denied" % self.url) from error
            raise HTTPError("%s" % error, code=error.code) from error
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

    def _iter_chunks(self, request):
        while 1:
            if self.stop_request and self.stop_request.is_set():
                self.content = b""
                return self
            try:
                chunk = request.read(self.buffer_size)
            except (socket.timeout, ConnectionResetError) as err:
                raise HTTPError("Request timed out") from err
            self.downloaded_size += len(chunk)
            if not chunk:
                return
            yield chunk

    def post(self, data):
        raise NotImplementedError

    def write_to_file(self, path):
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
    def json(self):
        _raw_json = self.text
        if _raw_json:
            try:
                return json.loads(_raw_json)
            except json.decoder.JSONDecodeError as err:
                raise ValueError(f"JSON response from {self.url} could not be decoded: '{_raw_json[:80]}'") from err
        return {}

    @property
    def text(self):
        if self.content:
            return self.content.decode()
        return ""


def download_file(url, dest, overwrite=False, raise_errors=False):
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
