#!/usr/bin/python
# -*- coding:Utf-8 -*-
#
#  Copyright (C) 2012 Mathieu Comandon <strider@strycore.com>
#
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License version 3 as
#  published by the Free Software Foundation.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
"""Personnal Game Archive module. Handle local database of user's games."""

import os

from lutris.util.strings import slugify
from lutris.util.log import logger
from lutris.util import sql
from lutris import settings

PGA_DB = settings.PGA_DB


def create_games(cursor):
    create_game_table_query = """CREATE TABLE IF NOT EXISTS games (
        id INTEGER PRIMARY KEY,
        name TEXT,
        slug TEXT,
        platform TEXT,
        runner TEXT,
        executable TEXT,
        directory TEXT,
        lastplayed INTEGER)"""
    cursor.execute(create_game_table_query)


def create_sources(cursor):
    create_sources_table_query = """CREATE TABLE IF NOT EXISTS sources (
        id INTEGER PRIMARY KEY,
        uri TEXT
    )"""
    cursor.execute(create_sources_table_query)


def create():
    """Create the local PGA database."""
    logger.debug("Running CREATE statement...")
    with sql.db_cursor(PGA_DB) as cursor:
        create_games(cursor)
        create_sources(cursor)


def get_games(name_filter=None):
    """Get the list of every game in database."""
    with sql.db_cursor(PGA_DB) as cursor:
        if name_filter is not None:
            query = "select * from games where name LIKE ?"
            rows = cursor.execute(query, (name_filter, ))
        else:
            query = "select * from games"
            rows = cursor.execute(query)
        results = rows.fetchall()
        column_names = [column[0] for column in cursor.description]
    game_list = []
    for row in results:
        game_info = {}
        for index, column in enumerate(column_names):
            game_info[column] = row[index]
        game_list.append(game_info)
    return game_list


def add_game(name, runner, slug=None):
    """Adds a game to the PGA database."""
    if not slug:
        slug = slugify(name)
    sql.db_insert(PGA_DB, "games",
                  {'name': name, 'slug': slug, 'runner': runner})


def delete_game(name):
    """Deletes a game from the PGA"""
    sql.db_delete(PGA_DB, "games", 'name', name)


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
