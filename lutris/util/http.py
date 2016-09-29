import os
import json
import socket
import urllib.request
import urllib.error
import urllib.parse

from lutris.util.log import logger


def download_asset(url, dest, overwrite=False, stop_request=None):
    if os.path.exists(dest):
        if overwrite:
            os.remove(dest)
        else:
            logger.info("Destination %s exists, not overwriting" % dest)
            return
    # TODO: Downloading icons and banners makes a bunch of useless http
    # requests + it's really slow
    content = download_content(url, log_errors=False,
                               stop_request=stop_request)
    if content:
        with open(dest, 'wb') as dest_file:
            dest_file.write(content)
        return True
    else:
        return False


def download_content(url, data=None, log_errors=True, stop_request=None):
    request = Request(url, log_errors, stop_request=stop_request).get(data)
    return request.content


def download_json(url, params=''):
    """Download and decode json string at URL."""
    if params:
        url = url + "?" + params
    content = download_content(url)
    if content:
        return json.loads(content)


class Request(object):
    def __init__(self, url, error_logging=True, timeout=5, stop_request=None,
                 thread_queue=None, headers={}):
        self.url = url
        self.error_logging = error_logging
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
            if self.error_logging:
                logger.error("Unavailable url (%s): %s", self.url, e)
        except (socket.timeout, urllib.error.URLError) as e:
            if self.error_logging:
                logger.error("Unable to connect to server (%s): %s",
                             self.url, e)
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
                chunk = request.read(self.buffer_size)
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
