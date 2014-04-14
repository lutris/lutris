import os
from lutris.runners.runner import Runner


class o2em(Runner):
    """Magnavox Oyssey² Emulator"""
    package = "o2em"
    executable = "o2em"
    platform = "Odyssey 2"

    bios_choices = [
        ("Odyssey² bios", "o2rom"),
        ("French odyssey² Bios", "c52"),
        ("VP+ Bios", "g7400"),
        ("French VP+ Bios", "jopac")
    ]
    controller_choices = [
        ("Disable", "0"),
        ("Arrows keys and right shift", "1"),
        ("W,S,A,D,SPACE", "2"),
        ("Joystick", "3")
    ]
    game_options = [{
        "option": "rom",
        "type": "file",
        "label": "Rom File"
    }]
    runner_options = [
        {
            "option": "bios",
            "type": "choice",
            "choices": bios_choices,
            "label": "Bios"
        },
        {
            "option": "controller1",
            "type": "choice",
            "choices": controller_choices,
            "label": "First controller"
        },
        {
            "option": "controller2",
            "type": "choice",
            "choices": controller_choices,
            "label": "Second controller"
        },
        {
            "option": "fullscreen",
            "type": "bool",
            "label": "Fullscreen"
        },
        {
            "option": "scanlines",
            "type": "bool",
            "label": "Scanlines"
        }
    ]

    def play(self):
        bios_path = os.path.join(os.path.expanduser("~"), ".o2em/bios/")
        arguments = ["-biosdir=\"%s\"" % bios_path]

        if self.runner_config.get("fullscreen"):
            arguments.append("-fullscreen")

        if self.runner_config.get("scanlines"):
            arguments.append("-scanlines")

        if "first_controller" in self.runner_config:
            arguments.append("-s1=%s" % self.runner_config["controller1"])
        if "second_controller" in self.runner_config:
            arguments.append("-s2=%s" % self.runner_config["controller2"])
        romdir = os.path.dirname(self.settings["game"]["rom"])
        romfile = os.path.basename(self.settings["game"]["rom"])
        self.arguments.append("-romdir=\"%s\"/" % romdir)
        self.arguments.append("\"%s\"" % romfile)
        return {'command': [self.executable] + self.arguments}
