"""Functions to interact with the Lutris REST API"""

import json
import re
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Collection
from typing import Any, TypeAlias, cast

from lutris import settings
from lutris.util import http
from lutris.util.linux import LINUX_SYSTEM
from lutris.util.log import logger

ApiGameDict: TypeAlias = dict[str, Any]
GamesPageDict: TypeAlias = dict[str, Any]
InstallerInfoDict: TypeAlias = dict[str, str]


def normalize_version_architecture(version_name: str) -> str:
    """Ensures the version name has an architecture on the end ofit;
    adds the system's architecture if it is missing."""
    base_version, arch = parse_version_architecture(version_name)
    return format_version_architecture(base_version, arch) if base_version else ""


def format_version_architecture(base_version: str, arch: str | None = None) -> str:
    """Assembles a version with architecture from the version and architecture."""
    if not base_version:
        return ""

    # A gross hack, since runner versions could be used with non-Wine runners,
    # but it so happens we don't. 'GE-Proton' versions arbitrarily do not have
    # an architecture on them - they are always 64-bit. This also covers the
    # lower-case 'ge-proton' sentinel meaning "whatever GE-Proton Umu provides";
    # suffixing that yields a version that resolves to no Wine at all.
    if base_version.casefold().startswith("ge-proton"):
        return base_version

    if arch:
        return "{}-{}".format(base_version, arch)

    return base_version


def parse_version_architecture(version_name: str) -> tuple[str, str | None]:
    """Splits a version that ends with an architecture into the plain version and
    architecture, as a tuple. If the version has no architecture, this provides
    the system's architecture instead."""
    if version_name:
        if version_name.endswith("-i386") or version_name.endswith("-x86_64"):
            version, arch = version_name.rsplit("-", 1)
            return version, arch
    return version_name, LINUX_SYSTEM.arch


def get_http_post_response(url: str, payload: bytes) -> Any:
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


def get_game_api_page(game_slugs: Collection[str] | None, page: int | str = 1) -> GamesPageDict:
    """Read a single page of games from the API and return the response

    Args:
        game_slugs (list): list of game slugs
        page (str): Page of results to get
    """
    url = settings.SITE_URL + "/api/games"
    if int(page) > 1:
        url += "?page={}".format(page)
    if not game_slugs:
        return {}
    payload = json.dumps({"games": game_slugs, "page": page}).encode("utf-8")
    return cast(GamesPageDict, get_http_post_response(url, payload))


def get_game_service_api_page(service: str, appids: Collection[str] | None, page: int | str = 1) -> GamesPageDict:
    """Get matching Lutris games from a list of appids from a given service"""
    url = settings.SITE_URL + "/api/games/service/%s" % service
    if int(page) > 1:
        url += "?page={}".format(page)
    if not appids:
        return {}
    payload = json.dumps({"appids": appids}).encode("utf-8")
    return cast(GamesPageDict, get_http_post_response(url, payload))


def get_api_games(
    game_slugs: Collection[str] | None = None, page: int = 1, service: str | None = None
) -> list[ApiGameDict]:
    """Return all games from the Lutris API matching the given game slugs"""
    if service:
        response_data = get_game_service_api_page(service, game_slugs)
    else:
        response_data = get_game_api_page(game_slugs)

    if not response_data:
        return []
    results: list[ApiGameDict] = response_data.get("results", [])
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
        results += cast(list[ApiGameDict], response_data.get("results"))
    return results


def get_game_details(slug: str) -> ApiGameDict:
    url = settings.SITE_URL + "/api/games/%s" % slug
    request = http.Request(url)
    try:
        response = request.get()
    except http.HTTPError as ex:
        logger.debug("Unable to load %s: %s", slug, ex)
        return {}
    return cast(ApiGameDict, response.json)


def parse_installer_url(url: str) -> InstallerInfoDict:
    """
    Parses `lutris:` urls, extracting any info necessary to install or run a game.
    """
    action = None
    launch_config_name = None
    try:
        parsed_url = urllib.parse.urlparse(url, scheme="lutris")
    except Exception as ex:
        logger.warning("Unable to parse url %s", url)
        raise ValueError("Invalid lutris url %s" % url) from ex
    if parsed_url.scheme != "lutris":
        raise ValueError("Invalid lutris url %s" % url)
    url_path = parsed_url.path
    if not url_path:
        raise ValueError("Invalid lutris url %s" % url)
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
        "launch_config_name": launch_config_name,
    }


def format_installer_url(installer_info: InstallerInfoDict) -> str:
    """
    Generates 'lutris:' urls, given the same dictionary that
    parse_intaller_url returns.
    """

    game_slug = installer_info.get("game_slug")
    revision = installer_info.get("revision")
    action = installer_info.get("action")
    service: str = installer_info.get("service")
    appid: str = installer_info.get("appid")
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

    parts = [urllib.parse.quote(str(part), safe="") for part in parts]
    path = "/".join(parts)

    if revision:
        query = urllib.parse.urlencode({"revision": str(revision)})
    else:
        query = ""

    url = urllib.parse.urlunparse(("lutris", "", path, "", query, None))
    return url
