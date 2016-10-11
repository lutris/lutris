import json
import socket
import urllib.request
import urllib.error
import urllib.parse

from lutris.util.log import logger


class Request(object):
    def __init__(self, url, timeout=5, stop_request=None,
                 thread_queue=None, headers={}):
        self.url = url
        self.content = ''
        self.timeout = timeout
        self.stop_request = stop_request
        self.thread_queue = thread_queue
        self.buffer_size = 32 * 1024  # Bytes
        self.downloaded_size = 0
        self.headers = headers

    def get(self, data=None):
        req = urllib.request.Request(url=self.url, data=data, headers=self.headers)
        try:
            request = urllib.request.urlopen(req, timeout=self.timeout)
        except urllib.error.HTTPError as e:
            logger.error("Unavailable url (%s): %s", self.url, e)
        except (socket.timeout, urllib.error.URLError) as e:
            logger.error("Unable to connect to server (%s): %s", self.url, e)
        else:
            try:
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

    @property
    def json(self):
        if self.content:
            return json.loads(self.text)

    @property
    def text(self):
        if self.content:
            return self.content.decode()
