import os
import json
import urllib
import urllib2
import socket

from lutris import settings
from lutris.util import http
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
    response = http.download_json(url, params)
    return response['games'] if response else []


# TODO: use it when switched API to DRF
def get_games(slugs):
    """Return remote games from a list of slugs.

    :rtype: list of dicts"""
    logger.debug("Fetching game set")
    game_set = ';'.join(slugs)
    url = settings.SITE_URL + "api/game/%s/" % game_set
    return http.download_json(url, params="?format=json")['objects']


def get_runners(runner_name):
    api_url = "https://lutris.net/api/runners/" + runner_name
    response = http.Request(api_url).get()
    return response.json
