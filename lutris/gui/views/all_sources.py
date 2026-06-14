"""Helpers for the virtual 'All Sources' game view.

The view mixes local games with games from every enabled service, so its rows
carry an encoded view-id of the form 'service:<service_id>:<appid>'. These
helpers are the single source of truth for that wire format.
"""

SERVICE_VIEW_ID_PREFIX = "service"


def get_service_view_id(service_id: str, appid: str) -> str:
    """Encode a service game's identity into a view-id for the All Sources view."""
    return "%s:%s:%s" % (SERVICE_VIEW_ID_PREFIX, service_id, appid)


def parse_service_view_id(game_id: str) -> tuple[str | None, str | None]:
    """Decode a view-id produced by get_service_view_id back into (service_id, appid).

    Returns (None, None) if the id is not in the 'service:<service_id>:<appid>'
    format. Note that callers should still validate the service_id against the
    known services before treating the id as a service game.
    """
    parts = str(game_id).split(":", 2)
    if len(parts) == 3 and parts[0] == SERVICE_VIEW_ID_PREFIX:
        return parts[1], parts[2]
    return None, None


def get_unmatched_local_games(local_games: list[dict], service_appids: dict[str, set]) -> list[dict]:
    """Filter out local games that will also appear as a row from their service.

    'service_appids' maps each service id to the appids it provides; a service
    mapped to an empty set (e.g. because loading its games failed) keeps all of
    its local games visible, so a broken service fails soft.
    """
    return [
        game
        for game in local_games
        if game.get("service") not in service_appids or game.get("service_id") not in service_appids[game["service"]]
    ]
