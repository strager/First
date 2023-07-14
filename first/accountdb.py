from first.config import cfg
from first.db import DbBase
from first.errors import FirstAccountNotFoundError
from first.twitch import TwitchUserId
import sqlite3
import threading

accounts_config = cfg["accountsdb"]

FirstAccountId = int

class FirstAccountDb(DbBase):
    """Access to a database storing First! account information.

    An account on First! is linked to a user on Twitch.
    """

    def __init__(self, db=accounts_config["db"]):
        super().__init__()
        self._create_sqlite3_database(db)
        cur = self.db.cursor()
        cur.execute(
            (
                "CREATE TABLE IF NOT EXISTS "
                "account("
                    "account_id INTEGER PRIMARY KEY NOT NULL, "
                    "twitch_user_id UNIQUE, "
                    f"{self._created_at_and_updated_at_column_definitions_sql()}"
                ")"
            )
        )
        self._create_updated_at_trigger(table_name="account")

    def get_account_id_by_twitch_user_id(self, twitch_user_id: TwitchUserId) -> FirstAccountId:
        """Throws FirstAccountNotFoundError if no matching account was found.
        """
        with self._lock:
            cur = self.db.cursor()
            data = {
                "twitch_user_id": twitch_user_id,
            }
            result = cur.execute(
                (
                    "SELECT account_id FROM account WHERE twitch_user_id = :twitch_user_id"
                ), data)
            result_fetched = result.fetchone()
        if result_fetched is None:
            raise FirstAccountNotFoundError
        account_id, = result_fetched
        return account_id

    def create_or_get_account(self, twitch_user_id: TwitchUserId) -> FirstAccountId:
        with self._lock:
            cur = self.db.cursor()
            data = {
                "twitch_user_id": twitch_user_id,
            }
            cur.execute(
                (
                    "INSERT OR IGNORE INTO account (twitch_user_id) VALUES (:twitch_user_id) "
                ), data)
            self.db.commit()
            return cur.lastrowid

    def get_account_twitch_user_id(self, account_id: FirstAccountId) -> TwitchUserId:
        with self._lock:
            cur = self.db.cursor()
            data = {
                "account_id": account_id,
            }
            result = cur.execute("SELECT twitch_user_id FROM account WHERE account_id = :account_id", data)
            result_fetched = result.fetchone()
        if result_fetched is None:
            raise FirstAccountNotFoundError
        account_id, = result_fetched
        return account_id
