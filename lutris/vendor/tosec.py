#    tosec.py A Python module to use TOSEC data files as a SQLite database.
#    Copyright (C) 2013 Adrien Plazas
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
#    Adrien Plazas <kekun.plazas@laposte.net>
#    Mathieu Comandon <strider@strycore.com>

import re
import sqlite3
import hashlib
import os.path
import datetime

STANDARD_CODES = {
    "[a]": "Alternate",
    "[p]": "Pirate",
    "[t]": "Trained",
    "[T-]": "OldTranslation",
    "[T+]": "NewerTranslation",
    "(-)": "Unknown Year",
    "[!]": "Verified Good Dump",
    r"(\d+)": "(# of Languages)",
    "(??k)": "ROM Size",
    "(Unl)": "Unlicensed",
    "[b]": "Bad Dump",
    "[f]": "Fixed",
    "[h]": "Hack",
    "[o]": "Overdump",
    "(M#)": "Multilanguage",
    "(###)": "Checksum",
    "ZZZ_": "Unclassified",
}


class TOSEC:
    """A class to ease the use of TOSEC data files as a SQLite database."""

    def __init__(self, directory):
        self.path = os.path.join(directory, "tosec.db")

        # Init the database
        self.db = sqlite3.connect(self.path)
        self.db.execute(
            """CREATE TABLE IF NOT EXISTS systems
                          (
                            id TEXT PRIMARY KEY,
                            version TEXT
                          )"""
        )
        self.db.execute(
            """CREATE TABLE IF NOT EXISTS games
                          (
                            id INTEGER PRIMARY KEY,
                            title TEXT,
                            flags TEXT,
                            system TEXT,
                            UNIQUE (title, flags, system)
                          )"""
        )
        self.db.execute(
            """CREATE TABLE IF NOT EXISTS roms
                          (
                            id INTEGER PRIMARY KEY,
                            flags TEXT,
                            size INTEGER,
                            crc TEXT,
                            md5 TEXT,
                            sha1 TEXT,
                            game INTEGER,
                            FOREIGN KEY(game) REFERENCES game(id)
                          )"""
        )

    def __enter__(self):
        print("enter")
        return self

    def __exit__(self, type, value, traceback):
        print("exit")
        self.db.close()

    def __del__(self):
        self.db.close()

    def parse_file(self, file, system):
        """Add a data file for the given system and update the database if
           this data file's version is newer than the previous one for the
           given system or simply add it if there was no database for this
           system.
        """
        words = tosec_to_words(file)
        info, games = get_games_from_words(words)

        # If the info don't have a version, it is not valid and the file
        # shouldn't be added
        if "version" not in info:
            return False

        new_version = info["version"]

        # Check the version actually in the database
        actual_version = None
        for row in self.db.execute(
            "SELECT version FROM systems WHERE id = ?", [system]
        ):
            actual_version = row[0]

        # If the old version is more recent thab the new one, the new one
        # shouldn't be added
        if actual_version and datefromiso(actual_version) >= datefromiso(new_version):
            return False

        # What if we have to update the version instead of adding it ?
        if actual_version:
            self.db.execute(
                "UPDATE systems SET version = ? WHERE id = ?", [new_version, system]
            )
        else:
            self.db.execute(
                "INSERT INTO systems (id, version) VALUES (?, ?)", [system, new_version]
            )

        for game in games:
            rom = game["rom"]
            title, game_flags, rom_flags = split_game_title(game["name"])

            game_id = None

            # Adding game
            game_info = [title, game_flags, system]
            rows = self.db.execute(
                "SELECT id FROM games " "WHERE title = ? AND flags = ? AND system = ?",
                game_info,
            )
            for row in rows:
                game_id = row[0]
            if not game_id:
                self.db.execute(
                    "INSERT INTO games(id, title, flags, system) "
                    "VALUES (NULL, ?, ?, ?)",
                    game_info,
                )
                new_rows = self.db.execute(
                    "SELECT id FROM games "
                    "WHERE title = ? AND flags = ? AND system = ?",
                    game_info,
                )
                for row in new_rows:
                    game_id = row[0]

            # Adding rom
            rom_info = [rom_flags, rom["size"], rom["crc"], rom["md5"], rom["sha1"]]
            rom_exists = False
            rom_rows = self.db.execute(
                "SELECT id FROM roms "
                "WHERE flags = ? AND size = ? AND crc = ? "
                "AND md5 = ? AND sha1 = ?",
                rom_info,
            )
            for _ in rom_rows:
                rom_exists = True
            if not rom_exists:
                rom_info.append(game_id)
                rom_info = [
                    rom_flags,
                    rom["size"],
                    rom["crc"],
                    rom["md5"],
                    rom["sha1"],
                    game_id,
                ]
                self.db.execute(
                    "INSERT INTO roms(id, flags, size, crc, md5, sha1, game) "
                    "VALUES (NULL, ?, ?, ?, ?, ?, ?)",
                    rom_info,
                )

        self.db.commit()
        return True

    def get_rom_id(self, rom):
        opened_rom = open(rom, "rb")
        data = opened_rom.read()

        md5 = hashlib.md5(data).hexdigest()
        sha1 = hashlib.sha1(data).hexdigest()

        rom_rows = self.db.execute(
            "SELECT id FROM roms WHERE md5 = ? AND sha1 = ?", [md5, sha1]
        )
        for row in rom_rows:
            return row[0]
        return None

    def get_game_title(self, rom):
        rom_id = self.get_rom_id(rom)

        if rom_id:
            title_rows = self.db.execute(
                "SELECT title FROM games, roms "
                "WHERE roms.game = games.id AND roms.id = ?",
                [rom_id],
            )
            for row in title_rows:
                return row[0]
        return os.path.basename(rom)


def tosec_to_words(file):
    input_file = open(file, "r")
    data = input_file.read()
    result = re.split(r"""((?:[^ \n\r\t"]|"[^"]*")+)""", data)
    return result[1::2]


def get_games_from_words(words):
    """Transform a list of words into a tuple containing the clrmamepro object
       and a list of the game objects both as nested dictionnaries having the
       same structure than the original TOSEC file.
    """
    clrmamepro = None
    games = []
    game = {}

    last_path = ""
    path = ""
    tag = None
    for word in words:
        if last_path != "" and path == "":
            if game.get("game"):
                games.append(game["game"])
            elif game.get("clrmamepro"):
                clrmamepro = game["clrmamepro"]
            game = {}
        else:
            last_path = path
        if not tag:
            if word == ")":
                # Go up in the dictionaries tree
                splitted_path = path.split(" ")
                path = ""
                for element in splitted_path[:-1]:
                    if path == "":
                        path = element
                    else:
                        path = path + " " + element
            else:
                tag = word
        else:
            if word == "(":
                # Add a new depth in the dictionaries tree
                dict_game = game
                for element in path.split(" "):
                    if element != "":
                        dict_game = dict_game[element]
                dict_game[tag] = {}
                if path == "":
                    path = tag
                else:
                    path = path + " " + tag
            else:
                dict_game = game
                for element in path.split(" "):
                    dict_game = dict_game[element]
                dict_game[tag] = word
            tag = None

    return clrmamepro, games


def split_game_title(game):
    """Return a tuple containg the game title, the game flags and the ROM
       flags.
    """
    title = ""
    game_flags = ""
    rom_flags = ""
    result = re.match(
        r'''^"([^\(\)\[\]]+) .*?(\(?[^\[\]]*\)?)(\[?[^\(\)]*\]?)"''', game
    )
    if result:
        title = result.group(1)
        game_flags = result.group(2)
        rom_flags = result.group(3)
    return title, game_flags, rom_flags


def datefromiso(isoformat):
    date = isoformat.split("-")
    return datetime.date(int(date[0]), int(date[1]), int(date[2]))
