import os
import json
import urllib
import urllib2
import socket

from lutris import settings
from lutris import pga
from lutris.util import http
from lutris.util import resources
from lutris.util.log import logger


API_KEY_FILE_PATH = os.path.join(settings.CACHE_DIR, 'auth-token')


def read_api_key():
    if not os.path.exists(API_KEY_FILE_PATH):
        return
    with open(API_KEY_FILE_PATH, 'r') as token_file:
        api_string = token_file.read()
    username, token = api_string.split(":")
    return {
        'token': token,
        'username': username
    }


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


def disconnect():
    if not os.path.exists(API_KEY_FILE_PATH):
        return
    os.remove(API_KEY_FILE_PATH)


def get_library():
    """Return the remote library as a list of dicts."""
    logger.debug("Fetching game library")
    credentials = read_api_key()
    if not credentials:
        return {}
    username = credentials["username"]
    api_key = credentials["token"]
    url = settings.SITE_URL + "api/v1/library/%s/" % username
    params = urllib.urlencode({'api_key': api_key, 'username': username,
                               'format': 'json'})
    return http.download_json(url, params)['games']

def get_games(slugs):
    """Return remote games from a list of slugs.

    :rtype: list of dicts"""
    logger.debug("Fetching game set")
    game_set = ';'.join(slugs)
    url = settings.SITE_URL + "api/v1/game/set/%s/" % game_set
    return http.download_json(url, params="?format=json")['objects']


def sync(caller=None):
    """Synchronize from remote to local library.

    :param caller: The LutrisWindow object
    :return: The synchronized games (slugs)
    :rtype: set of strings
    """
    logger.debug("Syncing game library")
    # Get local library
    local_library = pga.get_games()
    local_slugs = set([game['slug'] for game in local_library])
    logger.debug("%d games in local library", len(local_slugs))
    # Get remote library
    remote_library = get_library()
    remote_slugs = set([game['slug'] for game in remote_library])
    logger.debug("%d games in remote library (inc. unpublished)",
                 len(remote_slugs))

    not_in_local = remote_slugs.difference(local_slugs)
    added = sync_missing_games(not_in_local, remote_library, caller)
    updated = sync_game_details(local_slugs, caller)
    return added.update(updated)


def sync_missing_games(not_in_local, remote_library, caller=None):
    """Get missing games in local library from remote library.

    :param caller: The LutrisWindow object
    :return: The slugs of the added games
    :rtype: set
    """
    if not not_in_local:
        return set()

    for game in remote_library:
        slug = game['slug']
        # Sync
        if slug in not_in_local:
            logger.debug("Adding to local library: %s", slug)
            pga.add_game(
                game['name'], slug=slug, year=game['year'],
                updated=game['updated'], steamid=['steamid']
            )
            if caller:
                caller.add_game_to_view(slug)
        else:
            not_in_local.discard(slug)
    logger.debug("%d games added", len(not_in_local))
    return not_in_local


def sync_game_details(local_slugs, caller=None):
    """Get missing local game details,

    :param caller: The LutrisWindow object
    :return: The slugs of the updated games.
    :rtype: set
    """
    if not local_slugs:
        return set()

    updated = set()

    # Get remote games
    remote_games = get_games(sorted(local_slugs))
    if not remote_games:
        return set()

    for game in remote_games:
        slug = game['slug']
        local_game = pga.get_game_by_slug(slug)

        # Sync
        if game['updated'] > local_game['updated']:
            logger.debug("Syncing details for %s" % slug)
            pga.add_or_update(
                local_game['name'], local_game['runner'], slug,
                year=game['year'], updated=game['updated']
            )
            caller.view.update_row(game)

            # Sync icons (TODO: Only update if icon actually updated)
            resources.download_icon(slug, 'banner', overwrite=True,
                                    callback=caller.on_image_downloaded)
            resources.download_icon(slug, 'icon', overwrite=True,
                                    callback=caller.on_image_downloaded)
            updated.add(slug)

    logger.debug("%d games updated", len(updated))
    return updated
