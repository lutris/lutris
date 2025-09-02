import sqlite3
import threading
from typing import Any

# Prevent multiple access to the database (SQLite limitation)
DB_LOCK = threading.RLock()


class db_cursor(object):
    def __init__(self, db_path):
        self.db_path = db_path
        self.db_conn = None

    def __enter__(self):
        self.db_conn = sqlite3.connect(self.db_path)
        cursor = self.db_conn.cursor()
        return cursor

    def __exit__(self, _type, value, traceback):
        self.db_conn.commit()
        self.db_conn.close()


def cursor_execute(cursor, query, params=None):
    """Execute a SQL query, run it in a lock block"""
    params = params or ()
    lock = DB_LOCK.acquire(timeout=5)  # pylint: disable=consider-using-with
    if not lock:
        raise RuntimeError(f"Database is busy. Not executing {query}")

    try:
        return cursor.execute(query, params)
    finally:
        DB_LOCK.release()


def db_insert(db_path, table, fields):
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


def db_update(db_path, table, updated_fields, conditions):
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


def db_delete(db_path, table, field, value):
    with db_cursor(db_path) as cursor:
        cursor_execute(cursor, "delete from {0} where {1}=?".format(table, field), (value,))


def db_select(db_path, table, fields=None, condition=None):
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


def db_query(db_path, query, params=()):
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


def add_field(db_path, tablename, field):
    query = "ALTER TABLE %s ADD COLUMN %s %s" % (
        tablename,
        field["name"],
        field["type"],
    )
    with db_cursor(db_path) as cursor:
        cursor.execute(query)


def _create_filter(field: str, value: Any, params: list, negate: bool = False) -> str:
    """Creates a filter to match a field to a vlaue, or to a list of
    values. None can be used as well, to make NULL."""
    also_null = False
    if hasattr(value, "__iter__") and not isinstance(value, str):
        values = list(value)

        if None in values:
            values.remove(None)
            also_null = True
    elif value is None:
        also_null = True
        values = []
    else:
        values = [value]

    if len(values) == 0:
        if negate:
            if also_null:
                return f"{field} IS NOT NULL"
            else:
                return "1 = 1"
        else:
            if also_null:
                return f"{field} IS NULL"
            else:
                return "1 = 0"

    if len(values) == 1:
        params.append(values[0])
        sql = f"{field} != ?" if negate else f"{field} = ?"
    else:
        sql = f"{field} NOT IN (" if negate else f"{field} IN ("
        for i, v in enumerate(values):
            params.append(v)
            if i > 0:
                sql += ", "
            sql += "?"
        sql += ")"

    if also_null:
        if negate:
            return f"({field} IS NOT NULL AND {sql})"
        else:
            return f"({field} IS NULL OR {sql})"
    else:
        return sql


def filtered_query(db_path, table, searches=None, filters=None, excludes=None, sorts=None):
    query = "select * from %s" % table
    params = []
    sql_filters = []
    for field in searches or {}:
        sql_filters.append("%s LIKE ?" % field)
        params.append("%" + searches[field] + "%")
    for field in filters or {}:
        sql_filters.append(_create_filter(field, filters[field], params))
    for field in excludes or {}:
        sql_filters.append(_create_filter(field, excludes[field], params, negate=True))
    if sql_filters:
        query += " WHERE " + " AND ".join(sql_filters)
    if sorts:
        query += " ORDER BY %s" % ", ".join(["%s %s" % (sort[0], sort[1]) for sort in sorts])
    else:
        query += " ORDER BY slug ASC"
    return db_query(db_path, query, tuple(params))
