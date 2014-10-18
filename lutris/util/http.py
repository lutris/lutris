import os
import json
import socket
import urllib
import urllib2

from lutris.util.log import logger


class RessourceOpener(urllib.FancyURLopener):
    def http_error_default(self, url, fp, errcode, errmsg, headers):
        if errcode >= 400:
            raise IOError(errmsg, errcode, url)


def download_asset(url, dest, overwrite=False):
    asset_opener = RessourceOpener()
    if os.path.exists(dest):
        if overwrite:
            os.remove(dest)
        else:
            logger.info("Destination %s exists, not overwritting" % dest)
            return
    try:
        asset_opener.retrieve(url, dest)
    except IOError as ex:
        if ex[1] != 404:
            logger.error("Error while fetching %s: %s" % (url, ex))
        return False
    return True


def download_content(url, data=None):
    timeout = 5
    content = None
    try:
        request = urllib2.urlopen(url, data, timeout)
    except urllib2.HTTPError as e:
        logger.error("Unavailable url (%s): %s", url, e)
    except (socket.timeout, urllib2.URLError) as e:
        logger.error("Unable to connect to server (%s): %s", url, e)
    else:
        content = request.read()
    return content


def download_json(url, params=''):
    """Download and decode json string at URL."""
    content = download_content(url + "?" + params)
    if content:
        return json.loads(content)
