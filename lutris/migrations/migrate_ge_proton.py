"""Replace the Wine version 'GE-Proton (Latest)' with 'ge-proton'."""

import os

from lutris import settings
from lutris.database.games import get_games_by_runner
from lutris.util.yaml import read_yaml_from_file, write_yaml_to_file


def migrate():
    """Run migration"""
    try:
        config_paths = [os.path.join(settings.CONFIG_DIR, "runners/wine.yml")]
        games_dir = os.path.realpath(os.path.join(settings.CONFIG_DIR, "games"))

        for db_game in get_games_by_runner("wine"):
            config_filename = db_game.get("configpath")
            if not config_filename:
                continue
            safe_filename = os.path.basename(config_filename)
            if safe_filename != config_filename:
                continue
            config_path = os.path.realpath(os.path.join(games_dir, "%s.yml" % safe_filename))
            if os.path.commonpath([games_dir, config_path]) != games_dir:
                continue
            config_paths.append(config_path)

        for config_path in config_paths:
            try:
                if os.path.isfile(config_path):
                    config = read_yaml_from_file(config_path)
                    wine = config.get("wine")
                    if wine:
                        version = wine.get("version")
                        if version and version.casefold() == "ge-proton (latest)":
                            wine["version"] = "ge-proton"
                            write_yaml_to_file(config, filepath=config_path)
            except Exception as ex:
                print(f"Failed to convert GE-Proton (Latest) to ge-proton in '{config_path}': {ex}")
    except Exception as ex:
        print(f"Failed to convert GE-Proton (Latest) to ge-proton: {ex}")
        return []
