"""TwitchAuthDb"""
import sqlite3
import threading
from datetime import datetime
import typing
from first.twitch import Twitch, TwitchUserId
from first.config import cfg
from first.db import DbBase, Timestamp
from first.errors import UserNotFoundError

Token = str

authdb_config = cfg["authdb"]

class TokenProvider(typing.Protocol):
    def get_access_token(self) -> Token: ...
    def refresh_access_token(self) -> Token: ...
    @property
    def user_id(self) -> TwitchUserId: ...

class TwitchAuthDbUserTokenProvider(TokenProvider):
    _authdb: "TwitchAuthDb"
    _user_id: TwitchUserId

    def __init__(self, authdb: "TwitchAuthDb", user_id: TwitchUserId) -> None:
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

    @property
    def user_id(self) -> TwitchUserId:
        return self._user_id

class TwitchAppTokenProvider(TokenProvider):

    def __init__(self) -> None: ...

    def get_access_token(self) -> Token:
        twitch = Twitch()
        return twitch.get_authenticated_app_access_token()

    def refresh_access_token(self) -> Token:
        return get_access_token()

    @property
    def user_id(self) -> TwitchUserId:
        return None

class TwitchAuthDb(DbBase):
    def __init__(self, db=authdb_config["db"]):
        super().__init__()
        self._create_sqlite3_database(db)
        cur = self.db.cursor()
        cur.execute(
            (
                "CREATE TABLE IF NOT EXISTS "
                "twitch_tokens("
                    "user_id UNIQUE, "
                    "access_token, "
                    "refresh_token, "
                    f"{self._created_at_and_updated_at_column_definitions_sql()}"
                ")"
            )
        )
        self._create_updated_at_trigger(table_name="twitch_tokens")


    def update_or_create_user(self, user_id: TwitchUserId, access_token: Token, refresh_token: Token):
        """
        If user does not exist it creates a new one.
        If it exists, it just updates the tokens.
        """
        with self._lock:
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

    def get_access_token(self, user_id: TwitchUserId) -> Token:
        with self._lock:
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

    def get_refresh_token(self, user_id: TwitchUserId) -> Token:
        with self._lock:
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

    def get_all_user_ids_slow(self) -> typing.List[TwitchUserId]:
        user_ids = []
        with self._lock:
            cur = self.db.cursor()
            result = cur.execute("SELECT user_id FROM twitch_tokens")
            while True:
                rows = result.fetchmany()
                if not rows:
                    break
                for (user_id,) in rows:
                    user_ids.append(user_id)
        return user_ids

    def get_created_at_time(self, user_id: TwitchUserId) -> Timestamp:
        created_at, _updated_at = self._get_created_at_and_updated_at(
            table_name="twitch_tokens",
            where_clause="WHERE user_id = :user_id",
            parameters={
                "user_id": user_id,
            },
        )
        return created_at

    def get_updated_at_time(self, user_id: TwitchUserId) -> Timestamp:
        _created_at, updated_at = self._get_created_at_and_updated_at(
            table_name="twitch_tokens",
            where_clause="WHERE user_id = :user_id",
            parameters={
                "user_id": user_id,
            },
        )
        return updated_at
