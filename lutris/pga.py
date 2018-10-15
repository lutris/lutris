# -*- coding: utf-8 -*-
"""Personnal Game Archive module. Handle local database of user's games."""

import os
import time
from itertools import chain

from lutris.util.strings import slugify
from lutris.util.log import logger
from lutris.util import sql
from lutris import settings

PGA_DB = settings.PGA_DB


def get_schema(tablename):
    """
    Fields:
        - position
        - name
        - type
        - not null
        - default
        - indexed
    """
    tables = []
    query = "pragma table_info('%s')" % tablename
    with sql.db_cursor(PGA_DB) as cursor:
        for row in cursor.execute(query).fetchall():
            field = {
                'name': row[1],
                'type': row[2],
                'not_null': row[3],
                'default': row[4],
                'indexed': row[5]
            }
            tables.append(field)
    return tables


def field_to_string(
    name="", type="", not_null=False, default=None, indexed=False
):
    field_query = "%s %s" % (name, type)
    if indexed:
        field_query += " PRIMARY KEY"
    return field_query


def create_table(name, schema):
    fields = ", ".join([field_to_string(**f) for f in schema])
    fields = "(%s)" % fields
    query = "CREATE TABLE IF NOT EXISTS %s %s" % (name, fields)
    logger.debug("[PGAQuery] %s", query)
    with sql.db_cursor(PGA_DB) as cursor:
        cursor.execute(query)


def migrate(table, schema):
    existing_schema = get_schema(table)
    migrated_fields = []
    if existing_schema:
        columns = [col['name'] for col in existing_schema]
        for field in schema:
            if field['name'] not in columns:
                migrated_fields.append(field['name'])
                sql.add_field(PGA_DB, table, field)
    else:
        create_table(table, schema)
    return migrated_fields


def migrate_games():
    schema = [
        {'name': 'id', 'type': 'INTEGER', 'indexed': True},
        {'name': 'name', 'type': 'TEXT'},
        {'name': 'slug', 'type': 'TEXT'},
        {'name': 'installer_slug', 'type': 'TEXT'},
        {'name': 'parent_slug', 'type': 'TEXT'},
        {'name': 'platform', 'type': 'TEXT'},
        {'name': 'runner', 'type': 'TEXT'},
        {'name': 'executable', 'type': 'TEXT'},
        {'name': 'directory', 'type': 'TEXT'},
        {'name': 'updated', 'type': 'DATETIME'},
        {'name': 'lastplayed', 'type': 'INTEGER'},
        {'name': 'installed', 'type': 'INTEGER'},
        {'name': 'installed_at', 'type': 'INTEGER'},
        {'name': 'year', 'type': 'INTEGER'},
        {'name': 'steamid', 'type': 'INTEGER'},
        {'name': 'configpath', 'type': 'TEXT'},
        {'name': 'has_custom_banner', 'type': 'INTEGER'},
        {'name': 'has_custom_icon', 'type': 'INTEGER'},
    ]
    return migrate('games', schema)


def migrate_sources():
    schema = [
        {'name': 'id', 'type': 'INTEGER', 'indexed': True},
        {'name': 'uri', 'type': 'TEXT UNIQUE'},
    ]
    return migrate('sources', schema)


def syncdb():
    """Update the database to the current version, making necessary changes
    for backwards compatibility."""
    migrated = migrate_games()
    if 'configpath' in migrated:
        set_config_paths()
    migrate_sources()


def set_config_paths():
    for game in get_games():
        if game.get('configpath'):
            continue
        game_config_path = os.path.join(settings.CONFIG_DIR,
                                        "games/%s.yml" % game['slug'])
        if os.path.exists(game_config_path):
            logger.debug('Setting configpath to %s', game['slug'])
            sql.db_update(
                PGA_DB,
                'games',
                {'configpath': game['slug']},
                ('id', game['id'])
            )


def get_games(name_filter=None, filter_installed=False, filter_runner=None, select='*', show_installed_first=False):
    """Get the list of every game in database."""
    query = "select " + select + " from games"
    params = []
    filters = []
    if name_filter:
        params.append(name_filter)
        filters.append("name LIKE ?")
    if filter_installed:
        filters.append("installed = 1")
    if filter_runner:
        params.append(filter_runner)
        filters.append("runner = ?")
    if filters:
        query += " WHERE " + " AND ".join([f for f in filters])
    if show_installed_first:
        query += " ORDER BY installed DESC, slug"
    else:
        query += " ORDER BY slug"

    return sql.db_query(PGA_DB, query, tuple(params))


def get_game_ids():
    """Return a list of ids of games in the database."""
    games = get_games()
    return [game['id'] for game in games]


def get_games_where(**conditions):
    """
        Query games table based on conditions

        Args:
            conditions (dict): named arguments with each field matches its desired value.
            Special values for field names can be used:
                <field>__isnull will return rows where `field` is NULL if the value is True
                <field>__not will invert the condition using `!=` instead of `=`
                <field>__in will match rows for every value of `value`, which should be an iterable

        Returns:
            list: Rows matching the query

    """
    query = "select * from games"
    condition_fields = []
    condition_values = []
    for field, value in conditions.items():
        field, *extra_conditions = field.split('__')
        if extra_conditions:
            extra_condition = extra_conditions[0]
            if extra_condition == 'isnull':
                condition_fields.append('{} is {} null'.format(field, '' if value else 'not'))
            if extra_condition == 'not':
                condition_fields.append("{} != ?".format(field))
                condition_values.append(value)
            if extra_condition == 'in':
                if not hasattr(value, '__iter__'):
                    raise ValueError("Value should be an iterable (%s given)" % value)
                if len(value) > 999:
                    raise ValueError("SQLite limnited to a maximum of 999 parameters.")
                if value:
                    condition_fields.append("{} in ({})".format(
                        field, ', '.join('?' * len(value)) or ""
                    ))
                    condition_values = list(chain(condition_values, value))
        else:
            condition_fields.append("{} = ?".format(field))
            condition_values.append(value)
    condition = " AND ".join(condition_fields)
    if condition:
        query = " WHERE ".join((query, condition))
    else:
        # FIXME: Inspect and document why we should return an empty list when
        # no condition is present.
        return []
    return sql.db_query(PGA_DB, query, tuple(condition_values))


def get_game_by_field(value, field='slug'):
    """Query a game based on a database field"""
    if field not in ('slug', 'installer_slug', 'id', 'configpath', 'steamid'):
        raise ValueError("Can't query by field '%s'" % field)
    game_result = sql.db_select(PGA_DB, "games", condition=(field, value))
    if game_result:
        return game_result[0]
    return {}


def add_game(name, **game_data):
    """Add a game to the PGA database."""
    game_data['name'] = name
    game_data['installed_at'] = int(time.time())
    if 'slug' not in game_data:
        game_data['slug'] = slugify(name)
    return sql.db_insert(PGA_DB, "games", game_data)


def add_games_bulk(games):
    """
        Add a list of games to the PGA database.
        The dicts must have an identical set of keys.

        Args:
            games (list): list of games in dict format
        Returns:
            list: List of inserted game ids
    """
    return [sql.db_insert(PGA_DB, "games", game) for game in games]


def add_or_update(**params):
    slug = params.get('slug')
    name = params.get('name')
    id = params.get('id')
    assert any([slug, name, id])
    if 'id' in params:
        game = get_game_by_field(params['id'], 'id')
    else:
        if not slug:
            slug = slugify(name)
        game = get_game_by_field(slug, 'slug')
    if game:
        game_id = game['id']
        sql.db_update(PGA_DB, "games", params, ('id', game_id))
        return game_id
    else:
        return add_game(**params)


def delete_game(id):
    """Delete a game from the PGA."""
    sql.db_delete(PGA_DB, "games", 'id', id)


def set_uninstalled(id):
    sql.db_update(PGA_DB, 'games', {'installed': 0, 'runner': ''}, ('id', id))


def add_source(uri):
    sql.db_insert(PGA_DB, "sources", {"uri": uri})


def delete_source(uri):
    sql.db_delete(PGA_DB, "sources", 'uri', uri)


def read_sources():
    with sql.db_cursor(PGA_DB) as cursor:
        rows = cursor.execute("select uri from sources")
        results = rows.fetchall()
    return [row[0] for row in results]


def write_sources(sources):
    db_sources = read_sources()
    for uri in db_sources:
        if uri not in sources:
            sql.db_delete(PGA_DB, "sources", 'uri', uri)
    for uri in sources:
        if uri not in db_sources:
            sql.db_insert(PGA_DB, "sources", {'uri': uri})


def check_for_file(game, file_id):
    for source in read_sources():
        if source.startswith("file://"):
            source = source[7:]
        else:
            protocol = source[:7]
            logger.warn(
                "PGA source protocol {} not implemented".format(protocol)
            )
            continue
        if not os.path.exists(source):
            logger.info("PGA source {} unavailable".format(source))
            continue
        game_dir = os.path.join(source, game)
        if not os.path.exists(game_dir):
            continue
        game_files = os.listdir(game_dir)
        for game_file in game_files:
            game_base, _ext = os.path.splitext(game_file)
            if game_base == file_id:
                return os.path.join(game_dir, game_file)
    return False


def get_used_runners():
    """Return a list of the runners in use by installed games."""
    with sql.db_cursor(PGA_DB) as cursor:
        query = ("select distinct runner from games "
                 "where runner is not null order by runner")
        rows = cursor.execute(query)
        results = rows.fetchall()
    return [result[0] for result in results if result[0]]


def get_used_platforms():
    """Return a list of platforms currently in use"""
    with sql.db_cursor(PGA_DB) as cursor:
        query = ("select distinct platform from games "
                 "where platform is not null and platform is not '' order by platform")
        rows = cursor.execute(query)
        results = rows.fetchall()
    return [result[0] for result in results if result[0]]
