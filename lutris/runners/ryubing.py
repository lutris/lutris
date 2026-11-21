import filecmp
import os
from gettext import gettext as _
from pathlib import Path
from shutil import copyfile

from lutris.exceptions import MissingGameExecutableError
from lutris.runners.runner import Runner
from lutris.util import system
from lutris.util.log import logger
from lutris.util.upstream import ReleaseSource


class ryubing(Runner):
    human_name = _("Ryubing")
    platform_dict = Runner.to_platform_dict([_("Nintendo Switch")])
    description = _("Nintendo Switch emulator")
    runnable_alone = True
    runner_executable = "ryubing/Ryujinx"
    system_executable = "Ryujinx"
    upstream = ReleaseSource("ryubing/ryujinx", r"^ryujinx-[\d.]+-linux_x64\.tar\.gz$", host="git.ryujinx.app")
    upstream_arch = "x86_64"

    game_options = [
        {
            "option": "main_file",
            "type": "file",
            "label": _("NSP file"),
            "help": _("The game data, commonly called a ROM image."),
        },
        {
            "option": "application_id",
            "type": "string",
            "label": _("Application ID"),
            "help": _("Select which app to launch for a multi-game XCI image"),
        },
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
    def ryubing_data_dir(self) -> Path:
        portable = Path(self.get_executable()).resolve().parent / "portable"
        if portable.is_dir():
            return portable
        config_home = os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config"
        return Path(config_home) / "Ryujinx"

    def play(self):
        """Run the game."""
        arguments = self.get_command()
        rom = self.game_config.get("main_file") or ""
        if not system.path_exists(rom):
            raise MissingGameExecutableError(filename=rom)

        if app_id := self.game_config.get("application_id"):
            arguments.append("--application-id")
            arguments.append(app_id)
        arguments.append(rom)
        return {"command": arguments}

    def _update_key(self, key_type: str) -> None:
        key = self.runner_config.get(key_type)
        if not key:
            return
        if not system.path_exists(key):
            logger.warning("Keys file %s does not exist", key)
            return

        key_loc = self.ryubing_data_dir / "system" / key_type.replace("_", ".")
        if key_loc.is_file() and filecmp.cmp(key, key_loc):
            return
        key_loc.parent.mkdir(parents=True, exist_ok=True)
        copyfile(key, key_loc)

    def prelaunch(self) -> None:
        for key in ["prod_keys", "title_keys"]:
            self._update_key(key_type=key)
