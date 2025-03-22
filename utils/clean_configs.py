import os

from lutris.database.games import get_games
from lutris.settings import CONFIG_DIR

config_paths = set()
for dbgame in get_games():
    config_paths.add(dbgame["configpath"] + ".yml")

config_files = set()
for filename in os.listdir(CONFIG_DIR):
    config_files.add(filename)


extra_configs = config_files - config_paths
for extra in extra_configs:
    os.unlink(os.path.join(CONFIG_DIR, extra))

print("Lutris configs:", len(config_paths))
print("Config files:", len(config_files))
print(len(extra_configs))
