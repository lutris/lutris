"""Helper functions to assist downloading files from ModDB"""
import moddb
import re

MODDB_FQDN = 'https://www.moddb.com'
MODDB_URL_MATCHER = '^https://(www\.)?moddb\.com'

def is_moddb_url(url):
    return re.match(MODDB_URL_MATCHER, url.lower()) is not None

def get_moddb_download_url(moddb_permalink_url):
    return MODDB_FQDN + __autoselect_moddb_mirror(__get_html_and_resolve_mirrors_list(moddb_permalink_url))._url

def __autoselect_moddb_mirror(mirrors_list):
    # dumb autoselect for now: rank mirrors by capacity (lower is better), pick first (lowest load)
    return sorted(mirrors_list, key=lambda m: m.capacity)[0]

def __get_html_and_resolve_mirrors_list(moddb_permalink_url):
    moddb_obj = moddb.parse_page(moddb_permalink_url)
    if not isinstance(moddb_obj, moddb.File):
        raise RuntimeError("supplied url does not point to the page of a file hosted on moddb.com")

    mirrors_list = moddb_obj.get_mirrors()
    if not any(mirrors_list):
        raise RuntimeError("no available mirror for the file hosted on moddb.com")

    return mirrors_list
