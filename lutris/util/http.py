import json
import socket
import platform
import urllib.request
import urllib.error
import urllib.parse
from ssl import CertificateError

from lutris.settings import SITE_URL, VERSION, PROJECT
from lutris.util.log import logger


class Request(object):
    def __init__(self, url, timeout=30, stop_request=None,
                 thread_queue=None, headers={}, cookies=None):

        if not url:
            raise ValueError('An URL is required!')

        if url.startswith('//'):
            url = 'https:' + url

        if url.startswith('/'):
            url = SITE_URL + url

        self.url = url
        self.content = ''
        self.timeout = timeout
        self.stop_request = stop_request
        self.thread_queue = thread_queue
        self.buffer_size = 32 * 1024  # Bytes
        self.downloaded_size = 0
        self.headers = {
            'User-Agent': self.user_agent
        }
        self.response_headers = None
        if not isinstance(headers, dict):
            raise TypeError('HTTP headers needs to be a dict ({})'.format(headers))
        self.headers.update(headers)
        if cookies:
            cookie_processor = urllib.request.HTTPCookieProcessor(cookies)
            self.opener = urllib.request.build_opener(cookie_processor)
        else:
            self.opener = None

    @property
    def user_agent(self):
        return '{}/{} ({} {})'.format(PROJECT, VERSION,
                                      ' '.join(platform.dist()),
                                      platform.machine())

    def get(self, data=None):
        req = urllib.request.Request(url=self.url, data=data, headers=self.headers)
        try:
            if self.opener:
                request = self.opener.open(req, timeout=self.timeout)
            else:
                request = urllib.request.urlopen(req, timeout=self.timeout)
        except (urllib.error.HTTPError, CertificateError) as e:
            logger.error("Unavailable url (%s): %s", self.url, e)
        except (socket.timeout, urllib.error.URLError) as e:
            logger.error("Unable to connect to server (%s): %s", self.url, e)
        else:
            try:
                total_size = request.info().get('Content-Length').strip()
                total_size = int(total_size)
            except AttributeError:
                total_size = 0

            self.response_headers = request.getheaders()
            self.status_code = request.getcode()
            chunks = []
            while 1:
                if self.stop_request and self.stop_request.is_set():
                    self.content = ''
                    return self
                try:
                    chunk = request.read(self.buffer_size)
                except socket.timeout as e:
                    logger.error("Request timed out")
                    self.content = ''
                    return self
                self.downloaded_size += len(chunk)
                if self.thread_queue:
                    self.thread_queue.put(
                        (chunk, self.downloaded_size, total_size)
                    )
                else:
                    chunks.append(chunk)
                if not chunk:
                    break
            request.close()
            self.content = b''.join(chunks)
            self.info = request.info()
        return self

    def post(self, data):
        raise NotImplementedError

    def write_to_file(self, path):
        content = self.content
        if content:
            with open(path, 'wb') as dest_file:
                dest_file.write(content)

    @property
    def json(self):
        if self.content:
            try:
                return json.loads(self.text)
            except json.decoder.JSONDecodeError:
                raise ValueError("Invalid response ({}:{}): {}".format(
                    self.url, self.status_code, self.text[:80]
                ))

    @property
    def text(self):
        if self.content:
            return self.content.decode()
