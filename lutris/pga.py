# -*- coding: utf-8 -*-
"""Personnal Game Archive module. Handle local database of user's games."""

import os
import logging

from lutris.util.strings import slugify
from lutris.util.log import logger
from lutris.util import sql
from lutris import settings

PGA_DB = settings.PGA_DB
LOGGER = logging.getLogger(__name__)


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


def add_field(tablename, field):
    query = "ALTER TABLE %s ADD COLUMN %s %s" % (
        tablename, field['name'], field['type']
    )
    with sql.db_cursor(PGA_DB) as cursor:
        cursor.execute(query)


def create_table(name, schema):
    fields = ", ".join([field_to_string(**f) for f in schema])
    fields = "(%s)" % fields
    query = "CREATE TABLE IF NOT EXISTS %s %s" % (name, fields)
    LOGGER.debug("[PGAQuery] %s", query)
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
                add_field(table, field)
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
        {'name': 'year', 'type': 'INTEGER'},
        {'name': 'steamid', 'type': 'INTEGER'},
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
    if 'installed' in migrated:
        set_installed_games()
    migrate_sources()

    # Rename runners
    sql.db_update(PGA_DB, 'games', {'runner': 'mame'}, ('runner', 'sdlmame'))
    sql.db_update(PGA_DB, 'games', {'runner': 'mess'}, ('runner', 'sdlmess'))


def set_installed_games():
    games = get_games()
    for game in games:
        if game['directory'] and os.path.exists(game['directory']):
            sql.db_update(PGA_DB, 'games',
                          {'installed': 1}, ('slug', game['slug']))


def get_table_length(table='games'):
    with sql.db_cursor(PGA_DB) as cursor:
        query = "select count() from games"
        cursor.execute(query)
        return cursor.fetchone()[0]


def get_games(name_filter=None, filter_installed=False):
    """Get the list of every game in database."""
    with sql.db_cursor(PGA_DB) as cursor:
        query = "select * from games"
        params = ()
        filters = []
        if name_filter:
            params = (name_filter, )
            filters.append("name LIKE ?")
        if filter_installed:
            filters.append("installed = 1")
        if filters:
            query += " WHERE " + " AND ".join([f for f in filters])
        query += " ORDER BY slug"
        rows = cursor.execute(query, params)
        results = rows.fetchall()
        column_names = [column[0] for column in cursor.description]
    game_list = []
    for row in results:
        game_info = {}
        for index, column in enumerate(column_names):
            game_info[column] = row[index]
        game_list.append(game_info)
    return game_list


def get_game_by_slug(slug, field='slug'):
    if field not in ('slug', 'installer_slug'):
        raise ValueError("Invalid field name: %s", field)
    game_result = sql.db_select(PGA_DB, "games", condition=(field, slug))
    if game_result:
        return game_result[0]
    return {}


def add_game(name, **game_data):
    """Add a game to the PGA database."""
    game_data['name'] = name
    if 'slug' not in game_data:
        game_data['slug'] = slugify(name)
    sql.db_insert(PGA_DB, "games", game_data)


def add_games_bulk(games):
    """Add a list of games to the PGA database.

    The dicts must have an identical set of keys.

    :type games: list of dicts
    """
    sql.db_insert_bulk(PGA_DB, "games", games)


def add_or_update(name, runner, slug=None, **kwargs):
    if not slug:
        slug = slugify(name)
    game = get_game_by_slug(slug)
    kwargs['name'] = name
    kwargs['runner'] = runner
    kwargs['slug'] = slug
    if game:
        game_id = game['id']
        sql.db_update(PGA_DB, "games", kwargs, ('id', game_id))
    else:
        add_game(**kwargs)


def delete_game(slug):
    """Delete a game from the PGA."""
    sql.db_delete(PGA_DB, "games", 'slug', slug)


def set_uninstalled(slug):
    sql.db_update(PGA_DB, 'games', {'installed': 0, 'runner': ''},
                  ('slug', slug))


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
