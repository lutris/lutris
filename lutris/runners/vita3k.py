from gettext import gettext as _
from pathlib import Path

from lutris.exceptions import MissingGameExecutableError
from lutris.runners.json import JSON_RUNNER_DIRS, JsonRunner


class MissingVitaTitleIDError(MissingGameExecutableError):
    """Raise when the Title ID field has not be supplied to the Vita runner game options"""

    def __init__(self, message=None, *args, **kwargs):
        if not message:
            message = _("The Vita App has no Title ID set")

        super().__init__(message, *args, **kwargs)


# Use the vita3k.json runner definition as a base class
RUNNER_NAME = "vita3k"


def get_vita_json_path():
    for json_dir in JSON_RUNNER_DIRS:
        json_dir_path = Path(json_dir)
        if not json_dir_path.exists():
            continue
        vita_json_path = json_dir_path / f"{RUNNER_NAME}.json"
        if vita_json_path.exists():
            return vita_json_path


class vita3k(JsonRunner):
    legacy_entry_point_option = "main_file"

    def __init__(self, config=None):
        self.json_path = get_vita_json_path()
        super().__init__(config=config)

    def play(self):
        # Replace the "main_file" key with "title_id" option for backwards compatibility
        # This is to prevent the MissingGameExecutableError exception, as Vita3k runs game via title ID
        if self.entry_point_option not in self.game_config and __class__.legacy_entry_point_option in self.game_config:
            self.game_config[self.entry_point_option] = self.game_config[__class__.legacy_entry_point_option]
            del self.game_config[__class__.legacy_entry_point_option]

        if not self.game_config.get(self.entry_point_option, ""):
            raise MissingVitaTitleIDError(_("The Vita App has no Title ID set"))

        return super().play()
