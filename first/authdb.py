"""AuthDb"""
import sqlite3
import threading
from datetime import datetime
import typing
from first.twitch import Twitch
from first.config import cfg

UserId = str
Token = str
Time = datetime

authdb_config = cfg["authdb"]

class UserNotFoundError(Exception):
    pass

class TokenProvider(typing.Protocol):
    def get_access_token(self) -> Token: ...
    def refresh_access_token(self) -> Token: ...

class AuthDbUserTokenProvider(TokenProvider):
    _authdb: "AuthDb"
    _user_id: UserId

    def __init__(self, authdb: "AuthDb", user_id: UserId) -> None:
        self._authdb = authdb
        self._user_id = user_id

    def get_access_token(self) -> Token:
        return self._authdb.get_access_token(self._user_id)

    def refresh_access_token(self) -> Token:
        refresh_result = Twitch().refresh_auth_token(self._authdb.get_refresh_token(self._user_id))
        self._authdb.update_or_create_user(
            user_id=self._user_id,
            access_token=refresh_result.new_access_token,
            refresh_token=refresh_result.new_refresh_token,
        )
        return refresh_result.new_access_token

class AuthDb:
    db: sqlite3.Connection

    # NOTE[AuthDb-lock]: __lock serializes access to self.db, but does not
    # synchronize other instances of AuthDb with the same database file.
    #
    # sqlite3 can serialize calls automatically (sqlite3.threadsafety == 3), but
    # this is a build-time setting for CPython this not guaranteed to be
    # enabled. Therefore, we must serialize/lock ourselves.
    __lock: threading.Lock

    def __init__(self, db=authdb_config["db"]):
        self.db = sqlite3.connect(
            db,
            # See NOTE[AuthDb-lock].
            check_same_thread=False,
        )
        cur = self.db.cursor()
        cur.execute(
            (
                "CREATE TABLE IF NOT EXISTS "
                "twitch_tokens("
                    "user_id UNIQUE, "
                    "access_token, "
                    "refresh_token, "
                    "created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, "
                    "updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP"
                ")"
            )
        )
        cur.execute(
            (
                "CREATE TRIGGER IF NOT EXISTS [UPDATE_DT]"
                "  AFTER UPDATE ON twitch_tokens FOR EACH ROW"
                "  WHEN OLD.updated_at = NEW.updated_at OR OLD.updated_at IS NULL"
                " BEGIN"
                "   UPDATE twitch_tokens SET updated_at=CURRENT_TIMESTAMP WHERE user_id=NEW.user_id;"
                " END;"
            )
        )

        self.__lock = threading.Lock()


    def update_or_create_user(self, user_id: UserId, access_token: Token, refresh_token: Token):
        """
        If user does not exist it creates a new one.
        If it exists, it just updates the tokens.
        """
        with self.__lock:
            cur = self.db.cursor()
            data = {
                "user_id": user_id,
                "access_token": access_token,
                "refresh_token": refresh_token,
            }
            cur.execute(
                (
                    "INSERT INTO twitch_tokens (user_id, access_token, refresh_token) VALUES(:user_id, :access_token, :refresh_token) "
                    "ON CONFLICT (user_id) "
                    "DO UPDATE SET access_token = :access_token, refresh_token = :refresh_token"
                ), data)

            self.db.commit()

    def get_access_token(self, user_id: UserId) -> Token:
        with self.__lock:
            cur = self.db.cursor()
            data = {
                "user_id": user_id,
            }
            result = cur.execute("SELECT access_token FROM twitch_tokens WHERE user_id = :user_id", data)
            result_fetched = result.fetchone()
        if result_fetched is None:
            raise UserNotFoundError
        access_token, = result_fetched
        return access_token

    def get_refresh_token(self, user_id: UserId) -> Token:
        with self.__lock:
            cur = self.db.cursor()
            data = {
                "user_id": user_id,
            }
            result = cur.execute("SELECT refresh_token FROM twitch_tokens WHERE user_id = :user_id", data)
            result_fetched = result.fetchone()
        if result_fetched is None:
            raise UserNotFoundError
        refresh_token, = result_fetched
        return refresh_token

    def get_created_at_time(self, user_id: UserId) -> Time:
        with self.__lock:
            cur = self.db.cursor()
            data = {
                "user_id": user_id,
            }
            result = cur.execute("SELECT created_at FROM twitch_tokens WHERE user_id = :user_id", data)
            created_at, = result.fetchone()
        created_at = datetime.fromisoformat(created_at + "Z")
        return created_at

    def get_updated_at_time(self, user_id: UserId) -> Time:
        with self.__lock:
            cur = self.db.cursor()
            data = {
                "user_id": user_id,
            }
            result = cur.execute("SELECT updated_at FROM twitch_tokens WHERE user_id = :user_id", data)
            updated_at, = result.fetchone()
        updated_at = datetime.fromisoformat(updated_at + "Z")
        return updated_at
