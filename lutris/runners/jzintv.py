# -*- coding:Utf-8 -*-
import os.path
from lutris.runners.runner import Runner


class jzintv(Runner):
    """Intellivision Emulator"""
    package = "jzintv"
    executable = "jzintv"
    platform = "Intellivision"
    # jzintv is not yet available as a package  in Debian and Ubuntu,
    # it requires some packaging
    is_installable = False
    game_options = [{
        "option": "rom",
        "type": "file",
        "label": "Rom File"
    }]
    runner_options = [
        {
            "option": "bios_path",
            "type": "directory_chooser",
            "label": "Bios Path"
        },
        {
            "option": "fullscreen",
            "type": "bool",
            "label": "Fullscreen"
        }
    ]

    def play(self):
        """Run Intellivision game"""
        arguments = [self.executable]
        if self.runner_config.get("fullscreen"):
            arguments = arguments + ["-f"]
        bios_path = self.runner_config.get("bios_path")
        if os.path.exists(bios_path):
            arguments.append("--execimg=\"%s/exec.bin\"" % bios_path)
            arguments.append("--gromimg=\"%s/grom.bin\"" % bios_path)
        else:
            return {'error': 'NO_BIOS'}
        romdir = os.path.dirname(self.settings["game"]["rom"])
        romfile = os.path.basename(self.settings["game"]["rom"])
        arguments += ["--rom-path=\"%s/\"" % romdir]
        arguments += ["\"%s\"" % romfile]
        return {'command': arguments}
