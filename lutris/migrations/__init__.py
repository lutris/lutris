import importlib

from lutris import settings
from lutris.util.log import logger

MIGRATION_VERSION = 10  # Never decrease this number

# Replace deprecated migrations with empty lists
MIGRATIONS = [
    [], [], [], [], [], [], [],
    ["mess_to_mame"],
    ["migrate_hidden_ids"],
    ["migrate_steam_appids"],
]


def get_migration_module(migration_name):
    return importlib.import_module("lutris.migrations.%s" % migration_name)


def migrate():
    current_version = int(settings.read_setting("migration_version") or 0)
    if current_version >= MIGRATION_VERSION:
        return
    for i in range(current_version, MIGRATION_VERSION):
        for migration_name in MIGRATIONS[i]:
            logger.info("Running migration: %s", migration_name)
            migration = get_migration_module(migration_name)
            migration.migrate()

    settings.write_setting("migration_version", MIGRATION_VERSION)
