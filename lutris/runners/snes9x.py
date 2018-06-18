import os
import subprocess
import xml.etree.ElementTree as etree

from lutris.util.log import logger
from lutris.runners.runner import Runner
from lutris import settings

SNES9X_DIR = os.path.join(settings.DATA_DIR, "runners/snes9x")


class snes9x(Runner):
    description = "Super Nintendo emulator"
    human_name = "Snes9x"
    platforms = ['Nintendo SNES']
    runnable_alone = True
    runner_executable = "snes9x/bin/snes9x-gtk"
    game_options = [
        {
            "option": "main_file",
            "type": "file",
            "default_path": "game_path",
            "label": "ROM file",
            'help': ("The game data, commonly called a ROM image.")
        }
    ]

    runner_options = [
        {
            "option": "fullscreen",
            "type": "bool",
            "label": "Fullscreen",
            "default": "1"
        },
        {
            "option": "maintain_aspect_ratio",
            "type": "bool",
            "label": "Maintain aspect ratio (4:3)",
            "default": "1",
            'help': ("Super Nintendo games were made for 4:3 "
                     "screens with rectangular pixels, but modern screens "
                     "have square pixels, which results in a vertically "
                     "squeezed image. This option corrects this by displaying "
                     "rectangular pixels.")
        },
        {
            "option": "sound_driver",
            "type": "choice",
            "label": "Sound driver",
            'advanced': True,
            "choices": (("SDL", "1"), ("ALSA", "2"), ("OSS", "0")),
            "default": "1"
        }
    ]

    @property
    def config_file(self):
        return system.expanduser("~/.snes9x/snes9x.xml", self.get_env(os_env=True))

    def set_option(self, option, value):
        config_file = self.config_file
        if not os.path.exists(config_file):
            subprocess.Popen([self.get_executable(), '-help'])
        if not os.path.exists(config_file):
            logger.error("Snes9x config file creation failed")
            return
        tree = etree.parse(config_file)
        node = tree.find("./preferences/option[@name='%s']" % option)
        if value.__class__.__name__ == "bool":
            value = "1" if value else "0"
        node.attrib['value'] = value
        tree.write(config_file)

    def play(self):
        for option_name in self.config.runner_config:
            self.set_option(option_name, self.runner_config.get(option_name))

        rom = self.game_config.get('main_file') or ''
        if not os.path.exists(rom):
            return {'error': 'FILE_NOT_FOUND', 'file': rom}
        return {'command': [self.get_executable(), rom]}
