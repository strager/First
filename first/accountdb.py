from first.config import cfg
from first.db import DbBase, Timestamp
from first.errors import FirstAccountNotFoundError
from first.twitch import TwitchUserId
import sqlite3
import threading
import typing

accounts_config = cfg["accountsdb"]

FirstAccountId = int
RewardId = str

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
                    "reward_id, "
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
                "SELECT account_id FROM account WHERE twitch_user_id = :twitch_user_id",
                data
            )
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
            # NOTE(strager): lastrowid is unreliable. Use RETURNING instead.
            # NOTE(strager): If we ignore on duplicates ('INSERT OR IGNORE' or
            # 'ON CONFLICT DO NOTHING'), SQLite does not return a rowid. Do a
            # no-op UPDATE SET.
            result = cur.execute(
                (
                    "INSERT INTO account (twitch_user_id) "
                    "VALUES (:twitch_user_id) "
                    "ON CONFLICT DO UPDATE SET twitch_user_id = twitch_user_id "
                    "RETURNING account_id"
                ),
                data
            )
            result_fetched = result.fetchone()
            self.db.commit()
        return result_fetched[0]

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
        return str(account_id)

    def get_account_reward_id(self, account_id: FirstAccountId) -> RewardId:
        with self._lock:
            cur = self.db.cursor()
            data = {
                "account_id": account_id,
            }
            result = cur.execute("SELECT reward_id FROM account WHERE account_id = :account_id", data)
            result_fetched = result.fetchone()
        if result_fetched is None:
            raise FirstAccountNotFoundError
        reward_id, = result_fetched
        return reward_id

    def set_account_reward_id(self, account_id: FirstAccountId | None, reward_id: RewardId | None) -> None:
        with self._lock:
            cur = self.db.cursor()
            data = {
                "account_id": account_id,
                "reward_id": reward_id,
            }
            cur.execute(
                (
                    "UPDATE account SET reward_id = :reward_id "
                    "WHERE account_id = :account_id"
                ), data)
            self.db.commit()

    def get_all_twitch_user_ids_with_any_reward_id(self) -> typing.List[TwitchUserId]:
        twitch_user_ids = []
        with self._lock:
            cur = self.db.cursor()
            result = cur.execute("SELECT twitch_user_id FROM account WHERE reward_id IS NOT NULL")
            while True:
                rows = result.fetchmany()
                if not rows:
                    break
                for (twitch_user_id, ) in rows:
                    twitch_user_ids.append(twitch_user_id)
        return twitch_user_ids

    class AccountForTesting(typing.NamedTuple):
        account_id: FirstAccountId
        twitch_user_id: TwitchUserId
        reward_id: RewardId
        created_at: Timestamp
        updated_at: Timestamp

    def get_all_accounts_for_testing(self) -> typing.List[AccountForTesting]:
        accounts = []
        with self._lock:
            cur = self.db.cursor()
            result = cur.execute("SELECT account_id, twitch_user_id, reward_id, created_at, updated_at FROM account")
            while True:
                rows = result.fetchmany()
                if not rows:
                    break
                for (account_id, twitch_user_id, reward_id, created_at, updated_at) in rows:
                    accounts.append(self.AccountForTesting(account_id=account_id, twitch_user_id=twitch_user_id, reward_id=reward_id, created_at=created_at, updated_at=updated_at))
        return accounts
