"""Reads the Dolphin game database, stored in a binary format"""
import os

DOLPHIN_GAME_CACHE_FILE = os.path.expanduser("~/.cache/dolphin-emu/gamelist.cache")


def get_hex_string(string):
    """Return the hexadecimal representation of a string"""
    return " ".join("{:02x}".format(c) for c in string)


def get_word_len(string):
    """Return the length of a string as specified in the Dolphin format"""
    return int("0x" + "".join("{:02x}".format(c) for c in string[::-1]), 0)


class DolphinCacheReader:
    header_size = 20
    structure = {
        'is_valid': 'b',
        'path': 's',
        'filename': 's',
        'field_a': 8,
        'field_b': 8,
        'name_short': 'a',
        'name_long': 'a',
        'maker_short': 'a',
        'maker_long': 'a',
        'description': 'a',
        'some_other_name': 's',
        'code_1': 's',
        'code_2': 's',
        'field_c': 32,
        'field_d': 1,
        'rel_date': 's',
        'field_e': 8,
        'banner': 'i',
        'field_f': 28,
    }

    def __init__(self):
        self.offset = 0
        with open(DOLPHIN_GAME_CACHE_FILE, "rb") as dolphin_cache_file:
            self.cache_content = dolphin_cache_file.read()

    def get_games(self):
        self.offset += self.header_size
        games = []
        while self.offset < len(self.cache_content):
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
                else:
                    game[key] = self.get_raw(i)
            games.append(game)
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
        has_image = get_word_len(self.cache_content[self.offset:self.offset + 8])
        self.offset += 8
        image = ''
        if has_image:
            image = self.cache_content[self.offset:self.offset + 12288]
            self.offset += 12288
        return image

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
