import json
import socket
import urllib.request
import urllib.error
import urllib.parse
from ssl import CertificateError

from lutris.settings import SITE_URL, VERSION, PROJECT
from lutris.util.log import logger


class HTTPError(Exception):
    """Exception raised on request failures"""


class UnauthorizedAccess(Exception):
    """Exception raised for 401 HTTP errors"""


class Request:
    def __init__(
            self,
            url,
            timeout=30,
            stop_request=None,
            headers=None,
            cookies=None,
    ):

        if not url:
            raise ValueError("An URL is required!")

        if url.startswith("//"):
            url = "https:" + url

        if url.startswith("/"):
            url = SITE_URL + url

        self.url = url
        self.status_code = None
        self.content = b""
        self.timeout = timeout
        self.stop_request = stop_request
        self.buffer_size = 1024 * 1024  # Bytes
        self.total_size = None
        self.downloaded_size = 0
        self.headers = {"User-Agent": self.user_agent}
        self.response_headers = None
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

    @property
    def user_agent(self):
        return "{} {}".format(PROJECT, VERSION)

    def get(self, data=None):
        logger.debug("GET %s", self.url)
        req = urllib.request.Request(url=self.url, data=data, headers=self.headers)
        try:
            if self.opener:
                request = self.opener.open(req, timeout=self.timeout)
            else:
                request = urllib.request.urlopen(req, timeout=self.timeout)
        except (urllib.error.HTTPError, CertificateError) as error:
            if error.code == 401:
                raise UnauthorizedAccess("Access to %s denied" % self.url)
            raise HTTPError("Request to %s failed: %s" % (self.url, error))
        except (socket.timeout, urllib.error.URLError) as error:
            raise HTTPError("Unable to connect to server %s: %s" % (self.url, error))
        if request.getcode() > 200:
            logger.debug("Server responded with status code %s", request.getcode())
        try:
            self.total_size = int(request.info().get("Content-Length").strip())
        except AttributeError:
            logger.warning("Failed to read response's content length")
            self.total_size = 0

        self.response_headers = request.getheaders()
        self.status_code = request.getcode()
        if self.status_code > 299:
            logger.warning("Request responded with code %s", self.status_code)
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
            except socket.timeout:
                raise HTTPError("Request timed out")
            self.downloaded_size += len(chunk)
            if not chunk:
                return
            yield chunk

    def post(self, data):
        raise NotImplementedError

    def write_to_file(self, path):
        content = self.content
        if content:
            with open(path, "wb") as dest_file:
                dest_file.write(content)

    @property
    def json(self):
        if self.content:
            try:
                return json.loads(self.text)
            except json.decoder.JSONDecodeError:
                raise ValueError(
                    "Invalid response ({}:{}): {}".format(
                        self.url, self.status_code, self.text[:80]
                    )
                )
        return {}

    @property
    def text(self):
        if self.content:
            return self.content.decode()
        return ""
