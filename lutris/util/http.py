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
                 thread_queue=None, headers={}):

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
        if not isinstance(headers, dict):
            raise TypeError('HTTP headers needs to be a dict ({})'.format(headers))
        self.headers.update(headers)

    @property
    def user_agent(self):
        return '{}/{} ({} {})'.format(PROJECT, VERSION,
                                      ' '.join(platform.dist()),
                                      platform.machine())

    def get(self, data=None):
        req = urllib.request.Request(url=self.url, data=data, headers=self.headers)
        try:
            request = urllib.request.urlopen(req, timeout=self.timeout)
        except (urllib.error.HTTPError, CertificateError) as e:
            logger.error("Unavailable url (%s): %s", self.url, e)
                total_size = request.info().get('Content-Length').strip()
                total_size = int(total_size)
            except AttributeError:
                total_size = 0

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
            return json.loads(self.text)

    @property
    def text(self):
        if self.content:
            return self.content.decode()
