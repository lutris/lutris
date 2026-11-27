"""Low level helpers around the SQLite database.

Two rules are enforced throughout this module:

* Identifiers (table names, column names, sort fields) are never interpolated blindly: they
  are validated by the helpers below, which reject anything that is not a plain SQL
  identifier and check known tables against an explicit column whitelist (see
  register_table_columns()).
* Values are always passed as bound parameters, never formatted into the query.

Writes are serialized through DB_LOCK (one writer at a time, see db_cursor). Reads go through
db_read_cursor and are not serialized: SQLite serves every connection a consistent snapshot,
and WAL journaling (enabled by schema.syncdb()) lets readers and the writer work at the same
time.
"""

import logging
import re
import sqlite3
import threading
from collections.abc import Callable, Iterable, Sequence
from types import TracebackType
from typing import Any, TypeAlias

# Prevent concurrent writes to the database (SQLite limitation). This must cover the entire
# connection lifetime, not just individual statements: SQLite holds a transaction's locks
# from its first statement all the way through the commit, so guarding only execute() would
# leave the commit in db_cursor.__exit__ free to race with another connection and fail with
# "database is locked".
DB_LOCK = threading.RLock()

# How long to wait for DB_LOCK - and, through the connection timeout, for SQLite's own locks -
# before concluding something is deadlocked. DB_LOCK is held for a whole transaction, and a
# thread holding it can be delayed by an unrelated CPU-bound thread hogging the GIL, so this
# is deliberately generous.
DB_LOCK_TIMEOUT_SECONDS = 30

DBResult: TypeAlias = dict[str, Any]
DBResults: TypeAlias = list[DBResult]
DBCondition: TypeAlias = tuple[str, Any]
DBConditionsDict: TypeAlias = dict[str, Any]
DBUpdateDict: TypeAlias = dict[str, Any]
DBParams: TypeAlias = Sequence[Any]
DBSorts: TypeAlias = Sequence[Sequence[str]]
DBQueryCondition: TypeAlias = tuple[str, DBParams]
# Only plain, unquoted SQL identifiers are accepted for table and column names.
_IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
# Field expressions are limited to a plain column or one of the aggregates below, as used by
# count lookups (e.g. "COUNT(id)").
_AGGREGATE_PATTERN = re.compile(
    r"^(?P<function>[A-Za-z_][A-Za-z0-9_]*)\s*\(\s*(?P<argument>\*|[A-Za-z_][A-Za-z0-9_]*)\s*\)$"
)
_ALLOWED_AGGREGATES = frozenset({"avg", "count", "group_concat", "max", "min", "sum", "total"})
_COLUMN_TYPE_PATTERN = re.compile(r"^[A-Za-z]+(?: [A-Za-z]+)*$")
_ALLOWED_COMPARISON_OPERATORS = frozenset({"=", "!=", "<", "<=", ">", ">="})
_SORT_DIRECTIONS = frozenset({"ASC", "DESC"})

# Explicit column whitelist, keyed by table name. It is populated from the reference schema
# (see lutris.database.schema) and by create_table()/add_fields(), so a mistyped or hostile
# field name is rejected before it reaches SQLite. Tables that were never registered are still
# validated syntactically - which is what keeps them injection safe - but their columns cannot
# be checked.
_TABLE_COLUMNS: dict[str, frozenset[str]] = {}

# Called after a write has been committed, so that consumers of cached data can drop it.
_DATA_CHANGE_LISTENERS: list[Callable[[], None]] = []


def validate_identifier(name: Any, kind: str = "identifier") -> str:
    """Return `name` if it is a plain SQL identifier, raise ValueError otherwise.

    This is the gate that keeps dynamically built queries safe: no quoting, escaping or SQL
    keywords are possible, only letters, digits and underscores not starting with a digit.
    """
    if not isinstance(name, str) or not _IDENTIFIER_PATTERN.match(name):
        raise ValueError("Invalid SQL %s: %r" % (kind, name))
    return name


def validate_table_name(table: str) -> str:
    """Return `table` if it is a valid table name, raise ValueError otherwise."""
    return validate_identifier(table, "table name")


def validate_field_name(table: str, field: str) -> str:
    """Return `field` if it is a valid column of `table`, raise ValueError otherwise.

    The name is always checked syntactically; when the columns of `table` are known (see
    register_table_columns) it must also be one of them, so typos and field names borrowed
    from another table fail loudly instead of silently building an invalid query.
    """
    validate_identifier(field, "field name")
    known_columns = _TABLE_COLUMNS.get(table)
    if known_columns is not None and field not in known_columns:
        raise ValueError("Unknown field '%s' for table '%s'" % (field, table))
    return field


def validate_field_expression(table: str, expression: str) -> str:
    """Validate one entry of the `fields` argument of db_select().

    Accepts `*`, a column name, or an aggregate over a column or `*` such as "COUNT(id)".
    """
    if expression == "*":
        return expression
    aggregate = _AGGREGATE_PATTERN.match(expression or "")
    if aggregate:
        if aggregate.group("function").lower() not in _ALLOWED_AGGREGATES:
            raise ValueError("Unsupported aggregate function in field expression: %r" % expression)
        argument = aggregate.group("argument")
        if argument != "*":
            validate_field_name(table, argument)
        return expression
    return validate_field_name(table, expression)


def validate_column_type(column_type: str) -> str:
    """Return `column_type` when it looks like a SQLite column type, raise ValueError otherwise."""
    if not isinstance(column_type, str) or not _COLUMN_TYPE_PATTERN.match(column_type):
        raise ValueError("Invalid SQL column type: %r" % (column_type,))
    return column_type


def register_table_columns(table: str, columns: Iterable[str]) -> None:
    """Declare the columns of `table`, enabling whitelist validation for its fields."""
    validate_table_name(table)
    for column in columns:
        validate_identifier(column, "field name")
    _TABLE_COLUMNS[table] = frozenset(columns)


def get_table_columns(table: str) -> frozenset[str] | None:
    """Return the known columns of `table`, or None if the table was never registered."""
    return _TABLE_COLUMNS.get(table)


def add_data_change_listener(listener: Callable[[], None]) -> None:
    """Register a callback that runs whenever this process commits a write.

    Caches that mirror the database must not outlive a write, so instead of guessing with
    timeouts - which both risks serving stale rows and punishes cache hits - they subscribe
    here and are invalidated explicitly. Writes made by *other* processes cannot be observed
    this way.
    """
    _DATA_CHANGE_LISTENERS.append(listener)


def notify_data_change() -> None:
    """Inform listeners that the database has been modified.

    Called by db_cursor once a transaction that changed rows has been committed, so writers do
    not have to remember to call it themselves.
    """
    for listener in tuple(_DATA_CHANGE_LISTENERS):
        try:
            listener()
        except Exception:  # pylint: disable=broad-except
            # A broken listener must never fail an otherwise successful write.
            logging.getLogger(__name__).exception("Data change listener %r failed", listener)


def _connect(db_path: str) -> sqlite3.Connection:
    """Open a connection with the settings used everywhere in this module.

    The timeout is SQLite's busy timeout, so contention makes the caller wait instead of
    failing straight away with "database is locked". Rows are returned as sqlite3.Row, which
    behaves like both a tuple and a mapping, so results can be turned into dicts with a single
    `dict(row)` call instead of zipping rows with cursor.description by hand.
    """
    connection = sqlite3.connect(db_path, timeout=DB_LOCK_TIMEOUT_SECONDS)
    connection.row_factory = sqlite3.Row
    return connection


class db_cursor:
    """Context manager providing a cursor for a single, serialized database transaction.

    DB_LOCK is held for the whole block, from connecting through the commit, so that one
    transaction's SQLite locks can never overlap another connection's.

    Since that lock is global and guards every write in the process, code inside the block
    must not suspend. In particular, never yield from inside one of these blocks: the lock
    would stay held until the generator is resumed or garbage collected, and if the caller
    abandons the generator part way through, every other write blocks until then.

    For the same reason, keep the block short and do not let the cursor outlive it; the
    connection is closed on exit. Use db_read_cursor for read-only queries.
    """

    def __init__(self, db_path: str):
        self.db_path = db_path
        self.db_conn: sqlite3.Connection | None = None

    def __enter__(self) -> sqlite3.Cursor:
        if not DB_LOCK.acquire(timeout=DB_LOCK_TIMEOUT_SECONDS):  # pylint: disable=consider-using-with
            raise RuntimeError(f"Database is busy. Not opening {self.db_path}")

        try:
            self.db_conn = _connect(self.db_path)
            return self.db_conn.cursor()
        except BaseException:
            # __exit__ is not called when __enter__ raises, so the lock must be released here
            # or it would be held forever.
            DB_LOCK.release()
            raise

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if self.db_conn is None:
            DB_LOCK.release()
            return
        changed_rows = 0
        try:
            try:
                if exc_type is None:
                    self.db_conn.commit()
                    # Counted per connection (each transaction gets a fresh one), so this is
                    # exactly "did this transaction change any row". Doing it here rather than
                    # in each write helper means raw cursor writes signal data changes too.
                    changed_rows = self.db_conn.total_changes
                else:
                    self.db_conn.rollback()
            finally:
                self.db_conn.close()
        finally:
            DB_LOCK.release()
        if changed_rows:
            # Listeners are told after the lock is released: they are allowed to do work of
            # their own, and holding DB_LOCK while they run would invite deadlocks.
            notify_data_change()


class db_read_cursor:
    """Context manager providing a cursor for read-only queries, without taking DB_LOCK.

    Reads do not need to be serialized: every connection sees a consistent snapshot, and with
    WAL journaling enabled (see enable_wal()) readers do not block the writer or each other.
    Keeping reads off the global lock means a slow query issued by one thread can no longer
    stall writes - or the UI thread - for the duration of another thread's write transaction.

    Writes must go through db_cursor() instead: this cursor never commits, so a write issued
    here would be rolled back on exit.
    """

    def __init__(self, db_path: str):
        self.db_path = db_path
        self.db_conn: sqlite3.Connection | None = None

    def __enter__(self) -> sqlite3.Cursor:
        self.db_conn = _connect(self.db_path)
        return self.db_conn.cursor()

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if self.db_conn is not None:
            self.db_conn.close()
            self.db_conn = None


def enable_wal(db_path: str) -> bool:
    """Switch the database to WAL journaling. Returns True if WAL is active afterwards.

    Readers and the single writer can then run concurrently, which is what makes the
    lock-free read path (db_read_cursor) safe. WAL is a persistent property of the database
    file, so this only has to happen once; schema.syncdb() calls it on startup.

    Failure is not fatal: WAL is unsupported on some filesystems (network shares, for
    instance), in which case Lutris keeps working with the default rollback journal and just
    has more lock contention.
    """
    try:
        with db_cursor(db_path) as cursor:
            row = cursor.execute("PRAGMA journal_mode=WAL").fetchone()
        journal_mode = str(row[0]).lower() if row else ""
    except sqlite3.DatabaseError as err:
        logging.getLogger(__name__).warning("Could not enable WAL journaling on %s: %s", db_path, err)
        return False
    if journal_mode != "wal":
        logging.getLogger(__name__).info("Database %s kept journal mode %r", db_path, journal_mode)
        return False
    return True


def cursor_execute(cursor: sqlite3.Cursor, query: str, params: DBParams | None = None) -> sqlite3.Cursor:
    """Execute a SQL query on a cursor opened by db_cursor (writes, serialized) or
    db_read_cursor (reads, concurrent)."""
    return cursor.execute(query, params or ())


def _fetch_results(cursor: sqlite3.Cursor, query: str, params: DBParams | None = None) -> DBResults:
    """Run a read query on `cursor` and return its rows as dicts.

    The cursor must come from this module, since the dict conversion relies on the sqlite3.Row
    row factory installed by _connect().
    """
    cursor_execute(cursor, query, params)
    return [dict(row) for row in cursor.fetchall()]


def _last_rowid(cursor: sqlite3.Cursor) -> int:
    """Return the rowid of the last inserted row.

    sqlite3 types lastrowid as optional, so this narrows it and fails loudly rather than
    handing back None for a table without rowid.
    """
    rowid = cursor.lastrowid
    if rowid is None:
        raise RuntimeError("Insert did not return a rowid")
    return int(rowid)


def _create_insert_query(table: str, columns: Sequence[str]) -> str:
    """Build an insert statement whose (validated) identifier list is fixed once per call."""
    validate_table_name(table)
    if not columns:
        raise ValueError("Cannot insert into '%s' without fields" % table)
    validated_columns = ", ".join(validate_field_name(table, column) for column in columns)
    placeholders = ", ".join("?" for _ in columns)
    return "insert into %s(%s) values (%s)" % (table, validated_columns, placeholders)


def db_insert(db_path: str, table: str, fields: DBUpdateDict) -> int:
    """Insert a single row, returning the rowid it got."""
    query = _create_insert_query(table, list(fields.keys()))
    with db_cursor(db_path) as cursor:
        cursor_execute(cursor, query, tuple(fields.values()))
        inserted_id = _last_rowid(cursor)
    return inserted_id


def db_insert_many(db_path: str, table: str, rows: Sequence[DBUpdateDict]) -> list[int]:
    """Insert several rows in a single transaction, returning the rowids in row order.

    All rows must have the same set of keys (they are inserted with one statement). Doing this
    in a single transaction matters: the alternative - one db_insert() per row - takes DB_LOCK
    and commits once per row, which for a bulk import means hundreds of fsyncs and hundreds of
    chances to run into a competing connection. A failure while inserting leaves the table
    untouched, so a partly imported batch can never be observed.
    """
    if not rows:
        return []
    columns = list(rows[0].keys())
    for row in rows[1:]:
        if list(row.keys()) != columns:
            raise ValueError("All rows must have the same fields: %s != %s" % (columns, list(row.keys())))
    query = _create_insert_query(table, columns)
    inserted_ids = []
    with db_cursor(db_path) as cursor:
        for row in rows:
            cursor_execute(cursor, query, tuple(row[column] for column in columns))
            inserted_ids.append(_last_rowid(cursor))
    return inserted_ids


def db_update(db_path: str, table: str, updated_fields: DBUpdateDict, conditions: DBConditionsDict) -> sqlite3.Cursor:
    """Update `table` with the values given in the dict `updated_fields` on the
    condition given with the `conditions` dict.

    Conditions are mandatory: an update without them would silently rewrite every row of the
    table. The returned cursor is closed along with the connection.
    """
    validate_table_name(table)
    if not updated_fields:
        raise ValueError("Cannot update '%s' without fields" % table)
    if not conditions:
        raise ValueError("Refusing to update '%s' without conditions" % table)
    columns = ", ".join("%s=?" % validate_field_name(table, field) for field in updated_fields)
    condition_field = " AND ".join("%s=?" % validate_field_name(table, field) for field in conditions)
    field_values = tuple(updated_fields.values())
    condition_values = tuple(conditions.values())

    with db_cursor(db_path) as cursor:
        query = "UPDATE {0} SET {1} WHERE {2}".format(table, columns, condition_field)
        result = cursor_execute(cursor, query, field_values + condition_values)
    return result


def db_delete(db_path: str, table: str, field: str, value: Any) -> None:
    """Delete the rows of `table` whose `field` equals `value`."""
    validate_table_name(table)
    validate_field_name(table, field)
    with db_cursor(db_path) as cursor:
        cursor_execute(cursor, "delete from {0} where {1}=?".format(table, field), (value,))


def db_select(
    db_path: str, table: str, fields: Sequence[str] | None = None, condition: DBCondition | None = None
) -> DBResults:
    """Read rows from a single table, optionally restricted to one condition.

    `condition` is a (field, value) pair; an iterable value matches any of its members. Passing
    None as the value never matches anything, since SQL can't compare against NULL - this call
    used to build a `field = NULL` query, which is always false, and keeps that result rather
    than silently switching to `IS NULL` and returning unrelated rows. Use db_select with a
    condition, or filtered_query() with `filters`, to look for NULL values.
    """
    filters = None
    if condition:
        condition_field, condition_value = condition
        if condition_value is None:
            return []
        filters = {condition_field: condition_value}
    # Unlike filtered_query(), db_select() has never applied an implicit sort order, so callers
    # that expect their rows in insertion order keep getting them that way.
    query, params = _create_select_query(table, fields=fields, filters=filters, default_sort=False)
    with db_read_cursor(db_path) as cursor:
        return _fetch_results(cursor, query, params)


def db_query(db_path: str, query: str, params: DBParams = ()) -> DBResults:
    """Run a literal read query, with any variable parts passed as bound parameters.

    Prefer the builders below (filtered_query, db_select) for anything but hand written joins;
    they validate identifiers for you.
    """
    with db_read_cursor(db_path) as cursor:
        return _fetch_results(cursor, query, params)


def add_fields(db_path: str, tablename: str, fields: Sequence[dict[str, Any]]) -> None:
    """Add one or more columns to an existing table, in a single transaction.

    SQLite's ALTER TABLE cannot add PRIMARY KEY or UNIQUE *constraints* to an existing table,
    so a field flagged `unique` gets a unique index instead, which enforces the same thing.
    A field flagged `indexed` (the primary key of a freshly created table) cannot be honoured
    here and is reported by the caller - see schema.migrate().
    """
    validate_table_name(tablename)
    if not fields:
        return
    queries = []
    added_columns = []
    for field in fields:
        column = validate_identifier(field["name"], "field name")
        column_type = validate_column_type(field.get("type", ""))
        queries.append(("ALTER TABLE %s ADD COLUMN %s %s" % (tablename, column, column_type), ()))
        added_columns.append(column)
        if field.get("unique"):
            index_name = "%s_%s_unique" % (tablename, column)
            queries.append(("CREATE UNIQUE INDEX IF NOT EXISTS %s ON %s (%s)" % (index_name, tablename, column), ()))
    with db_cursor(db_path) as cursor:
        for query, params in queries:
            cursor_execute(cursor, query, params)
    # Keep the whitelist in step with the table so the new columns are usable right away.
    known_columns = _TABLE_COLUMNS.get(tablename)
    if known_columns is not None:
        _TABLE_COLUMNS[tablename] = known_columns | frozenset(added_columns)
    notify_data_change()


def add_field(db_path: str, tablename: str, field: dict[str, str]) -> None:
    """Add a single column to an existing table (see add_fields)."""
    add_fields(db_path, tablename, [field])


def _create_filter(table: str, field: str, value: Any, params: list[Any], negate: bool = False) -> str:
    """Creates a filter to match a field to a value, or to a list of
    values. None can be used as well, to make NULL."""
    validate_field_name(table, field)
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
        if negate:
            return f"({field} IS NULL OR {sql})"
        return sql


def create_comparison(table: str, field: str, operator: str, value: Any) -> DBQueryCondition:
    """Build a (sql, params) condition comparing `field` to `value`.

    Meant for the operators that `filters` does not cover (`<`, for instance). The field is
    validated here, so callers never format an identifier into SQL themselves.
    """
    validate_field_name(table, field)
    if operator not in _ALLOWED_COMPARISON_OPERATORS:
        raise ValueError("Unsupported comparison operator: %r" % (operator,))
    return "%s %s ?" % (field, operator), (value,)


def create_null_check(table: str, field: str, is_null: bool = True) -> DBQueryCondition:
    """Build a (sql, params) condition testing `field` for NULL (or for NOT NULL)."""
    validate_field_name(table, field)
    return "%s IS %sNULL" % (field, "" if is_null else "NOT "), ()


def _default_slug_sort(table: str) -> str:
    """The implicit ordering of filtered_query(), when the table can provide it.

    Every table Lutris registers has a slug column, but this helper is also used on ad-hoc
    tables (by migrations and tests) where an unconditional "ORDER BY slug" would simply fail.
    """
    known_columns = _TABLE_COLUMNS.get(table)
    if known_columns is not None and "slug" not in known_columns:
        return ""
    return " ORDER BY slug ASC"


def _create_order_by(table: str, sorts: DBSorts) -> str:
    """Build the ORDER BY clause of a query, validating every field and direction."""
    clauses = []
    for sort in sorts:
        try:
            field, direction = sort[0], sort[1]
        except (IndexError, KeyError, TypeError) as err:
            raise ValueError("Invalid sort specification: %r" % (sort,)) from err
        validate_field_name(table, field)
        if not isinstance(direction, str) or direction.upper() not in _SORT_DIRECTIONS:
            raise ValueError("Invalid sort direction: %r" % (direction,))
        clauses.append("%s %s" % (field, direction.upper()))
    return " ORDER BY " + ", ".join(clauses)


def _create_select_query(
    table: str,
    fields: Sequence[str] | None = None,
    searches: dict[str, str] | None = None,
    filters: DBConditionsDict | None = None,
    excludes: DBConditionsDict | None = None,
    conditions: Sequence[DBQueryCondition] | None = None,
    sorts: DBSorts | None = None,
    default_sort: bool = True,
) -> tuple[str, DBParams]:
    """Build a select statement, validating every identifier that goes into it.

    All the read helpers funnel through here, so there is exactly one place where identifiers
    are interpolated - and it only interpolates validated ones. `conditions` are pre-built
    (sql, params) fragments from create_comparison()/create_null_check(), for the operators
    that do not fit `filters`.
    """
    validate_table_name(table)
    if fields:
        columns = ", ".join(validate_field_expression(table, field) for field in fields)
    else:
        columns = "*"
    query = "select %s from %s" % (columns, table)
    params: list[Any] = []
    sql_filters = []
    for field, search in (searches or {}).items():
        validate_field_name(table, field)
        sql_filters.append("%s LIKE ?" % field)
        params.append("%" + search + "%")
    for field, value in (filters or {}).items():
        sql_filters.append(_create_filter(table, field, value, params))
    for field, value in (excludes or {}).items():
        sql_filters.append(_create_filter(table, field, value, params, negate=True))
    for condition_sql, condition_params in conditions or []:
        sql_filters.append("(%s)" % condition_sql)
        params.extend(condition_params)
    if sql_filters:
        query += " WHERE " + " AND ".join(sql_filters)
    if sorts:
        query += _create_order_by(table, sorts)
    elif default_sort:
        query += _default_slug_sort(table)
    return query, tuple(params)


def filtered_query(
    db_path: str,
    table: str,
    searches: dict[str, str] | None = None,
    filters: DBConditionsDict | None = None,
    excludes: DBConditionsDict | None = None,
    sorts: DBSorts | None = None,
    conditions: Sequence[DBQueryCondition] | None = None,
) -> DBResults:
    """Select rows from `table`.

    Args:
        searches: field -> substring to match with LIKE
        filters: field -> value, or list of values, a row must match
        excludes: field -> value, or list of values, a row must not match (rows with NULL in
            that field are included)
        sorts: list of (field, direction) pairs; defaults to slug ascending, for tables that
            have a slug column
        conditions: pre-built (sql, params) fragments, see create_comparison()
    """
    query, params = _create_select_query(
        table, searches=searches, filters=filters, excludes=excludes, sorts=sorts, conditions=conditions
    )
    return db_query(db_path, query, params)
