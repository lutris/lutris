import os
from lutris.settings import RUNTIME_DIR
from lutris.util import system
from lutris.util.log import logger


class ControllerMapping:
    valid_keys = [
        "platform",
        "leftx",
        "lefty",
        "rightx",
        "righty",
        "a",
        "b",
        "back",
        "dpdown",
        "dpleft",
        "dpright",
        "dpup",
        "guide",
        "leftshoulder",
        "leftstick",
        "lefttrigger",
        "rightshoulder",
        "rightstick",
        "righttrigger",
        "start",
        "x",
        "y",
    ]

    def __init__(self, guid, name, mapping):
        self.guid = guid
        self.name = name
        self.mapping = mapping
        self.keys = {}
        self.parse()

    def __str__(self):
        return self.name

    def parse(self):
        key_maps = self.mapping.split(",")
        for key_map in key_maps:
            if not key_map:
                continue
            xinput_key, sdl_key = key_map.split(":")
            if xinput_key not in self.valid_keys:
                logger.warning("Unrecognized key %s", xinput_key)
                continue
            self.keys[xinput_key] = sdl_key


class GameControllerDB:
    db_path = os.path.join(RUNTIME_DIR, "gamecontrollerdb/gamecontrollerdb.txt")

    def __init__(self):
        if not system.path_exists(self.db_path):
            raise OSError("Path to gamecontrollerdb.txt not provided or invalid")
        self.controllers = {}
        self.parsedb()

    def __str__(self):
        return "GameControllerDB <%s>" % self.db_path

    def __getitem__(self, value):
        return self.controllers[value]

    def parsedb(self):
        with open(self.db_path, "r") as db:
            for line in db.readlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                guid, name, mapping = line.strip().split(",", 2)
                self.controllers[guid] = ControllerMapping(guid, name, mapping)
