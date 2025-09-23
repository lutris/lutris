from gettext import gettext as _

from lutris.exceptions import MissingGameExecutableError
from lutris.runners.runner import Runner


class MissingVitaTitleIDError(MissingGameExecutableError):
    """Raise when the Title ID field has not be supplied to the Vita runner game options"""

    def __init__(self, message=None, *args, **kwargs):
        if not message:
            message = _("The Vita App has no Title ID set")

        super().__init__(message, *args, **kwargs)


class vita3k(Runner):
    human_name = _("Vita3K")
    platforms = [_("Sony PlayStation Vita")]
    description = _("Sony PlayStation Vita emulator")
    runnable_alone = True
    runner_executable = "vita3k/Vita3K-x86_64.AppImage"
    entry_point_option = "title_id"
    flatpak_id = None
    download_url = "https://github.com/Vita3K/Vita3K/releases/download/continuous/Vita3K-x86_64.AppImage"
    game_options = [
        {
            "option": "title_id",
            "type": "string",
            "label": _("Title ID of Installed Application"),
            "argument": "-r",
            "help": _(
                'Title ID of installed application. Eg."PCSG00042". User installed apps are located in '
                "ux0:/app/&lt;title-id&gt;."
            ),
        }
    ]
    runner_options = [
        {
            "option": "fullscreen",
            "type": "bool",
            "label": _("Fullscreen"),
            "default": True,
            "argument": "-F",
            "help": _("Start the emulator in fullscreen mode."),
        },
        {
            "option": "config",
            "type": "file",
            "label": _("Config location"),
            "argument": "-c",
            "help": _(
                'Get a configuration file from a given location. If a filename is given, it must end with ".yml", '
                "otherwise it will be assumed to be a directory."
            ),
        },
        {
            "option": "load-config",
            "label": _("Load configuration file"),
            "type": "bool",
            "argument": "-f",
            "help": _('If trues, informs the emualtor to load the config file from the "Config location" option.'),
        },
    ]

    legacy_game_options = [
        {
            "option": "main_file",
            "type": "string",
            "label": _("Legacy Title ID of Installed Application"),
            "argument": "-r",
            "help": _(
                'DEPRECATED: Legacy Title ID of installed application. The "title_id" option should be used instead'
                "ux0:/app/&lt;title-id&gt;."
            ),
        }
    ]

    # Vita3k uses an AppImage and doesn't require the Lutris runtime.
    system_options_override = [{"option": "disable_runtime", "default": True}]

    def play(self):
        """Run the game."""
        arguments = self.get_command()

        # adds arguments from the supplied option dictionary to the arguments list
        def append_args(option_dict, config):
            for option in option_dict:
                if option["option"] not in config:
                    continue
                if option["type"] == "bool":
                    if config.get(option["option"]):
                        if "argument" in option:
                            arguments.append(option["argument"])
                elif option["type"] == "choice":
                    if config.get(option["option"]) != "off":
                        if "argument" in option:
                            arguments.append(option["argument"])
                        arguments.append(config.get(option["option"]))
                elif option["type"] in ("string", "file"):
                    if "argument" in option:
                        arguments.append(option["argument"])
                    arguments.append(config.get(option["option"]))
                else:
                    raise RuntimeError("Unhandled type %s" % option["type"])

        # Append the runner arguments first, and game arguments afterwards
        append_args(self.runner_options, self.runner_config)

        # Read the "main_file" key option for backwards compatibility
        title_id = self.game_config.get(self.entry_point_option, "") or self.game_config.get("main_file", "")
        if not title_id:
            raise MissingVitaTitleIDError(_("The Vita App has no Title ID set"))

        append_args(self.game_options, self.game_config)

        # Fallback to reading the main_file option if the 'title_id' option is missing from the config yaml
        if self.entry_point_option not in self.game_config:
            append_args(self.legacy_game_options, self.game_config)
        return {"command": arguments}

    @property
    def game_path(self):
        return ""
