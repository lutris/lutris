import os
import json
import urllib
import urllib2
import socket

from lutris.util.log import logger
from lutris import settings
from lutris import pga


API_KEY_FILE_PATH = os.path.join(settings.CACHE_DIR, 'auth-token')


def read_api_key():
    if not os.path.exists(API_KEY_FILE_PATH):
        return
    with open(API_KEY_FILE_PATH, 'r') as token_file:
        api_string = token_file.read()
    username, api_key = api_string.split(":")
    return username, api_key


def connect(username, password):
    credentials = urllib.urlencode({'username': username,
                                    'password': password})
    login_url = settings.SITE_URL + "user/auth/"
    try:
        request = urllib2.urlopen(login_url, credentials, 10)
    except (socket.timeout, urllib2.URLError) as ex:
        logger.error("Unable to connect to server (%s): %s", login_url, ex)
        return False
    response = json.loads(request.read())
    if 'token' in response:
        token = response['token']
        with open(API_KEY_FILE_PATH, "w") as token_file:
            token_file.write(":".join((username, token)))
        return response['token']
    return False


def get_library():
    logger.debug("Fetching game library")
    username, api_key = read_api_key()
    library_url = settings.SITE_URL + "api/v1/library/%s/" % username
    params = urllib.urlencode({'api_key': api_key, 'username': username,
                               'format': 'json'})
    request = urllib2.urlopen(library_url + "?" + params)
    return json.loads(request.read())


def sync():
    logger.debug("Syncing game library")
    remote_library = get_library()['games']
    remote_slugs = set([game['slug'] for game in remote_library])
    logger.debug("%d games in remote library", len(remote_slugs))
    local_libray = pga.get_games()
    local_slugs = set([game['slug'] for game in local_libray])
    logger.debug("%d games in local library", len(local_slugs))
    not_in_local = remote_slugs.difference(local_slugs)
    for game in remote_library:
        if game['slug'] in not_in_local:
            logger.debug("Adding %s to local library", game['slug'])
            pga.add_game(game['name'], slug=game['slug'])
    return not_in_local
