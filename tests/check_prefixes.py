#!/usr/bin/env python3
import os
import sys
import subprocess
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from lutris.util.wineregistry import WineRegistry
PREFIXES_PATH = os.path.expanduser("~/Games/wine/prefixes")


def get_registries():
    registries = []
    directories = os.listdir(PREFIXES_PATH)
    directories.append(os.path.expanduser("~/.wine"))
    for prefix in directories:
        for path in os.listdir(os.path.join(PREFIXES_PATH, prefix)):
            if path.endswith(".reg"):
                registries.append(os.path.join(PREFIXES_PATH, prefix, path))
    return registries


def check_registry(registry_path):
    with open(registry_path, 'r') as registry_file:
        original_content = registry_file.read()

    try:
        registry = WineRegistry(registry_path)
    except:
        sys.stderr.write("Error parsing {}\n".format(registry_path))
        raise
    content = registry.render()
    if content != original_content:
        wrong_path = os.path.join(os.path.dirname(__file__), 'error.reg')
        with open(wrong_path, 'w') as wrong_reg:
            wrong_reg.write(content)

        print("Content of parsed registry doesn't match: {}".format(registry_path))
        subprocess.call(["meld", registry_path, wrong_path])
        sys.exit(2)


registries = get_registries()
for registry in registries:
    check_registry(registry)
print("All {} registry files validated!".format(len(registries)))
