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

    def __init__(self) -> None:
        self._lock = threading.Lock()
