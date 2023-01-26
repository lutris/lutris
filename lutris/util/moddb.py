"""Helper functions to assist downloading files from ModDB"""
import importlib
import re
import types

from lutris.util.log import logger

MODDB_FQDN = 'https://www.moddb.com'
MODDB_URL_MATCHER = r"^https://(www\.)?moddb\.com"
MODDB_MIRROR_URL_MATCHER = r"^https://(www\.)?moddb\.com/downloads/mirror"


def is_moddb_url(url):
    return re.match(MODDB_URL_MATCHER, url.lower()) is not None


def _try_import_moddb_library():
    try:
        lib = importlib.import_module('moddb')
        return lib
    except ImportError:
        # no logging works here for some reason
        return None


class ModDB:
    def __init__(
            self,
            moddb_lib: types.ModuleType = _try_import_moddb_library(),
            parse_page_method: types.MethodType = None):
        if moddb_lib is None:
            logger.warning(
                'The moddb library is not available, though the installer'
                ' is attempting to install a file hosted on moddb.com. The'
                ' moddb.com URLs will not be transformed, and rather passed as-is.')
        self.moddb_lib = moddb_lib
        self.parse = parse_page_method
        if self.parse is None and self.moddb_lib is not None:
            self.parse = self.moddb_lib.parse_page

    def transform_url(self, moddb_permalink_url):
        # no-op in case the lib did not load
        if self.moddb_lib is None:
            return moddb_permalink_url
        if not is_moddb_url(moddb_permalink_url):
            raise RuntimeError('Provided URL must be from moddb.com')

        return MODDB_FQDN + self._autoselect_moddb_mirror(
            self._get_html_and_resolve_mirrors_list(moddb_permalink_url))._url

    def _autoselect_moddb_mirror(self, mirrors_list):
        # dumb autoselect for now: rank mirrors by capacity (lower is better), pick first (lowest load)
        return sorted(mirrors_list, key=lambda m: m.capacity)[0]

    def _get_html_and_resolve_mirrors_list(self, moddb_permalink_url):
        # make sure the url is not that of a mirrored file
        # if this isn't checked, the helper might hang
        # while downloading a file instead of a web page
        # with no obvious reason to the user as to why
        if self._is_moddb_mirror_url(moddb_permalink_url):
            raise RuntimeError(
                'Provided URL points directly to a moddb.com mirror.'
                ' This is an incorrect configuration, please refer to'
                ' installers.rst for details.')

        moddb_obj = self.parse(moddb_permalink_url)
        if not isinstance(moddb_obj, self.moddb_lib.pages.File):
            raise RuntimeError('Provided URL does not point to the page of a file hosted on moddb.com')

        mirrors_list = moddb_obj.get_mirrors()
        if not any(mirrors_list):
            raise RuntimeError('No available mirror was available for the file hosted on moddb.com')

        return mirrors_list

    def _is_moddb_mirror_url(self, url):
        return re.match(MODDB_MIRROR_URL_MATCHER, url.lower()) is not None
