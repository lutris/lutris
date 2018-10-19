import os
import re
import json
import urllib.request
import urllib.parse
import urllib.error
import socket

from lutris import settings
from lutris.util import http
from lutris.util.log import logger


API_KEY_FILE_PATH = os.path.join(settings.CACHE_DIR, 'auth-token')


def read_api_key():
    if not os.path.exists(API_KEY_FILE_PATH):
        return None
    with open(API_KEY_FILE_PATH, 'r') as token_file:
        api_string = token_file.read()
    username, token = api_string.split(":")
    return {
        'token': token,
        'username': username
    }


def connect(username, password):
    credentials = urllib.parse.urlencode({'username': username,
                                          'password': password}).encode('utf-8')
    login_url = settings.SITE_URL + "/api/accounts/token"
    try:
        request = urllib.request.urlopen(login_url, credentials, 10)
    except (socket.timeout, urllib.error.URLError) as ex:
        logger.error("Unable to connect to server (%s): %s", login_url, ex)
        return False
    response = json.loads(request.read().decode())
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
        return []
    username = credentials["username"]
    token = credentials["token"]
    url = settings.SITE_URL + "/api/games/library/%s" % username
    headers = {'Authorization': 'Token ' + token}
    request = http.Request(url, headers=headers)
    response = request.get()
    response_data = response.json
    if response_data:
        return response_data['games']
    return []


def get_runners(runner_name):
    api_url = settings.SITE_URL + "/api/runners/" + runner_name
    response = http.Request(api_url).get()
    return response.json


def get_games(game_slugs=None, page='1'):
    url = settings.SITE_URL + "/api/games"

    if int(page) > 1:
        url += "?page={}".format(page)

    response = http.Request(url, headers={'Content-Type': 'application/json'})
    if game_slugs:
        payload = json.dumps({'games': game_slugs, 'page': page}).encode('utf-8')
    else:
        payload = None
    response.get(data=payload)
    response_data = response.json

    if not response_data:
        logger.warning('Unable to get games from API')
        return None

    results = response_data.get('results', [])
    while response_data.get('next'):
        page_match = re.search(r'page=(\d+)', response_data['next'])
        if page_match:
            page = page_match.group(1)
        else:
            logger.error("No page found in %s", response_data['next'])
            break
        page_result = get_games(game_slugs=game_slugs, page=page)
        if not page_result:
            logger.warning("Unable to get response for page %s", page)
            break
        else:
            results += page_result

    return results
