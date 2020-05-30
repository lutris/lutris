# Lutris Modules
from lutris.pga import PGA_DB
from lutris.util.sql import cursor_execute, db_cursor

SQL_STATEMENTS = [
    """
    create table games_tmp
    (
        id INTEGER primary key,
        name TEXT,
        slug TEXT,
        installer_slug TEXT,
        parent_slug TEXT,
        platform TEXT,
        runner TEXT,
        executable TEXT,
        directory TEXT,
        updated DATETIME,
        lastplayed INTEGER,
        installed INTEGER,
        installed_at INTEGER,
        year INTEGER,
        steamid INTEGER,
        gogid INTEGER,
        configpath TEXT,
        has_custom_banner INTEGER,
        has_custom_icon INTEGER,
        playtime REAL,
        humblestoreid TEXT
    );
    """, """
    insert into games_tmp select
        id,
        name,
        slug,
        installer_slug,
        parent_slug,
        platform,
        runner,
        executable,
        directory,
        updated,
        lastplayed,
        installed,
        installed_at,
        year,
        steamid,
        gogid,
        configpath,
        has_custom_banner,
        has_custom_icon,
        playtime,
        humblestoreid
    from games;
    """, "drop table games;", "alter table games_tmp rename to games;"
]


def migrate():
    """Convert the playtime to float from text, to allow sorting correctly"""

    with db_cursor(PGA_DB) as cursor:
        for sql_statement in SQL_STATEMENTS:
            cursor_execute(cursor, sql_statement)
