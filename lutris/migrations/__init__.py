from lutris import settings

MIGRATION_VERSION = 1


MIGRATIONS = []

MIGRATIONS.append([])  # Empty MIGRATIONS[0]

MIGRATIONS.append([
    'gens_to_dgen',
    'wine_desktop',
])


def migrate():
    current_version = settings.read_setting('migration_version') or 0
    if current_version >= MIGRATION_VERSION:
        return
    # settings.write_setting('migration_version', 1)
