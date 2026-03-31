"""Migrate the game configs for runners of FS-UAE, Mednafen, O2EM and Vice to use the platforms key
for specifying their list of choices for selecting which platform to run through their emulators."""

from gettext import gettext as _
from pathlib import Path

from lutris import settings
from lutris.database.games import get_games_by_runner
from lutris.util.yaml import read_yaml_from_file, write_yaml_to_file

BIOS_PLATFORM_RUNNERS = ["o2em"]
MACHINE_PLATFORM_RUNNERS = ["mednafen", "vice"]
MODEL_PLATFORM_RUNNERS = ["fsuae"]


def migrate() -> None:
    """Run migration"""
    try:
        # Used
        runner_to_config_path_table: dict[str, list[Path]] = {"o2em": [], "mednafen": [], "vice": [], "fsuae": []}

        for runner_name in runner_to_config_path_table.keys():
            for db_game in get_games_by_runner(runner_name):
                config_filename = db_game.get("configpath")
                runner_to_config_path_table[runner_name].append(
                    Path(settings.CONFIG_DIR) / f"games/{config_filename}.yml"
                )

        for runner_name, config_paths in runner_to_config_path_table.items():
            for config_path in config_paths:
                try:
                    if config_path.is_file():
                        config = read_yaml_from_file(str(config_path))
                        game_section = config.get("game")
                        if not isinstance(game_section, dict) or not game_section:
                            continue

                        if runner_name in BIOS_PLATFORM_RUNNERS:
                            old_platform_key = "bios"
                        elif runner_name in MACHINE_PLATFORM_RUNNERS:
                            old_platform_key = "machine"
                        else:
                            old_platform_key = "model"

                        # Migrate the old 'bios', 'machine' 'or 'model' key to the use the 'platform' key
                        # underneath the "game" object in the config file
                        if old_platform_value := game_section.get(old_platform_key):
                            game_section["platform"] = old_platform_value
                            del game_section[old_platform_key]
                            write_yaml_to_file(config, filepath=str(config_path))
                except Exception as ex:
                    print(
                        _(
                            "Failed to migrate old platform key to new 'platform' key for config '%s' using runner '%s'"
                            " : %s"
                        )
                        % (str(config_path), runner_name, str(ex))
                    )
    except Exception as ex:
        print(_("Failed to migrate old platform key to new 'platform' key: %s") % (str(ex)))
