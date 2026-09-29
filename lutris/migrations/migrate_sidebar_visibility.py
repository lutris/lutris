"""Migrate 'visible_in_side_panel' runner configs to 'suppressed'.

The 'visible_in_side_panel' runner option has been replaced by the runner
suppression feature, which hides runners from the sidebar, game config
dropdown, and saved search editor.

Externally-installed runners are now suppressed by default, so both
directions of the old setting need to be converted:
  visible_in_side_panel: false  →  suppressed: true
  visible_in_side_panel: true   →  suppressed: false  (override the new default)

For runners where suppression does not apply the old key is simply removed."""

import os

from lutris import settings
from lutris.util.yaml import read_yaml_from_file, write_yaml_to_file

# Runners that can be detected externally (have a flatpak_id or override
# check_installed() to detect a non-Lutris installation). This is a fixed
# set because no new runner could already have visible_in_side_panel stored.
SUPPRESSABLE_RUNNERS = {
    "azahar",
    "cemu",
    "dolphin",
    "dosbox",
    "duckstation",
    "flatpak",
    "fsuae",
    "hatari",
    "libretro",
    "linux",
    "mame",
    "openmsx",
    "pcsx2",
    "pico8",
    "reicast",
    "rpcs3",
    "ryujinx",
    "scummvm",
    "snes9x",
    "steam",
    "wine",
    "xemu",
    "xenia",
    "yuzu",
    "zdoom",
}


def migrate():
    runners_dir = settings.RUNNERS_CONFIG_DIR
    if not os.path.isdir(runners_dir):
        return

    for filename in os.listdir(runners_dir):
        if not filename.endswith(".yml"):
            continue
        config_path = os.path.join(runners_dir, filename)
        try:
            config = read_yaml_from_file(config_path)
            if not config:
                continue
            runner_name = filename[:-4]  # strip .yml
            runner_config = config.get(runner_name, {})
            if not runner_config:
                continue

            visible = runner_config.pop("visible_in_side_panel", None)
            if visible is None:
                continue

            if runner_name in SUPPRESSABLE_RUNNERS and "suppressed" not in runner_config:
                runner_config["suppressed"] = not visible

            config[runner_name] = runner_config
            write_yaml_to_file(config, filepath=config_path)
        except Exception as ex:
            print(f"Failed to migrate visible_in_side_panel in '{config_path}': {ex}")
