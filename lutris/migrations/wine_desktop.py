import os
from lutris import settings
from lutris import config
from lutris.util.yaml import read_yaml_from_file


def migrate():
    config_dir = os.path.join(settings.CONFIG_DIR, "games")
    for config_file in os.listdir(config_dir):
        config_path = os.path.join(config_dir, config_file)
        config_data = read_yaml_from_file(config_path)
        if "wine" not in config_data and "winesteam" not in config_data:
            continue
        if "wine" in config_data:
            runner = "wine"
        else:
            runner = "winesteam"
        if "Desktop" in config_data[runner]:
            desktop_value = config_data[runner]["Desktop"]
            if desktop_value == "off":
                config_data[runner]["Desktop"] = False
            else:
                config_data[runner]["Desktop"] = True
        if "Desktop_res" in config_data[runner]:
            desktop_res_value = config_data[runner].pop("Desktop_res")
            config_data[runner]["WineDesktop"] = desktop_res_value
        config.write_yaml_to_file(config_path, config_data)
