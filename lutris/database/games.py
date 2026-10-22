import math
import time
from collections.abc import Collection, Sequence
from itertools import chain
from typing import Any, TypeAlias, cast

from lutris import settings
from lutris.database import sql
from lutris.util.log import logger
from lutris.util.strings import slugify

# The fields get_game_by_field() may look up; all of them identify a game in practice.
_GAME_LOOKUP_FIELDS = frozenset({"slug", "installer_slug", "id", "configpath", "name"})

# Cached list of installed game identifiers per service, see get_service_games().
_SERVICE_CACHE: dict[str, list[str]] = {}

DbGameDict: TypeAlias = dict[str, Any]


def invalidate_service_cache() -> None:
    """Drop the cached per-service game lists.

    Registered as a data change listener below, so any write made through this process - from
    this module, a service, a scanner or a migration - invalidates the cache right away. This
    replaces a previous one second timeout, which could both serve stale rows immediately
    after an insert and needlessly re-query the database on a later cache hit.
    """
    _SERVICE_CACHE.clear()


sql.add_data_change_listener(invalidate_service_cache)


def _stringify_game_id(game: DbGameDict) -> DbGameDict:
    """Convert the 'id' field from int to str.

    SQLite returns ids as int, but game IDs are str throughout Lutris
    because they share data structures with string-typed service IDs
    in the UI layer.
    """
    if "id" in game:
        game["id"] = str(game["id"])
    return game


def _stringify_game_ids(games: list[DbGameDict]) -> list[DbGameDict]:
    """Apply _stringify_game_id to a list of game rows."""
    return [_stringify_game_id(row) for row in games]


def get_games(
    searches: dict[str, str] | None = None,
    filters: sql.DBConditionsDict | None = None,
    excludes: sql.DBConditionsDict | None = None,
    sorts: Sequence[str] | None = None,
) -> list[DbGameDict]:
    return _stringify_game_ids(
        sql.filtered_query(
            settings.DB_PATH, "games", searches=searches, filters=filters, excludes=excludes, sorts=sorts
        )
    )


def get_games_where(**conditions: Any) -> list[DbGameDict]:
    """
    Query games table based on conditions

    Args:
        conditions (dict): named arguments with each field matches its desired value.
        Special values for field names can be used:
            <field>__lessthan will return rows where `field` is less than the value
            <field>__isnull will return rows where `field` is NULL if the value is True
            <field>__not will invert the condition using `!=` instead of `=`
            <field>__in will match rows for every value of `value`, which should be an iterable

    Returns:
        list: Rows matching the query

    Field names have to be columns of the games table (they are validated, see
    sql.validate_field_name), and the suffix has to be one of those listed above: anything
    else raises a ValueError instead of being ignored.

    Calling this without conditions returns an empty list and never every game in the
    database. That is deliberate - this is a lookup helper, and a condition dict that came
    back empty must not silently turn into a full table scan - so use get_games() when every
    game is wanted.

    An empty iterable given to <field>__in matches nothing, and a None value matches rows
    where the field is NULL. <field>__not keeps the historical `!=` behaviour, which excludes
    rows where the field is NULL; get_games(excludes=...) includes those, if that is wanted.
    """
    if not conditions:
        return []
    filters: dict[str, Any] = {}
    extra_conditions: list[sql.DBQueryCondition] = []
    for key, value in conditions.items():
        field, *key_suffix = key.split("__")
        sql.validate_field_name("games", field)
        suffix = key_suffix[0] if key_suffix else ""
        if not suffix:
            filters[field] = value
        elif suffix == "lessthan":
            extra_conditions.append(sql.create_comparison("games", field, "<", value))
        elif suffix == "isnull":
            extra_conditions.append(sql.create_null_check("games", field, bool(value)))
        elif suffix == "not":
            extra_conditions.append(sql.create_comparison("games", field, "!=", value))
        elif suffix == "in":
            if not hasattr(value, "__iter__") or isinstance(value, str):
                raise ValueError("Value should be an iterable (%s given)" % value)
            if len(value) > 999:
                raise ValueError("SQLite limited to a maximum of 999 parameters.")
            filters[field] = value
        else:
            raise ValueError("Unsupported condition '%s'" % key)
    return _stringify_game_ids(
        sql.filtered_query(settings.DB_PATH, "games", filters=filters, conditions=extra_conditions)
    )


def get_games_by_ids(game_ids: Collection[str]) -> list[DbGameDict]:
    # sqlite limits the number of query parameters to 999, to
    # bypass that limitation, divide the query in chunks
    size = 999
    return list(
        chain.from_iterable(
            [
                get_games_where(id__in=list(game_ids)[page * size : page * size + size])
                for page in range(math.ceil(len(game_ids) / size))
            ]
        )
    )


def get_game_for_service(service: str, appid: str) -> DbGameDict | None:
    if service == "lutris":
        return get_game_by_field(appid, field="slug")

    existing_games = get_games(filters={"service_id": appid, "service": service})
    if existing_games:
        return existing_games[0]

    return None


def get_all_installed_game_for_service(service: str) -> dict[str, DbGameDict]:
    if service == "lutris":
        db_games = get_games(filters={"installed": 1})
        return {g["slug"]: g for g in db_games}

    db_games = get_games(filters={"service": service, "installed": 1})
    return {g["service_id"]: g for g in db_games}


def get_service_games(service: str) -> list[str]:
    """Return the list of all installed games for a service.

    The result is cached until something is written to the database (see
    invalidate_service_cache): this is queried for every search result, and the query is cheap
    but frequent. A copy is returned, so callers cannot modify what is cached.
    """
    if service not in _SERVICE_CACHE:
        if service == "lutris":
            _SERVICE_CACHE[service] = [game["slug"] for game in get_games(filters={"installed": "1"})]
        else:
            _SERVICE_CACHE[service] = [
                game["service_id"] for game in get_games(filters={"service": service, "installed": "1"})
            ]
    return list(_SERVICE_CACHE[service])


def get_game_by_field(value: Any, field: str = "slug") -> DbGameDict | None:
    """Query a game based on a database field, or None if not found.

    A None value returns None without querying: `field = NULL` matches nothing in SQL, so
    looking up NULLs here would turn a missing value into whichever game happens to have a
    NULL in that field.
    """
    if field not in _GAME_LOOKUP_FIELDS:
        raise ValueError("Can't query by field '%s'" % field)
    if value is None:
        return None
    game_result = get_games_where(**{field: value})
    if game_result:
        return game_result[0]
    return None


def get_games_by_runner(runner: str) -> list[DbGameDict]:
    """Return all games using a specific runner"""
    return get_games_where(runner=runner)


def get_games_by_slug(slug: str) -> list[DbGameDict]:
    """Return all games using a specific slug"""
    return get_games_where(slug=slug)


def add_game(**game_data: Any) -> str:
    """Add a game to the database."""
    game_data["installed_at"] = int(time.time())
    if "slug" not in game_data:
        game_data["slug"] = slugify(game_data["name"])
    return str(sql.db_insert(settings.DB_PATH, "games", game_data))


def add_games_bulk(games: list[DbGameDict]) -> list[str]:
    """
    Add a list of games to the database, in a single transaction.
    The dicts must have an identical set of keys.

    Args:
        games (list): list of games in dict format
    Returns:
        list: List of inserted game ids
    """
    return [str(game_id) for game_id in sql.db_insert_many(settings.DB_PATH, "games", games)]


def add_or_update(**params: Any) -> str:
    """Add a game to the database or update an existing one

    If an 'id' is provided in the parameters then it
    will try to match it, otherwise it will try matching
    by slug, creating one when possible.
    """
    game_id = update_existing(**params)
    if game_id:
        return game_id

    return add_game(**params)


def update_existing(**params: Any) -> str | None:
    """Updates a game, but do not add one. If the game exists, this returns its ID;
    if not it returns None and makes no changes."""
    game_id = get_matching_game(params)
    if game_id:
        params["id"] = game_id
        sql.db_update(settings.DB_PATH, "games", params, {"id": game_id})
        return game_id
    return None


def get_matching_game(params: dict[str, Any]) -> str | None:
    """Tries to match given parameters with an existing game"""
    # Always match by ID if provided
    if params.get("id"):
        game = get_game_by_field(params["id"], "id")
        if game:
            game_id: str = game["id"]
            return game_id
        logger.warning("Game ID %s provided but couldn't be matched", params["id"])
    slug = params.get("slug") or slugify(cast(str, params.get("name")))
    if not slug:
        raise ValueError("Can't add or update without an identifier")
    for game in get_games_by_slug(slug):
        game_id = game["id"]
        if game["installed"]:
            if game["configpath"] == params.get("configpath"):
                return game_id
        else:
            if game["runner"] == params.get("runner") or not all([params.get("runner"), game["runner"]]):
                return game_id
    return None


def delete_game(game_id: str) -> None:
    """Delete a game from the PGA."""
    sql.db_delete(settings.DB_PATH, "games", "id", game_id)


def get_used_runners() -> list[str]:
    """Return a list of the runners in use by installed games."""
    with sql.db_read_cursor(settings.DB_PATH) as cursor:
        query = "select distinct runner from games where runner is not null order by runner"
        rows = cursor.execute(query)
        results = rows.fetchall()
    return [result[0] for result in results if result[0]]


def get_used_platforms() -> list[str]:
    """Return a list of platforms currently in use"""
    with sql.db_read_cursor(settings.DB_PATH) as cursor:
        query = (
            "select distinct platform from games where platform is not null and platform is not '' order by platform"
        )
        rows = cursor.execute(query)
        results = rows.fetchall()
    return [result[0] for result in results if result[0]]


def get_game_count(param: str, value: Any) -> int | None:
    res = sql.db_select(settings.DB_PATH, "games", fields=("COUNT(id)",), condition=(param, value))
    if res:
        return cast(int, res[0]["COUNT(id)"])
    return None
