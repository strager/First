"""AuthDb"""
import sqlite3
from datetime import datetime

UserId = int
Token = str
Time = datetime

class AuthDb:
    def __init__(self):
        self.db = sqlite3.connect(":memory:")
        cur = self.db.cursor()
        cur.execute("CREATE TABLE twitch_tokens(user_id, access_token, refresh_token, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, updated_at)")


    def add_new_user(self, user_id: UserId, access_token: Token, refresh_token: Token):
        cur = self.db.cursor()
        data = {
            "user_id": user_id,
            "access_token": access_token,
            "refresh_token": refresh_token,
        }
        cur.execute("INSERT INTO twitch_tokens (user_id, access_token, refresh_token) VALUES(:user_id, :access_token, :refresh_token)", data)
        self.db.commit()


    def get_access_token(self, user_id: UserId) -> Token:
        cur = self.db.cursor()
        result = cur.execute("SELECT access_token FROM twitch_tokens")
        access_token, = result.fetchone()
        return access_token

    def get_created_at_time(self, user_id: UserId) -> Time:
        cur = self.db.cursor()
        data = {
            "user_id": user_id,
        }
        result = cur.execute("SELECT created_at FROM twitch_tokens WHERE user_id = :user_id", data)
        created_at, = result.fetchone()
        created_at = datetime.fromisoformat(created_at + "Z")
        return created_at
