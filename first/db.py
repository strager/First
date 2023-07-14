import sqlite3
import threading

class DbBase:
    """Base class for SQLite3 repository classes with useful helpers.

    Implemented helpers:
    * locking for thread safety (opt-in)
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
