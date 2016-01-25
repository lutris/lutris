from lutris import settings
from lutris.util.log import logger

MIGRATION_VERSION = 3

MIGRATIONS = []

MIGRATIONS.append([
    'wine_desktop',
])

MIGRATIONS.append([
    'gens_to_dgen',
    'fix_missing_steam_appids',
])

MIGRATIONS.append([
    'update_runners',
])


def get_migration_module(migration_name):
    return __import__('lutris.migrations.%s' % migration_name,
                      globals(), locals(), [migration_name], -1)


def migrate():
    current_version = settings.read_setting('migration_version') or 0
    current_version = int(current_version)
    if current_version >= MIGRATION_VERSION:
        return
    for i in range(current_version, MIGRATION_VERSION):
        for migration_name in MIGRATIONS[i]:
            logger.debug('Running migration: %s' % migration_name)
            migration = get_migration_module(migration_name)
            migration.migrate()

    settings.write_setting('migration_version', MIGRATION_VERSION)
