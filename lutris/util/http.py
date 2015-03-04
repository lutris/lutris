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
    timeout = 5
    content = None
    try:
        request = urllib2.urlopen(url, data, timeout)
    except urllib2.HTTPError as e:
        if log_errors:
            logger.error("Unavailable url (%s): %s", url, e)
    except (socket.timeout, urllib2.URLError) as e:
        if log_errors:
            logger.error("Unable to connect to server (%s): %s", url, e)
    else:
        content = request.read()
    return content


def download_json(url, params=''):
    """Download and decode json string at URL."""
    content = download_content(url + "?" + params)
    if content:
        return json.loads(content)
