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


import sqlite3
import re

from lutris.settings import PGA_PATH


def slugify(value):
    """
    Normalizes string, converts to lowercase, removes non-alpha characters,
    and converts spaces to hyphens.
    """
    import unicodedata
    value = unicodedata.normalize('NFKD', value).encode('ascii', 'ignore')
    value = unicode(re.sub('[^\w\s-]', '', value).strip().lower())
    return re.sub('[-\s]+', '-', value)


def connect():
    return sqlite3.connect(PGA_PATH)


def create():
    c = connect()
    q = 'create table games (name text, slug text, machine text, runner text)'
    c.execute(q)
    c.commit()
    c.close()


def get_games(name_filter=None):
    c = connect()
    cur = c.cursor()

    if filter is not None:
        q = "select * from where name LIKE = ?"
        rows = cur.execute(q, (name_filter, ))
    else:
        q = "select * from games"
        rows = cur.execute(q)
    results = rows.fetchall()
    cur.close()
    c.close()
    return results


def add_game(name, machine, runner):
    slug = slugify(name)
    c = connect()
    c.execute("""insert into games(name, slug, machine, runner) values
    (?, ?, ?, ?)""", (name, slug, machine, runner))
    c.commit()
    c.close()
