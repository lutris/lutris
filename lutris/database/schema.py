"""Definition of the database schema and the migration that keeps it up to date.

DATABASE is the reference model of every table Lutris owns. It doubles as the column
whitelist used by lutris.database.sql to validate dynamically built queries, and is
therefore handed to the SQL layer at import time.

Migration is additive only. SQLite cannot drop, rename or retype a column with a plain
statement, and rebuilding tables to do so would risk user data, so a database is never
rewritten: missing columns are added, and anything else found in the database is reported
and left alone. Changes to a table are applied in one transaction (see sql.add_fields), so
a failure part way through leaves the table as it was.
"""

from typing import Any, TypeAlias

from lutris import settings
from lutris.database import sql
from lutris.util.log import logger

DBSchema: TypeAlias = list[dict[str, Any]]

DATABASE: dict[str, DBSchema] = {
    "games": [
        {"name": "id", "type": "INTEGER", "indexed": True},
        {"name": "name", "type": "TEXT"},
        {
            "name": "sortname",
            "type": "TEXT",
        },
        {"name": "slug", "type": "TEXT"},
        {"name": "installer_slug", "type": "TEXT"},
        {"name": "parent_slug", "type": "TEXT"},
        {"name": "platform", "type": "TEXT"},
        {"name": "runner", "type": "TEXT"},
        {"name": "executable", "type": "TEXT"},
        {"name": "directory", "type": "TEXT"},
        {"name": "updated", "type": "DATETIME"},
        {"name": "lastplayed", "type": "INTEGER"},
        {"name": "installed", "type": "INTEGER"},
        {"name": "installed_at", "type": "INTEGER"},
        {"name": "year", "type": "INTEGER"},
        {"name": "configpath", "type": "TEXT"},
        {"name": "has_custom_banner", "type": "INTEGER"},
        {"name": "has_custom_icon", "type": "INTEGER"},
        {"name": "has_custom_coverart_big", "type": "INTEGER"},
        {"name": "playtime", "type": "REAL"},
        {"name": "service", "type": "TEXT"},
        {"name": "service_id", "type": "TEXT"},
        {
            "name": "discord_id",
            "type": "TEXT",
        },
    ],
    "service_games": [
        {"name": "id", "type": "INTEGER", "indexed": True},
        {"name": "service", "type": "TEXT"},
        {"name": "appid", "type": "TEXT"},
        {"name": "name", "type": "TEXT"},
        {"name": "slug", "type": "TEXT"},
        {"name": "icon", "type": "TEXT"},
        {"name": "logo", "type": "TEXT"},
        {"name": "url", "type": "TEXT"},
        {"name": "details", "type": "TEXT"},
        {"name": "lutris_slug", "type": "TEXT"},
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
    ],
    "saved_searches": [
        {"name": "id", "type": "INTEGER", "indexed": True},
        {"name": "name", "type": "TEXT", "unique": True},
        {"name": "search", "type": "TEXT", "unique": False},
    ],
}


def register_schema(database: dict[str, DBSchema]) -> None:
    """Declare the tables of `database` to the SQL layer, so field names can be validated."""
    for table_name, table_schema in database.items():
        sql.register_table_columns(table_name, [field["name"] for field in table_schema])


# Queries are validated against the reference schema from the moment it is available.
register_schema(DATABASE)


def get_schema(tablename: str) -> DBSchema:
    """
    Fields:
        - position
        - name
        - type
        - not null
        - default
        - indexed
    """
    sql.validate_table_name(tablename)
    fields = []
    # pragma_table_info() accepts the table name as a bound parameter, unlike the
    # `pragma table_info()` statement, so the name never has to be interpolated into SQL.
    query = "select * from pragma_table_info(?)"
    with sql.db_read_cursor(settings.DB_PATH) as cursor:
        for row in cursor.execute(query, (tablename,)):
            fields.append(
                {
                    "name": row["name"],
                    "type": row["type"],
                    "not_null": row["notnull"],
                    "default": row["dflt_value"],
                    "indexed": row["pk"],
                }
            )
    return fields


def field_to_string(name: str = "", type: str = "", indexed: bool = False, unique: bool = False) -> str:  # pylint: disable=redefined-builtin
    """Converts a python based table definition to it's SQL statement"""
    field_query = "%s %s" % (name, type)
    if indexed:
        field_query += " PRIMARY KEY"
    if unique:
        field_query += " UNIQUE"
    return field_query


def create_table(name: str, schema: DBSchema) -> None:
    """Creates a new table in the database"""
    sql.validate_table_name(name)
    for field in schema:
        sql.validate_identifier(field["name"], "field name")
        sql.validate_column_type(field.get("type", ""))
    fields = ", ".join([field_to_string(**f) for f in schema])
    query = "CREATE TABLE IF NOT EXISTS %s (%s)" % (name, fields)
    logger.debug("[Query] %s", query)
    with sql.db_cursor(settings.DB_PATH) as cursor:
        cursor.execute(query)
    if schema:
        sql.register_table_columns(name, [field["name"] for field in schema])
    sql.notify_data_change()


def migrate(table: str, schema: DBSchema) -> list[str]:
    """Compare a database table with the reference model and make necessary changes

    Only columns can be added; see the module docstring for what is deliberately not done.
    The additions for a table are applied in a single transaction, so either all of them are
    there or none is.

    Args:
        table (str): Name of the table to migrate
        schema (dict): Reference schema for the table

    Returns:
        list: The list of column names that have been added
    """
    sql.validate_table_name(table)
    existing_schema = get_schema(table)
    if not existing_schema:
        create_table(table, schema)
        return []

    existing_columns = {field["name"]: field for field in existing_schema}
    for field in schema:
        existing_field = existing_columns.get(field["name"])
        if existing_field is None:
            continue
        # SQLite reports the base type only, so "TEXT UNIQUE" is stored as "TEXT".
        existing_type = (existing_field["type"] or "").split(" ")[0].upper()
        reference_type = (field.get("type") or "").split(" ")[0].upper()
        if existing_type and reference_type and existing_type != reference_type:
            logger.warning(
                "Column %s.%s is %s in the database but %s in the schema. Changing a column type "
                "automatically is unsafe, so it is left as it is.",
                table,
                field["name"],
                existing_type,
                reference_type,
            )

    reference_columns = {field["name"] for field in schema}
    for extra_column in sorted(existing_columns.keys() - reference_columns):
        logger.debug("Keeping column %s.%s, it is not part of the reference schema", table, extra_column)

    missing_fields = [field for field in schema if field["name"] not in existing_columns]
    if not missing_fields:
        return []
    for field in missing_fields:
        logger.info("Migrating %s field %s", table, field["name"])
        if field.get("indexed"):
            logger.warning(
                "Column %s.%s is declared as a primary key, but SQLite cannot add one to an "
                "existing table; the column is created without it.",
                table,
                field["name"],
            )
    sql.add_fields(settings.DB_PATH, table, missing_fields)
    return [field["name"] for field in missing_fields]


def syncdb() -> None:
    """Update the database to the current version, making necessary changes
    for backwards compatibility."""
    # WAL is a property of the database file rather than the connection, so it is set once
    # here; it is what allows reads to run while a write transaction is in progress.
    sql.enable_wal(settings.DB_PATH)
    for table_name, table_data in DATABASE.items():
        migrate(table_name, table_data)
