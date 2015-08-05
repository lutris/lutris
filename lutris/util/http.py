import os
import json
import socket
import urllib2

from lutris.util.log import logger


def download_asset(url, dest, overwrite=False):
    if os.path.exists(dest):
        if overwrite:
            os.remove(dest)
        else:
            logger.info("Destination %s exists, not overwritting" % dest)
            return
    # TODO: Downloading icons and banners makes a bunch of useless http
    # requests + it's really slow
    content = download_content(url, log_errors=False)
    if content:
        with open(dest, 'w') as dest_file:
            dest_file.write(content)
        return True
    else:
        return False


def download_content(url, data=None, log_errors=True):
    request = Request(url, log_errors).get(data)
    return request.content


def download_json(url, params=''):
    """Download and decode json string at URL."""
    if params:
        url = url + "?" + params
    content = download_content(url)
    if content:
        return json.loads(content)


class Request(object):

    def __init__(self, url, error_logging=True, timeout=5):
        self.url = url
        self.error_logging = error_logging
        self.content = None
        self.timeout = timeout

    def get(self, data=None):
        try:
            request = urllib2.urlopen(self.url, data, self.timeout)
        except urllib2.HTTPError as e:
            if self.error_logging:
                logger.error("Unavailable url (%s): %s", self.url, e)
        except (socket.timeout, urllib2.URLError) as e:
            if self.error_logging:
                logger.error("Unable to connect to server (%s): %s",
                             self.url, e)
        else:
            self.content = request.read()
        return self

    def post(self, data):
        pass

    @property
    def json(self):
        if self.content:
            return json.loads(self.content)
