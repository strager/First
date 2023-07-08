"""AuthDb"""
import sqlite3
from datetime import datetime

UserId = int
Token = str
Time = datetime

class UserNotFoundError(Exception):
    pass

class AuthDb:
    def __init__(self):
        self.db = sqlite3.connect(":memory:")
        cur = self.db.cursor()
        cur.execute("CREATE TABLE twitch_tokens(user_id UNIQUE, access_token, refresh_token, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")
        cur.execute(
            (
                "CREATE TRIGGER [UPDATE_DT]"
                "  AFTER UPDATE ON twitch_tokens FOR EACH ROW"
                "  WHEN OLD.updated_at = NEW.updated_at OR OLD.updated_at IS NULL"
                " BEGIN"
                "   UPDATE twitch_tokens SET updated_at=CURRENT_TIMESTAMP WHERE user_id=NEW.user_id;"
                " END;"
            )
        )


    def update_or_create_user(self, user_id: UserId, access_token: Token, refresh_token: Token):
        """
        If user does not exist it creates a new one.
        If it exists, it just updates the tokens.
        """
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
        cur = self.db.cursor()
        result = cur.execute("SELECT access_token FROM twitch_tokens")
        result_fetched = result.fetchone()
        if result_fetched is None:
            raise UserNotFoundError
        access_token, = result_fetched
        return access_token

    def get_refresh_token(self, user_id: UserId) -> Token:
        cur = self.db.cursor()
        result = cur.execute("SELECT refresh_token FROM twitch_tokens")
        result_fetched = result.fetchone()
        if result_fetched is None:
            raise UserNotFoundError
        refresh_token, = result_fetched
        return refresh_token

    def get_created_at_time(self, user_id: UserId) -> Time:
        cur = self.db.cursor()
        data = {
            "user_id": user_id,
        }
        result = cur.execute("SELECT created_at FROM twitch_tokens WHERE user_id = :user_id", data)
        created_at, = result.fetchone()
        created_at = datetime.fromisoformat(created_at + "Z")
        return created_at

    def get_updated_at_time(self, user_id: UserId) -> Time:
        cur = self.db.cursor()
        data = {
            "user_id": user_id,
        }
        result = cur.execute("SELECT updated_at FROM twitch_tokens WHERE user_id = :user_id", data)
        updated_at, = result.fetchone()
        updated_at = datetime.fromisoformat(updated_at + "Z")
        return updated_at
