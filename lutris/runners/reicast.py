# Standard Library
import os
import re
import shutil
from collections import Counter
from configparser import RawConfigParser
from gettext import gettext as _

# Lutris Modules
from lutris import settings
from lutris.runners.runner import Runner
from lutris.util import joypad, system


class reicast(Runner):
    human_name = _("Reicast")
    description = _("Sega Dreamcast emulator")
    platforms = [_("Sega Dreamcast")]
    runner_executable = "reicast/reicast.elf"
    entry_point_option = "iso"
    flatpak_id = "org.flycast.Flycast"
    joypads = None

    game_options = [
        {
            "option": "iso",
            "type": "file",
            "label": _("Disc image file"),
            "help": _("The game data.\nSupported formats: ISO, CDI"),
        }
    ]

    def __init__(self, config=None):
        super().__init__(config)

        self.runner_options = [
            {
                "option": "fullscreen",
                "type": "bool",
                "label": _("Fullscreen"),
                "default": False,
            },
            {
                "option": "device_id_1",
                "type": "choice",
                "section": _("Gamepads"),
                "label": _("Gamepad 1"),
                "choices": self.get_joypads,
                "default": "-1",
            },
            {
                "option": "device_id_2",
                "type": "choice",
                "section": _("Gamepads"),
                "label": _("Gamepad 2"),
                "choices": self.get_joypads,
                "default": "-1",
            },
            {
                "option": "device_id_3",
                "type": "choice",
                "section": _("Gamepads"),
                "label": _("Gamepad 3"),
                "choices": self.get_joypads,
                "default": "-1",
            },
            {
                "option": "device_id_4",
                "type": "choice",
                "section": _("Gamepads"),
                "label": _("Gamepad 4"),
                "choices": self.get_joypads,
                "default": "-1",
            },
        ]

    def install(self, install_ui_delegate, version=None, callback=None):
        def on_runner_installed(*args):
            mapping_path = system.create_folder("~/.reicast/mappings")
            mapping_source = os.path.join(settings.RUNNER_DIR, "reicast/mappings")
            for mapping_file in os.listdir(mapping_source):
                shutil.copy(os.path.join(mapping_source, mapping_file), mapping_path)
            system.create_folder("~/.reicast/data")

        super().install(install_ui_delegate, version, on_runner_installed)

    def get_joypads(self):
        """Return list of joypad in a format usable in the options"""
        if self.joypads:
            return self.joypads
        joypad_list = [("No joystick", "-1")]
        joypad_devices = joypad.get_joypads()
        name_counter = Counter([j[1] for j in joypad_devices])
        name_indexes = {}
        for dev, joy_name in joypad_devices:
            dev_id = re.findall(r"(\d+)", dev)[0]
            if name_counter[joy_name] > 1:
                if joy_name not in name_indexes:
                    index = 1
                else:
                    index = name_indexes[joy_name] + 1
                name_indexes[joy_name] = index
            else:
                index = 0
            if index:
                joy_name += " (%d)" % index
            joypad_list.append((joy_name, dev_id))
        self.joypads = joypad_list
        return joypad_list

    @staticmethod
    def write_config(config):
        # use RawConfigParser to preserve case-sensitive configs written by Reicast
        # otherwise, Reicast will write with mixed-case and Lutris will overwrite with all lowercase
        #   which will confuse Reicast
        parser = RawConfigParser()
        parser.optionxform = lambda option: option

        config_path = os.path.expanduser("~/.reicast/emu.cfg")
        if system.path_exists(config_path):
            with open(config_path, "r", encoding="utf-8") as config_file:
                parser.read_file(config_file)

        for section in config:
            if not parser.has_section(section):
                parser.add_section(section)
            for key, value in config[section].items():
                parser.set(section, key, str(value))

        with open(config_path, "w", encoding="utf-8") as config_file:
            parser.write(config_file)

    def play(self):
        fullscreen = "1" if self.runner_config.get("fullscreen") else "0"
        reicast_config = {
            "x11": {"fullscreen": fullscreen},
            "input": {},
            "players": {"nb": "1"},
        }
        players = 1
        reicast_config["input"] = {}
        for index in range(1, 5):
            config_string = "device_id_%d" % index
            joy_id = self.runner_config.get(config_string) or "-1"
            reicast_config["input"]["evdev_{}".format(config_string)] = joy_id
            if index > 1 and joy_id != "-1":
                players += 1
        reicast_config["players"]["nb"] = players

        self.write_config(reicast_config)

        iso = self.game_config.get("iso")
        return {"command": self.get_command() + ["-config", f"config:image={iso}"]}
