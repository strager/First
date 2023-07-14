import datetime
import sqlite3
import threading
import typing

SQLCode = str
SQLTableName = str

Timestamp = datetime.datetime

class DbBase:
    """Base class for SQLite3 repository classes with useful helpers.

    Implemented helpers:
    * locking for thread safety (opt-in)
    * created-at and updated-at columns (opt-in)
    """

    # NOTE[DbBase-lock]: __lock serializes access to self.db, but does not
    # synchronize other instances of TwitchAuthDb with the same database file.
    #
    # sqlite3 can serialize calls automatically (sqlite3.threadsafety == 3), but
    # this is a build-time setting for CPython this not guaranteed to be
    # enabled. Therefore, we must serialize/lock ourselves.
    _lock: threading.Lock

    db: sqlite3.Connection

    def __init__(self) -> None:
        self._lock = threading.Lock()

    def _create_sqlite3_database(self, path: str) -> None:
        """Create a new database file or open an existing database file.

        If path is ":memory:", an in-memory database is created instead of a
        regular file.

        This function assigns to self.db.
        """
        self.db = sqlite3.connect(
            path,
            # See NOTE[DbBase-lock].
            check_same_thread=False,
        )

    def _created_at_and_updated_at_column_definitions_sql(self) -> SQLCode:
        """SQL syntax in CREATE TABLE to make two columns: 'created_at' and
        'updated_at'.
        """
        return (
            "created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, "
            "updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP"
        )

    def _create_updated_at_trigger(self, table_name: SQLTableName) -> SQLCode:
        """Create a trigger to update updated_at when any row changes in the
        given table.

        Precondition: The table has a rowid (i.e. WITHOUT ROWID was not specified).
        """
        with self._lock:
            cur = self.db.cursor()
            cur.execute(
                (
                    f"CREATE TRIGGER IF NOT EXISTS [{table_name}_update_dt]"
                    f"  AFTER UPDATE ON {table_name} FOR EACH ROW"
                    "  WHEN OLD.updated_at = NEW.updated_at OR OLD.updated_at IS NULL"
                    " BEGIN"
                    f"   UPDATE {table_name} SET updated_at=CURRENT_TIMESTAMP WHERE rowid=NEW.rowid;"
                    " END;"
                )
            )

    def _get_created_at_and_updated_at(self, table_name: SQLTableName, where_clause: SQLCode, parameters: typing.Dict) -> typing.Tuple[Timestamp, Timestamp]:
        with self._lock:
            cur = self.db.cursor()
            result = cur.execute(f"SELECT created_at, updated_at FROM {table_name} {where_clause}", parameters)
            created_at, updated_at = result.fetchone()
        created_at = datetime.datetime.fromisoformat(created_at + "Z")
        updated_at = datetime.datetime.fromisoformat(updated_at + "Z")
        return created_at, updated_at
