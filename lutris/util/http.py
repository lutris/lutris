import os
import urllib

from lutris.util.log import logger


class RessourceOpener(urllib.FancyURLopener):
    def http_error_default(self, url, fp, errcode, errmsg, headers):
        if errcode in (404, 500):
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
