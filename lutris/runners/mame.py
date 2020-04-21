"""Runner for MAME"""
import os
import subprocess
from lutris import settings
from lutris.runners.runner import Runner
from lutris.util import system
from lutris.util.log import logger

from lutris.util.mame.database import get_supported_systems


def get_system_choices():
    """Return list of systems for inclusion in dropdown"""
    xml_path = os.path.join(settings.CACHE_DIR, "mame", "mame.xml")
    if not system.path_exists(xml_path):
        logger.info("Getting full game list from MAME...")
        mame_inst = mame()
        mame_inst.write_xml_list()
    for system_id, info in sorted(
            get_supported_systems(xml_path).items(),
            key=lambda sys: (sys[1]["manufacturer"], sys[1]["description"])
    ):
        if info["description"].startswith(info["manufacturer"]):
            yield ("%(description)s (%(year)s)" % info, system_id)
        else:
            yield ("%(manufacturer)s %(description)s (%(year)s)" % info, system_id)


class mame(Runner):
    """MAME runner"""
    human_name = "MAME"
    description = "Arcade game emulator"
    platforms = ["Arcade"]
    runner_executable = "mame/mame"
    runnable_alone = True
    game_options = [
        {
            "option": "main_file",
            "type": "file",
            "label": "ROM file",
            "default_path": "game_path",
        }
    ]

    runner_options = [
        {"option": "fullscreen", "type": "bool", "label": "Fullscreen", "default": True},
        {
            "option": "waitvsync",
            "type": "bool",
            "label": "Wait for VSync",
            "help": (
                "Enable waiting for  the  start  of  VBLANK  before "
                "flipping  screens; reduces tearing effects."
            ),
            "default": False
        },
        {
            "option": "machine",
            "type": "choice_with_search",
            "label": "Machine",
            "choices": get_system_choices,
            "help": "The emulated machine.",
        }
    ]

    @property
    @staticmethod
    def config_dir():
        """Directory where MAME configuration is located"""
        return os.path.expanduser("~/.mame")

    @property
    def cache_dir(self):
        """Directory to store data extracted from MAME"""
        return os.path.join(settings.CACHE_DIR, "mame")

    @property
    def xml_path(self):
        return os.path.join(self.cache_dir, "mame.xml")

    @property
    def working_dir(self):
        return self.config_dir

    def write_xml_list(self):
        """Write the full game list in XML to disk"""
        if not os.path.exists(self.cache_dir):
            os.makedirs(self.cache_dir)
        with open(self.xml_path, "w") as xml_file:
            output = system.execute([self.get_executable(), "-listxml"])
            xml_file.write(output)
            logger.info("MAME XML list written to %s", self.xml_path)

    def prelaunch(self):
        if not system.path_exists(os.path.join(self.config_dir, "mame.ini")):
            try:
                os.makedirs(self.config_dir)
            except OSError:
                pass
            subprocess.Popen(
                [self.get_executable(), "-createconfig"], stdout=subprocess.PIPE
            )
        return True

    def play(self):
        options = []
        rompath = os.path.dirname(self.game_config.get("main_file"))
        rom = os.path.basename(self.game_config.get("main_file"))
        if not self.runner_config.get("fullscreen"):
            options.append("-window")

        if self.runner_config.get("waitvsync"):
            options.append("-waitvsync")

        return {
            "command": [
                self.get_executable(),
                "-inipath",
                self.config_dir,
                "-video",
                "opengl",
                "-skip_gameinfo",
                "-rompath",
                rompath,
                rom,
            ]
            + options
        }
