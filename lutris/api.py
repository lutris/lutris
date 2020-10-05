"""Functions to interact with the Lutris REST API"""
import json
import os
import re
import socket
import urllib.error
import urllib.parse
import urllib.request

from lutris import settings
from lutris.util import http, system
from lutris.util.log import logger

API_KEY_FILE_PATH = os.path.join(settings.CACHE_DIR, "auth-token")
USER_INFO_FILE_PATH = os.path.join(settings.CACHE_DIR, "user.json")
USER_ICON_FILE_PATH = os.path.join(settings.CACHE_DIR, "user.png")


def read_api_key():
    """Read the API token from disk"""
    if not system.path_exists(API_KEY_FILE_PATH):
        return None
    with open(API_KEY_FILE_PATH, "r") as token_file:
        api_string = token_file.read()
    try:
        username, token = api_string.split(":")
    except ValueError:
        logger.error("Unable to read Lutris token in %s", API_KEY_FILE_PATH)
        return None
    return {"token": token, "username": username}


def connect(username, password):
    """Connect to the Lutris API"""
    credentials = urllib.parse.urlencode({"username": username, "password": password}).encode("utf-8")
    login_url = settings.SITE_URL + "/api/accounts/token"
    try:
        request = urllib.request.urlopen(login_url, credentials, 10)
    except (socket.timeout, urllib.error.URLError) as ex:
        logger.error("Unable to connect to server (%s): %s", login_url, ex)
        return False
    response = json.loads(request.read().decode())
    if "token" in response:
        token = response["token"]
        with open(API_KEY_FILE_PATH, "w") as token_file:
            token_file.write(":".join((username, token)))
        get_user_info()
        return response["token"]
    return False


def disconnect():
    """Removes the API token, disconnecting the user"""
    for file_path in [API_KEY_FILE_PATH, USER_INFO_FILE_PATH]:
        if system.path_exists(file_path):
            os.remove(file_path)


def get_user_info():
    """Retrieves the user info to cache it locally"""
    credentials = read_api_key()
    if not credentials:
        return
    url = settings.SITE_URL + "/api/users/me"
    request = http.Request(url, headers={"Authorization": "Token " + credentials["token"]})
    response = request.get()
    account_info = response.json
    if not account_info:
        logger.warning("Unable to fetch user info for %s", credentials["username"])
    with open(USER_INFO_FILE_PATH, "w") as token_file:
        json.dump(account_info, token_file, indent=2)


def get_runners(runner_name):
    """Return the available runners for a given runner name"""
    api_url = settings.SITE_URL + "/api/runners/" + runner_name
    response = http.Request(api_url).get()
    return response.json


def get_http_response(url, payload):
    response = http.Request(url, headers={"Content-Type": "application/json"})
    try:
        response.get(data=payload)
    except http.HTTPError as ex:
        logger.error("Unable to get games from API: %s", ex)
        return None
    if response.status_code != 200:
        logger.error("API call failed: %s", response.status_code)
        return None
    return response.json


def get_game_api_page(game_ids, page=1):
    """Read a single page of games from the API and return the response

    Args:
        game_ids (list): list of game IDs, the ID type is determined by `query_type`
        page (str): Page of results to get
        query_type (str): Type of the IDs in game_ids, by default 'games' queries
                          games by their Lutris slug. 'gogid' can also be used.
    """
    url = settings.SITE_URL + "/api/games"
    if int(page) > 1:
        url += "?page={}".format(page)
    if not game_ids:
        return []
    payload = json.dumps({"games": game_ids, "page": page}).encode("utf-8")
    return get_http_response(url, payload)


def get_game_service_api_page(service, appids, page=1):
    """Get matching Lutris games from a list of appids from a given service"""
    url = settings.SITE_URL + "/api/games/service/%s" % service
    if int(page) > 1:
        url += "?page={}".format(page)
    if not appids:
        return []
    payload = json.dumps({"appids": appids}).encode("utf-8")
    return get_http_response(url, payload)


def get_api_games(game_slugs=None, page=1, service=None):
    """Return all games from the Lutris API matching the given game slugs"""
    if service:
        response_data = get_game_service_api_page(service, game_slugs)
    else:
        response_data = get_game_api_page(game_slugs)

    if not response_data:
        return []
    results = response_data.get("results", [])
    while response_data.get("next"):
        page_match = re.search(r"page=(\d+)", response_data["next"])
        if page_match:
            next_page = page_match.group(1)
        else:
            logger.error("No page found in %s", response_data["next"])
            break
        if service:
            response_data = get_game_service_api_page(service, game_slugs, page=next_page)
        else:
            response_data = get_game_api_page(game_slugs, page=next_page)
        if not response_data:
            logger.warning("Unable to get response for page %s", next_page)
            break
        results += response_data.get("results")
    return results


def search_games(query):
    if not query:
        return []
    query = query.lower().strip()[:32]
    url = "/api/games?%s" % urllib.parse.urlencode({"search": query})
    response = http.Request(settings.SITE_URL + url, headers={"Content-Type": "application/json"})
    try:
        response.get()
    except http.HTTPError as ex:
        logger.error("Unable to get games from API: %s", ex)
        return None
    response_data = response.json
    return response_data.get("results", [])


def get_bundle(bundle):
    """Retrieve a lutris bundle from the API"""
    url = "/api/bundles/%s" % bundle
    response = http.Request(settings.SITE_URL + url, headers={"Content-Type": "application/json"})
    try:
        response.get()
    except http.HTTPError as ex:
        logger.error("Unable to get bundle from API: %s", ex)
        return None
    response_data = response.json
    return response_data.get("games", [])


def parse_installer_url(url):
    """
    Parses `lutris:` urls, extracting any info necessary to install or run a game.
    """
    action = None
    try:
        parsed_url = urllib.parse.urlparse(url, scheme="lutris")
    except Exception:  # pylint: disable=broad-except
        logger.warning("Unable to parse url %s", url)
        return False
    if parsed_url.scheme != "lutris":
        return False
    url_path = parsed_url.path
    if not url_path:
        return False
    # urlparse can't parse if the path only contain numbers
    # workaround to remove the scheme manually:
    if url_path.startswith("lutris:"):
        url_path = url_path[7:]

    url_parts = url_path.split("/")
    if len(url_parts) == 2:
        action = url_parts[0]
        game_slug = url_parts[1]
    elif len(url_parts) == 1:
        game_slug = url_parts[0]
    else:
        raise ValueError("Invalid lutris url %s" % url)

    revision = None
    if parsed_url.query:
        query = dict(urllib.parse.parse_qsl(parsed_url.query))
        revision = query.get("revision")
    return {"game_slug": game_slug, "revision": revision, "action": action}
