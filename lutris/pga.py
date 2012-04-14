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

import sqlite3

from lutris.util.strings import slugify
from lutris.settings import PGA_PATH


def connect():
    """Connect to the local PGA database."""
    return sqlite3.connect(PGA_PATH)


def create():
    """Create the local PGA database."""
    con = connect()
    query = 'create table games ' + \
            '(name text, slug text, machine text, runner text)'
    con.execute(query)
    con.commit()
    con.close()


def get_games(name_filter=None):
    """Get the list of every game in database."""
    con = connect()
    cur = con.cursor()

    if filter is not None:
        query = "select * from where name LIKE = ?"
        rows = cur.execute(query, (name_filter, ))
    else:
        query = "select * from games"
        rows = cur.execute(query)
    results = rows.fetchall()
    cur.close()
    con.close()
    return results


def add_game(name, machine, runner):
    """Adds a game to the PGA database."""
    slug = slugify(name)
    con = connect()
    con.execute("""insert into games(name, slug, machine, runner) values
    (?, ?, ?, ?)""", (name, slug, machine, runner))
    con.commit()
    con.close()
