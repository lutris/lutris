from lutris import settings
from lutris.database import sql
from lutris.util.log import logger

PGA_DB = settings.PGA_DB
DATABASE = {
    "games": [
        {
            "name": "id",
            "type": "INTEGER",
            "indexed": True
        },
        {
            "name": "name",
            "type": "TEXT"
        },
        {
            "name": "slug",
            "type": "TEXT"
        },
        {
            "name": "installer_slug",
            "type": "TEXT"
        },
        {
            "name": "parent_slug",
            "type": "TEXT"
        },
        {
            "name": "platform",
            "type": "TEXT"
        },
        {
            "name": "runner",
            "type": "TEXT"
        },
        {
            "name": "executable",
            "type": "TEXT"
        },
        {
            "name": "directory",
            "type": "TEXT"
        },
        {
            "name": "updated",
            "type": "DATETIME"
        },
        {
            "name": "lastplayed",
            "type": "INTEGER"
        },
        {
            "name": "installed",
            "type": "INTEGER"
        },
        {
            "name": "installed_at",
            "type": "INTEGER"
        },
        {
            "name": "year",
            "type": "INTEGER"
        },
        {
            "name": "configpath",
            "type": "TEXT"
        },
        {
            "name": "has_custom_banner",
            "type": "INTEGER"
        },
        {
            "name": "has_custom_icon",
            "type": "INTEGER"
        },
        {
            "name": "playtime",
            "type": "REAL"
        },
        {
            "name": "hidden",
            "type": "INTEGER"
        },
        {
            "name": "service",
            "type": "TEXT"
        },
        {
            "name": "service_id",
            "type": "TEXT"
        }
    ],
    "service_games": [
        {
            "name": "id",
            "type": "INTEGER",
            "indexed": True
        },
        {
            "name": "service",
            "type": "TEXT"
        },
        {
            "name": "appid",
            "type": "TEXT"
        },
        {
            "name": "name",
            "type": "TEXT"
        },
        {
            "name": "slug",
            "type": "TEXT"
        },
        {
            "name": "icon",
            "type": "TEXT"
        },
        {
            "name": "logo",
            "type": "TEXT"
        },
        {
            "name": "url",
            "type": "TEXT"
        },
        {
            "name": "details",
            "type": "TEXT"
        },
        {
            "name": "lutris_slug",
            "type": "TEXT"
        },
    ],
    "sources": [
        {"name": "id", "type": "INTEGER", "indexed": True},
        {"name": "uri", "type": "TEXT UNIQUE"},
    ],
    "categories": [
        {"name": "id", "type": "INTEGER", "indexed": True},
        {"name": "name", "type": "TEXT", "unique": True},
    ],
    "games_categories": [
        {"name": "game_id", "type": "INTEGER", "indexed": False},
        {"name": "category_id", "type": "INTEGER", "indexed": False},
    ]
}


def get_schema(tablename):
    """
    Fields:
        - position
        - name
        - type
        - not null
        - default
        - indexed
    """
    tables = []
    query = "pragma table_info('%s')" % tablename
    with sql.db_cursor(PGA_DB) as cursor:
        for row in cursor.execute(query).fetchall():
            field = {
                "name": row[1],
                "type": row[2],
                "not_null": row[3],
                "default": row[4],
                "indexed": row[5],
            }
            tables.append(field)
    return tables


def field_to_string(name="", type="", indexed=False, unique=False):  # pylint: disable=redefined-builtin
    """Converts a python based table definition to it's SQL statement"""
    field_query = "%s %s" % (name, type)
    if indexed:
        field_query += " PRIMARY KEY"
    if unique:
        field_query += " UNIQUE"
    return field_query


def create_table(name, schema):
    """Creates a new table in the database"""
    fields = ", ".join([field_to_string(**f) for f in schema])
    query = "CREATE TABLE IF NOT EXISTS %s (%s)" % (name, fields)
    logger.debug("[PGAQuery] %s", query)
    with sql.db_cursor(PGA_DB) as cursor:
        cursor.execute(query)


def migrate(table, schema):
    """Compare a database table with the reference model and make necessary changes

    This is very basic and only the needed features have been implemented (adding columns)

    Args:
        table (str): Name of the table to migrate
        schema (dict): Reference schema for the table

    Returns:
        list: The list of column names that have been added
    """

    existing_schema = get_schema(table)
    migrated_fields = []
    if existing_schema:
        columns = [col["name"] for col in existing_schema]
        for field in schema:
            if field["name"] not in columns:
                logger.info("Migrating %s field %s", table, field["name"])
                migrated_fields.append(field["name"])
                sql.add_field(PGA_DB, table, field)
    else:
        create_table(table, schema)
    return migrated_fields


def syncdb():
    """Update the database to the current version, making necessary changes
    for backwards compatibility."""
    for table in DATABASE:
        migrate(table, DATABASE[table])
