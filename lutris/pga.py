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
import sqlite3

from lutris.util.strings import slugify
from lutris.util.log import logger
from lutris import settings

PGA_DB = settings.PGA_DB


class db_cursor():
    def __enter__(self):
        self.db_conn = sqlite3.connect(PGA_DB)
        cursor = self.db_conn.cursor()
        return cursor

    def __exit__(self, type, value, traceback):
        self.db_conn.commit()
        self.db_conn.close()


def create_games(cursor):
    create_game_table_query = """CREATE TABLE games (
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
    create_sources_table_query = """CREATE TABLE sources (
        id INTEGER PRIMARY KEY,
        uri TEXT
    )"""
    cursor.execute(create_sources_table_query)


def create():
    """Create the local PGA database."""
    logger.debug("Running CREATE statement...")
    with db_cursor() as cursor:
        create_games(cursor)
        create_sources(cursor)


def db_insert(table, fields):
    field_names = ", ".join(fields.keys())
    placeholders = ("?, " * len(fields))[:-2]
    field_values = tuple(fields.values())
    with db_cursor() as cursor:
        cursor.execute(
            "insert into {0}({1}) values ({2})".format(table,
                                                       field_names,
                                                       placeholders),
            field_values
        )


def db_delete(table, field, value):
    with db_cursor() as cursor:
        cursor.execute("delete from {0} where {1}=?".format(table, field),
                       (value,))


def get_games(name_filter=None):
    """Get the list of every game in database."""
    with db_cursor() as cursor:
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
    db_insert("games", {'name': name, 'slug': slug, 'runner': runner})


def delete_game(name):
    """Deletes a game from the PGA"""
    db_delete("games", 'name', name)


def add_source(uri):
    db_insert("sources", {"uri": uri})


def delete_source(uri):
    db_delete("sources", 'uri', uri)


def read_sources():
    with db_cursor() as cursor:
        rows = cursor.execute("select uri from sources")
        results = rows.fetchall()
    return [row[0] for row in results]


def write_sources(sources):
    db_sources = read_sources()
    for uri in db_sources:
        if uri not in sources:
            db_delete("sources", 'uri', uri)
    for uri in sources:
        if uri not in db_sources:
            db_insert("sources", {'uri': uri})


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
            print "dir", game_dir
            continue
        game_files = os.listdir(game_dir)
        for game_file in game_files:
            print "file", game_file
            game_base, _ext = os.path.splitext(game_file)
            if game_base == file_id:
                return os.path.join(game_dir, game_file)
    return False
