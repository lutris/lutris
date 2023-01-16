"""Helper functions to assist downloading files from ModDB"""
import moddb
import re
import types

MODDB_FQDN = 'https://www.moddb.com'
MODDB_URL_MATCHER = '^https://(www\.)?moddb\.com'

def is_moddb_url(url):
    return re.match(MODDB_URL_MATCHER, url.lower()) is not None


class ModDB:
    def __init__(self, parse_page_method: types.MethodType = moddb.parse_page):
        self.parse = parse_page_method

    def transform_url(self, moddb_permalink_url):
        if not is_moddb_url(moddb_permalink_url):
            raise RuntimeError("provided url must be from moddb.com")

        return MODDB_FQDN + self._autoselect_moddb_mirror(self._get_html_and_resolve_mirrors_list(moddb_permalink_url))._url

    def _autoselect_moddb_mirror(self, mirrors_list):
        # dumb autoselect for now: rank mirrors by capacity (lower is better), pick first (lowest load)
        return sorted(mirrors_list, key=lambda m: m.capacity)[0]

    def _get_html_and_resolve_mirrors_list(self, moddb_permalink_url):
        moddb_obj = self.parse(moddb_permalink_url)
        if not isinstance(moddb_obj, moddb.pages.File):
            raise RuntimeError("supplied url does not point to the page of a file hosted on moddb.com")

        mirrors_list = moddb_obj.get_mirrors()
        if not any(mirrors_list):
            raise RuntimeError("no available mirror for the file hosted on moddb.com")

        return mirrors_list

