import filecmp
import os
from gettext import gettext as _
from shutil import copyfile

from lutris.exceptions import MissingGameExecutableError
from lutris.runners.runner import Runner
from lutris.util import system
from lutris.util.log import logger


class ryujinx(Runner):
    human_name = _("Ryujinx")
    platforms = [_("Nintendo Switch")]
    description = _("Nintendo Switch emulator")
    runnable_alone = True
    runner_executable = "ryujinx/publish/Ryujinx"
    flatpak_id = "io.github.ryubing.Ryujinx"
    download_url = "https://lutris.nyc3.digitaloceanspaces.com/runners/ryujinx/ryujinx-1.0.7074-linux_x64.tar.gz"

    game_options = [
        {
            "option": "main_file",
            "type": "file",
            "label": _("NSP file"),
            "help": _("The game data, commonly called a ROM image."),
        }
    ]
    runner_options = [
        {
            "option": "prod_keys",
            "label": _("Encryption keys"),
            "type": "file",
            "help": _("File containing the encryption keys."),
        },
        {
            "option": "title_keys",
            "label": _("Title keys"),
            "type": "file",
            "help": _("File containing the title keys."),
        },
    ]

    @property
    def ryujinx_data_dir(self):
        """Return dir where Ryujinx files lie."""
        candidates = ("~/.local/share/ryujinx",)
        for candidate in candidates:
            path = system.fix_path_case(os.path.join(os.path.expanduser(candidate), "nand"))
            if system.path_exists(path):
                return path[: -len("nand")]

    def play(self):
        """Run the game."""
        arguments = self.get_command()
        rom = self.game_config.get("main_file") or ""
        if not system.path_exists(rom):
            raise MissingGameExecutableError(filename=rom)
        arguments.append(rom)
        return {"command": arguments}

    def _update_key(self, key_type):
        """Update a keys file if set"""
        ryujinx_data_dir = self.ryujinx_data_dir
        if not ryujinx_data_dir:
            logger.error("Ryujinx data dir not set")
            return
        if key_type == "prod_keys":
            key_loc = os.path.join(ryujinx_data_dir, "keys/prod.keys")
        elif key_type == "title_keys":
            key_loc = os.path.join(ryujinx_data_dir, "keys/title.keys")
        else:
            logger.error("Invalid keys type %s!", key_type)
            return

        key = self.runner_config.get(key_type)
        if not key:
            logger.debug("No %s file was set.", key_type)
            return
        if not system.path_exists(key):
            logger.warning("Keys file %s does not exist!", key)
            return

        keys_dir = os.path.dirname(key_loc)
        if not os.path.exists(keys_dir):
            os.makedirs(keys_dir)
        elif os.path.isfile(key_loc) and filecmp.cmp(key, key_loc):
            # If the files are identical, don't do anything
            return
        copyfile(key, key_loc)

    def prelaunch(self):
        for key in ["prod_keys", "title_keys"]:
            self._update_key(key_type=key)
