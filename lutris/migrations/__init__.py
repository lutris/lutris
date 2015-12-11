from lutris import settings

MIGRATION_VERSION = 1

MIGRATIONS = []

MIGRATIONS.append([
    'gens_to_dgen',
    'wine_desktop',
])


def get_migration_module(migration_name):
    return __import__('lutris.migrations.%s' % migration_name,
                      globals(), locals(), [migration_name], -1)


def migrate():
    current_version = settings.read_setting('migration_version') or 0
    if current_version >= MIGRATION_VERSION:
        return
    for i in range(current_version, MIGRATION_VERSION):
        for migration_name in MIGRATIONS[i]:
            migration = get_migration_module(migration_name)
            migration.migrate()

    settings.write_setting('migration_version', MIGRATION_VERSION)
