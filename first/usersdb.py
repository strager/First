"""UsersDb"""
import sqlite3
import threading
import typing
from first.config import cfg
from first.errors import UserNotFoundError, UniqueUserAlreadyExists

UserId = str

users_config = cfg["usersdb"]

class UsersDb:
    db: sqlite3.Connection

    # See NOTE[TwitchAuthDb-lock].
    __lock: threading.Lock

    def __init__(self, db=users_config["db"]):
        self.db = sqlite3.connect(
            db,
            # See NOTE[TwitchAuthDb-lock].
            check_same_thread=False,
        )
        cur = self.db.cursor()
        cur.execute(
            (
                "CREATE TABLE IF NOT EXISTS "
                "users("
                    "user_id UNIQUE, "
                    "user_login UNIQUE, "
                    "user_name UNIQUE"
                ")"
            )
        )

        self.__lock = threading.Lock()

    def insert_new_user(self, user_id: UserId, user_login: str, user_name: str):
        with self.__lock:
            cur = self.db.cursor()
            data = {
                "user_id": user_id,
                "user_login": user_login,
                "user_name": user_name,
            }
            try:
                cur.execute(
                    (
                        "INSERT INTO users (user_id, user_login, user_name) VALUES(:user_id, :user_login, :user_name) "
                    ), data)
                self.db.commit()
            except sqlite3.IntegrityError as error:
                raise UniqueUserAlreadyExists

    def get_user_login_from_id(self, user_id: UserId) -> str:
        with self.__lock:
            cur = self.db.cursor()
            data = {
                "user_id": user_id,
            }
            result = cur.execute("SELECT user_login FROM users WHERE user_id = :user_id", data)
            result_fetched = result.fetchone()
        if result_fetched is None:
            raise UserNotFoundError
        login, = result_fetched
        return login

    def get_user_name_from_id(self, user_id: UserId) -> str:
        with self.__lock:
            cur = self.db.cursor()
            data = {
                "user_id": user_id,
            }
            result = cur.execute("SELECT user_name FROM users WHERE user_id = :user_id", data)
            result_fetched = result.fetchone()
        if result_fetched is None:
            raise UserNotFoundError
        name, = result_fetched
        return name
