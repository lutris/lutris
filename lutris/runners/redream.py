import os
import shutil
from gettext import gettext as _

from lutris import settings
from lutris.runners.runner import Runner


class redream(Runner):
    human_name = _("Redream")
    description = _("Sega Dreamcast emulator")
    platforms = [_("Sega Dreamcast")]
    runner_executable = "redream/redream"
    download_url = "https://redream.io/download/redream.x86_64-linux-v1.5.0.tar.gz"
    game_options = [
        {
            "option": "main_file",
            "type": "file",
            "label": _("Disc image file"),
            "help": _("Game data file\nSupported formats: GDI, CDI, CHD"),
        }
    ]
    runner_options = [
        {
            "option": "fs",
            "type": "bool",
            "section": _("Graphics"),
            "label": _("Fullscreen"),
            "default": False},
        {
            "option": "ar",
            "type": "choice",
            "section": _("Graphics"),
            "label": _("Aspect Ratio"),
            "choices": [(_("4:3"), "4:3"), (_("Stretch"), "stretch")],
            "default": "4:3",
        },
        {
            "option": "region",
            "type": "choice",
            "label": _("Region"),
            "choices": [(_("USA"), "usa"), (_("Europe"), "europe"), (_("Japan"), "japan")],
            "default": "usa",
        },
        {
            "option": "language",
            "type": "choice",
            "label": _("System Language"),
            "choices": [
                (_("English"), "english"),
                (_("German"), "german"),
                (_("French"), "french"),
                (_("Spanish"), "spanish"),
                (_("Italian"), "italian"),
                (_("Japanese"), "japanese"),
            ],
            "default": "english",
        },
        {
            "option": "broadcast",
            "type": "choice",
            "label": "Television System",
            "choices": [
                (_("NTSC"), "ntsc"),
                (_("PAL"), "pal"),
                (_("PAL-M (Brazil)"), "pal_m"),
                (_("PAL-N (Argentina, Paraguay, Uruguay)"), "pal_n"),
            ],
            "default": "ntsc",
        },
        {
            "option": "time_sync",
            "type": "choice",
            "label": _("Time Sync"),
            "choices": [
                (_("Audio and video"), "audio and video"),
                (_("Audio"), "audio"),
                (_("Video"), "video"),
                (_("None"), "none"),
            ],
            "default": "audio and video",
            "advanced": True,
        },
        {
            "option": "int_res",
            "type": "choice",
            "label": _("Internal Video Resolution Scale"),
            "choices": [
                ("×1", "1"),
                ("×2", "2"),
                ("×3", "3"),
                ("×4", "4"),
                ("×5", "5"),
                ("×6", "6"),
                ("×7", "7"),
                ("×8", "8"),
            ],
            "default": "2",
            "advanced": True,
            "help": _("Only available in premium version."),
        },
    ]

    async def install(self, install_ui_delegate, version=None):
        if not await super().install(install_ui_delegate, version=version):
            return False

        license_filename = await install_ui_delegate.show_install_file_inquiry(
            question=_("Do you want to select a premium license file?"),
            title=_("Use premium version?"),
            message=_("Use premium version?"))

        if license_filename:
            shutil.copy(
                license_filename, os.path.join(settings.RUNNER_DIR, "redream")
            )
        return True

    def play(self):
        command = self.get_command()

        if self.runner_config.get("fs") is True:
            command.append("--fullscreen=1")
        else:
            command.append("--fullscreen=0")

        if self.runner_config.get("ar"):
            command.append("--aspect=" + self.runner_config.get("ar"))

        if self.runner_config.get("region"):
            command.append("--region=" + self.runner_config.get("region"))

        if self.runner_config.get("language"):
            command.append("--language=" + self.runner_config.get("language"))

        if self.runner_config.get("broadcast"):
            command.append("--broadcast=" + self.runner_config.get("broadcast"))

        if self.runner_config.get("time_sync"):
            command.append("--time_sync=" + self.runner_config.get("time_sync"))

        if self.runner_config.get("int_res"):
            command.append("--res=" + self.runner_config.get("int_res"))

        command.append(self.game_config.get("main_file"))

        return {"command": command}
