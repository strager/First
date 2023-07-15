"""Twitch Users Db"""
import sqlite3
import threading
import typing
from first.config import cfg
from first.db import DbBase
from first.errors import UserNotFoundError
from first.twitch import TwitchUserId

DbPath = str

class TwitchUsersDb(DbBase):
    class UserFields(typing.NamedTuple):
        login_name: str
        user_name: str

    def __init__(self, db: DbPath):
        super().__init__()
        self._create_sqlite3_database(db)
        cur = self.db.cursor()
        cur.execute(
            (
                "CREATE TABLE IF NOT EXISTS "
                "users("
                    "user_id UNIQUE, "
                    "user_login, "
                    "user_name"
                ")"
            )
        )

        self._lock = threading.Lock()

    def insert_or_update_user(self, user_id: TwitchUserId, user_login: typing.Optional[str] = None, user_name: typing.Optional[str] = None):
        if user_name is None:
            try:
                user_name = self.get_user_name_from_id(user_id)
            except UserNotFoundError:
                user_name = ""
        if user_login is None:
            try:
                user_login = self.get_user_login_from_id(user_id)
            except UserNotFoundError:
                user_login = ""
        with self._lock:
            cur = self.db.cursor()
            data = {
                "user_id": user_id,
                "user_login": user_login,
                "user_name": user_name,
            }
            cur.execute(
                (
                    "INSERT INTO users (user_id, user_login, user_name) "
                    "VALUES(:user_id, :user_login, :user_name) "
                    "ON CONFLICT (user_id) "
                    "DO UPDATE SET user_login = :user_login, user_name = :user_name"
                ), data)
            self.db.commit()

    def _get_user_fields_by_id(self, user_id: TwitchUserId) -> UserFields:
        with self._lock:
            cur = self.db.cursor()
            data = {
                "user_id": user_id,
            }
            result = cur.execute("SELECT user_login, user_name FROM users WHERE user_id = :user_id", data)
            result_fetched = result.fetchone()
        if result_fetched is None:
            raise UserNotFoundError
        fields = self.UserFields(*result_fetched)
        return fields

    def get_user_login_from_id(self, user_id: TwitchUserId) -> str:
        return self._get_user_fields_by_id(user_id).login_name

    def get_user_name_from_id(self, user_id: TwitchUserId) -> str:
        return self._get_user_fields_by_id(user_id).user_name
