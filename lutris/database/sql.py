import sqlite3
import threading
from typing import Any, Dict, List, Optional, Tuple, Union

from lutris.util.log import logger

# Prevent multiple access to the database (SQLite limitation)
DB_LOCK = threading.RLock()


class db_cursor(object):
    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        self.db_conn = None

    def __enter__(self) -> sqlite3.Cursor:
        self.db_conn = sqlite3.connect(self.db_path)
        assert self.db_conn is not None
        cursor = self.db_conn.cursor()
        return cursor

    def __exit__(self, _type, value, traceback) -> None:
        assert self.db_conn is not None
        self.db_conn.commit()
        self.db_conn.close()


def cursor_execute(cursor: sqlite3.Cursor, query: str, params: Optional[Tuple] = None) -> Optional[sqlite3.Cursor]:
    """Execute a SQL query, run it in a lock block"""
    params = params or ()
    lock = DB_LOCK.acquire(timeout=1)  # pylint: disable=consider-using-with
    if not lock:
        logger.error("Database is busy. Not executing %s", query)
        return None

    try:
        return cursor.execute(query, params)
    finally:
        DB_LOCK.release()


def db_insert(db_path: str, table: str, fields: Dict) -> Optional[int]:
    columns = ", ".join(list(fields.keys()))
    placeholders = ("?, " * len(fields))[:-2]
    field_values = tuple(fields.values())
    with db_cursor(db_path) as cursor:
        cursor_execute(
            cursor,
            "insert into {0}({1}) values ({2})".format(table, columns, placeholders),
            field_values,
        )
        inserted_id = cursor.lastrowid
    return inserted_id


def db_update(db_path: str, table: str, updated_fields: Dict, conditions: Dict) -> Optional[sqlite3.Cursor]:
    """Update `table` with the values given in the dict `values` on the
    condition given with the `row` tuple.
    """
    columns = "=?, ".join(list(updated_fields.keys())) + "=?"
    field_values = tuple(updated_fields.values())

    condition_field = " AND ".join(["%s=?" % field for field in conditions])
    condition_value = tuple(conditions.values())

    with db_cursor(db_path) as cursor:
        query = "UPDATE {0} SET {1} WHERE {2}".format(table, columns, condition_field)
        result = cursor_execute(cursor, query, field_values + condition_value)
    return result


def db_delete(db_path: str, table: str, field: str, value: Union[str, int]) -> None:
    with db_cursor(db_path) as cursor:
        cursor_execute(cursor, "delete from {0} where {1}=?".format(table, field), (value,))


def db_select(
    db_path: str, table: str, fields: Optional[Tuple] = None, condition: Optional[Tuple] = None
) -> List[Dict]:
    if fields:
        columns = ", ".join(fields)
    else:
        columns = "*"
    with db_cursor(db_path) as cursor:
        query = "SELECT {} FROM {}"
        if condition:
            condition_field, condition_value = condition
            if isinstance(condition_value, (list, tuple, set)):
                condition_value = tuple(condition_value)
                placeholders = ", ".join("?" * len(condition_value))
                where_condition = " where {} in (" + placeholders + ")"
            else:
                condition_value = (condition_value,)
                where_condition = " where {}=?"
            query = query + where_condition
            query = query.format(columns, table, condition_field)
            params = condition_value
        else:
            query = query.format(columns, table)
            params = ()
        cursor_execute(cursor, query, params)
        rows = cursor.fetchall()
        column_names = [column[0] for column in cursor.description]
    results = []
    for row in rows:
        row_data = {}
        for index, column in enumerate(column_names):
            row_data[column] = row[index]
        results.append(row_data)
    return results


def db_query(db_path: str, query: str, params=()) -> List:
    with db_cursor(db_path) as cursor:
        cursor_execute(cursor, query, params)
        rows = cursor.fetchall()
        column_names = [column[0] for column in cursor.description]
    results = []
    for row in rows:
        row_data = {}
        for index, column in enumerate(column_names):
            row_data[column] = row[index]
        results.append(row_data)
    return results


def add_field(db_path: str, tablename: str, field: Dict[str, Any]) -> None:
    query = "ALTER TABLE %s ADD COLUMN %s %s" % (
        tablename,
        field["name"],
        field["type"],
    )
    with db_cursor(db_path) as cursor:
        cursor.execute(query)


def filtered_query(db_path: str, table: str, searches=None, filters=None, excludes=None, sorts=None) -> List[Dict]:
    query = "select * from %s" % table
    params = []
    sql_filters = []
    for field in searches or {}:
        sql_filters.append("%s LIKE ?" % field)
        params.append("%" + searches[field] + "%")
    for field in filters or {}:
        if filters[field] is not None:  # but 0 or False are okay!
            sql_filters.append("%s = ?" % field)
            params.append(filters[field])
    for field in excludes or {}:
        if excludes[field]:
            sql_filters.append("%s IS NOT ?" % field)
            params.append(excludes[field])
    if sql_filters:
        query += " WHERE " + " AND ".join(sql_filters)
    if sorts:
        query += " ORDER BY %s" % ", ".join(["%s %s" % (sort[0], sort[1]) for sort in sorts])
    else:
        query += " ORDER BY slug ASC"
    return db_query(db_path, query, tuple(params))
