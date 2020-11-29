import os
import shutil
from gettext import gettext as _

from lutris import settings
from lutris.gui.dialogs import FileDialog, QuestionDialog
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
            "help": _("Game data file\n" "Supported formats: GDI, CDI, CHD"),
        }
    ]
    runner_options = [
        {"option": "fs", "type": "bool", "label": _("Fullscreen mode"), "default": False},
        {
            "option": "ar",
            "type": "choice",
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

    def install(self, version=None, downloader=None, callback=None):
        def on_runner_installed(*args):
            dlg = QuestionDialog(
                {
                    "question": _("Do you want to select a premium license file?"),
                    "title": _("Use premium version?"),
                }
            )
            if dlg.result == dlg.YES:
                license_dlg = FileDialog(_("Select a license file"))
                license_filename = license_dlg.filename
                if not license_filename:
                    return
                shutil.copy(
                    license_filename, os.path.join(settings.RUNNER_DIR, "redream")
                )

        super(redream, self).install(
            version=version, downloader=downloader, callback=on_runner_installed
        )

    def play(self):
        command = [self.get_executable()]

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
