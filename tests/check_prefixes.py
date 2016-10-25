import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from lutris.util.wineregistry import WineRegistry
PREFIXES_PATH = os.path.expanduser("~/Games/wine/prefixes")


def get_registries():
    registries = []
    for prefix in os.listdir(PREFIXES_PATH):
        for path in os.listdir(os.path.join(PREFIXES_PATH, prefix)):
            if path.endswith(".reg"):
                registries.append(os.path.join(PREFIXES_PATH, prefix, path))
    return registries


def check_registry(registry_path):
    with open(registry_path, 'r') as registry_file:
        original_content = registry_file.read()

    registry = WineRegistry(registry_path)
    content = registry.render()
    if content != original_content:
        with open(os.path.join(os.path.dirname(__file__), 'error.reg'), 'w') as wrong_reg:
            wrong_reg.write(content)

        raise ValueError("Invalid prefix parsing for {}".format(registry_path))


for registry in get_registries():
    check_registry(registry)
