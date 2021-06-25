"""Reads the Dolphin game database, stored in a binary format"""
import os
import sys
from PIL import Image

from lutris.util.log import logger

DOLPHIN_GAME_CACHE_FILE = os.path.expanduser("~/.cache/dolphin-emu/gamelist.cache")
CACHE_REVISION = 20



def get_hex_string(string):
    """Return the hexadecimal representation of a string"""
    return " ".join("{:02x}".format(c) for c in string)


def get_word_len(string):
    """Return the length of a string as specified in the Dolphin format"""
    return int("0x" + "".join("{:02x}".format(c) for c in string[::-1]), 0)

# https://github.com/dolphin-emu/dolphin/blob/90a994f93780ef8a7cccfc02e00576692e0f2839/Source/Core/UICommon/GameFile.h#L140
# https://github.com/dolphin-emu/dolphin/blob/90a994f93780ef8a7cccfc02e00576692e0f2839/Source/Core/UICommon/GameFile.cpp#L318

class DolphinCacheReader:
    header_size = 20
    structure = {
        'valid': 'b',
        'file_path': 's',
        'file_name': 's',
        'file_size': 8,
        'volume_size': 8,
        'volume_size_is_accurate': 1,
        'is_datel_disc': 1,
        'is_nkit': 1,
        'short_names': 'a',
        'long_names': 'a',
        'short_makers': 'a',
        'long_makers': 'a',
        'descriptions': 'a',
        'internal_name': 's',
        'game_id': 's',
        'gametdb_id': 's',
        'title_id': 8,
        'maker_id': 's',
        'region': 4,
        'country': 4,
        'platform': 1,
        'platform_': 3,
        'blob_type': 4,
        'block_size': 8,
        'compression_method': 's',
        'revision': 2,
        'disc_number': 1,
        'apploader_date': 's',
        'custom_name': 's',
        'custom_description': 's',
        'custom_maker': 's',
        'volume_banner': 'i',
        'custom_banner': 'i',
        'default_cover': 'c',
        'custom_cover': 'c',
    }

    def __init__(self):
        self.offset = 0
        with open(DOLPHIN_GAME_CACHE_FILE, "rb") as dolphin_cache_file:
            self.cache_content = dolphin_cache_file.read()
        if get_word_len(self.cache_content[:4]) != CACHE_REVISION:
            raise Exception('Incompatible Dolphin version')

    def get_game(self):
        game = {}
        for key, i in self.structure.items():
            if i == 's':
                game[key] = self.get_string()
            elif i == 'b':
                game[key] = self.get_boolean()
            elif i == 'a':
                game[key] = self.get_array()
            elif i == 'i':
                game[key] = self.get_image()
            elif i == 'c':
                game[key] = self.get_cover()
            else:
                game[key] = self.get_raw(i)
        return game

    def get_games(self):
        self.offset += self.header_size
        games = []
        while self.offset < len(self.cache_content):
            try:
                games.append(self.get_game())
            except Exception as ex:
                logger.error("Failed to read Dolphin database: %s", ex)
        return games

    def get_boolean(self):
        res = bool(get_word_len(self.cache_content[self.offset:self.offset + 1]))
        self.offset += 1
        return res

    def get_array(self):
        array_len = get_word_len(self.cache_content[self.offset:self.offset + 4])
        self.offset += 4
        array = {}
        for _i in range(array_len):
            array_key = self.get_raw(4)
            array[array_key] = self.get_string()
        return array

    def get_image(self):
        data_len = get_word_len(self.cache_content[self.offset:self.offset + 4])
        self.offset += 4
        res = self.cache_content[self.offset:self.offset + data_len * 4] # vector<u32>
        self.offset += data_len * 4
        width = get_word_len(self.cache_content[self.offset:self.offset + 4])
        self.offset += 4
        height = get_word_len(self.cache_content[self.offset:self.offset + 4])
        self.offset += 4
        return (width, height), res

    def get_cover(self):
        array_len = get_word_len(self.cache_content[self.offset:self.offset + 4])
        self.offset += 4
        return self.get_raw(array_len)

    def get_raw(self, word_len):
        res = get_hex_string(self.cache_content[self.offset:self.offset + word_len])
        self.offset += word_len
        return res

    def get_string(self):
        word_len = get_word_len(self.cache_content[self.offset:self.offset + 4])
        self.offset += 4
        string = self.cache_content[self.offset:self.offset + word_len]
        self.offset += word_len
        return string.decode('utf8')
