"""Functions to interact with the Lutris REST API"""
import json
import os
import re
import socket
import urllib.error
import urllib.parse
import urllib.request
from collections import OrderedDict

import requests

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
    with open(API_KEY_FILE_PATH, "r", encoding='utf-8') as token_file:
        api_string = token_file.read()
    try:
        username, token = api_string.split(":")
    except ValueError:
        logger.error("Unable to read Lutris token in %s", API_KEY_FILE_PATH)
        return None
    return {"token": token, "username": username}


def connect(username, password):
    """Connect to the Lutris API"""
    login_url = settings.SITE_URL + "/api/accounts/token"
    credentials = {"username": username, "password": password}
    try:
        response = requests.post(url=login_url, data=credentials, timeout=10)
        response.raise_for_status()
        json_dict = response.json()
        if "token" in json_dict:
            token = json_dict["token"]
            with open(API_KEY_FILE_PATH, "w", encoding='utf-8') as token_file:
                token_file.write("%s:%s" % (username, token))
            get_user_info()
            return token
    except (requests.RequestException, requests.ConnectionError, requests.HTTPError, requests.TooManyRedirects,
            requests.Timeout) as ex:
        logger.error("Unable to connect to server (%s): %s", login_url, ex)
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
    with open(USER_INFO_FILE_PATH, "w", encoding='utf-8') as token_file:
        json.dump(account_info, token_file, indent=2)


def get_runners(runner_name):
    """Return the available runners for a given runner name"""
    api_url = settings.SITE_URL + "/api/runners/" + runner_name
    host = settings.SITE_URL.split("//")[1]

    answers = socket.getaddrinfo(host, 443)
    (_family, _type, _proto, _canonname, _sockaddr) = answers[0]
    headers = OrderedDict({
        'Host': host
    })
    session = requests.Session()
    session.headers = headers
    response = session.get(api_url, headers=headers)
    return response.json()


def get_http_post_response(url, payload):
    response = http.Request(url, headers={"Content-Type": "application/json"})
    try:
        response.post(data=payload)
    except http.HTTPError as ex:
        logger.error("Unable to get games from API: %s", ex)
        return None
    if response.status_code != 200:
        logger.error("API call failed: %s", response.status_code)
        return None
    return response.json


def get_game_api_page(game_slugs, page=1):
    """Read a single page of games from the API and return the response

    Args:
        game_ids (list): list of game slugs
        page (str): Page of results to get
    """
    url = settings.SITE_URL + "/api/games"
    if int(page) > 1:
        url += "?page={}".format(page)
    if not game_slugs:
        return []
    payload = json.dumps({"games": game_slugs, "page": page}).encode("utf-8")
    return get_http_post_response(url, payload)


def get_game_service_api_page(service, appids, page=1):
    """Get matching Lutris games from a list of appids from a given service"""
    url = settings.SITE_URL + "/api/games/service/%s" % service
    if int(page) > 1:
        url += "?page={}".format(page)
    if not appids:
        return []
    payload = json.dumps({"appids": appids}).encode("utf-8")
    return get_http_post_response(url, payload)


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


def get_game_installers(game_slug, revision=None):
    """Get installers for a single game"""
    if not game_slug:
        raise ValueError("No game_slug provided. Can't query an installer")
    if revision:
        installer_url = settings.INSTALLER_REVISION_URL % (game_slug, revision)
    else:
        installer_url = settings.INSTALLER_URL % game_slug

    logger.debug("Fetching installer %s", installer_url)
    request = http.Request(installer_url)
    request.get()
    response = request.json
    if response is None:
        raise RuntimeError("Couldn't get installer at %s" % installer_url)

    # Revision requests return a single installer
    if revision:
        installers = [response]
    else:
        installers = response["results"]
    return [normalize_installer(i) for i in installers]


def get_game_details(slug):
    url = settings.SITE_URL + "/api/games/%s" % slug
    request = http.Request(url)
    try:
        response = request.get()
    except http.HTTPError as ex:
        logger.debug("Unable to load %s: %s", slug, ex)
        return {}
    return response.json


def normalize_installer(installer):
    """Adjusts an installer dict so it is in the correct form, with values
    of the expected types."""
    def must_be_str(key):
        if key in installer:
            installer[key] = str(installer[key])

    must_be_str("name")
    must_be_str("version")
    must_be_str("os")
    must_be_str("slug")
    must_be_str("game_slug")
    must_be_str("dlcid")
    must_be_str("runner")
    return installer


def search_games(query):
    if not query:
        return {}
    query = query.lower().strip()[:255]
    url = "/api/games?%s" % urllib.parse.urlencode({"search": query, "with-installers": True})
    response = http.Request(settings.SITE_URL + url, headers={"Content-Type": "application/json"})
    try:
        response.get()
    except http.HTTPError as ex:
        logger.error("Unable to get games from API: %s", ex)
        return {}
    return response.json


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
    launch_config_name = None
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

    url_parts = [urllib.parse.unquote(part) for part in url_path.split("/")]
    if len(url_parts) == 3:
        action = url_parts[0]
        game_slug = url_parts[1]
        launch_config_name = url_parts[2]
    elif len(url_parts) == 2:
        action = url_parts[0]
        game_slug = url_parts[1]
    elif len(url_parts) == 1:
        game_slug = url_parts[0]
    else:
        raise ValueError("Invalid lutris url %s" % url)

    # To link to service games, format a slug like <service>:<appid>
    if ":" in game_slug:
        service, appid = game_slug.split(":", maxsplit=1)
    else:
        service, appid = "", ""

    revision = None
    if parsed_url.query:
        query = dict(urllib.parse.parse_qsl(parsed_url.query))
        revision = query.get("revision")
    return {
        "game_slug": game_slug,
        "revision": revision,
        "action": action,
        "service": service,
        "appid": appid,
        "launch_config_name": launch_config_name
    }


def format_installer_url(installer_info):
    """
    Generates 'lutris:' urls, given the same dictionary that
    parse_intaller_url returns.
    """

    game_slug = installer_info.get("game_slug")
    revision = installer_info.get("revision")
    action = installer_info.get("action")
    service = installer_info.get("service")
    appid = installer_info.get("appid")
    launch_config_name = installer_info.get("launch_config_name")
    parts = []

    if action:
        parts.append(action)
    elif not launch_config_name:
        raise ValueError("A 'lutris:' URL can contain a launch configuration name only if it has an action.")

    if game_slug:
        parts.append(game_slug)
    else:
        parts.append(service + ":" + appid)

    if launch_config_name:
        parts.append(launch_config_name)

    parts = [urllib.parse.quote(str(part)) for part in parts]
    path = "/".join(parts)

    if revision:
        query = urllib.parse.urlencode({"revision": str(revision)})
    else:
        query = ""

    url = urllib.parse.urlunparse(("lutris", "", path, "", query, None))
    return url
