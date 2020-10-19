# Standard Library
import sqlite3
import time

# Lutris Modules
from lutris.util.log import logger

# Number of attempts to retry failed queries
DB_RETRIES = 5


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
    """Function used to retry queries in case an error occurs"""
    i = 0
    if params is None:
        params = ()
    while True:
        try:
            return cursor.execute(query, params)
        except sqlite3.OperationalError as ex:
            i += 1
            if i == DB_RETRIES:
                raise
            logger.error("SQL query '%s' failed. %d retries remaining: %s", query, DB_RETRIES - i, ex)
            error_message = str(ex)
            if "database is locked" in error_message:
                penalty = 20 * i
                logger.error("%s second penalty for trying to access the database while locked", penalty)
                time.sleep(penalty)
            else:
                time.sleep(0.5)


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
        cursor_execute(cursor, "delete from {0} where {1}=?".format(table, field), (value, ))


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
                condition_value = (condition_value, )
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


def filtered_query(
    db_path,
    table,
    searches=None,
    filters=None,
    excludes=None,
    sorts=None
):
    query = "select * from %s" % table
    params = []
    sql_filters = []
    for field in searches or {}:
        sql_filters.append("%s LIKE ?" % field)
        params.append("%" + searches[field] + "%")
    for field in filters or {}:
        if filters[field]:
            sql_filters.append("%s = ?" % field)
            params.append(filters[field])
    for field in excludes or {}:
        if excludes[field]:
            sql_filters.append("%s IS NOT ?" % field)
            params.append(excludes[field])
    if sql_filters:
        query += " WHERE " + " AND ".join(sql_filters)
    if sorts:
        query += " ORDER BY %s" % ", ".join(
            ["%s %s" % (sort[0], sort[1]) for sort in sorts]
        )
    else:
        query += " ORDER BY slug ASC"
    return db_query(db_path, query, tuple(params))
