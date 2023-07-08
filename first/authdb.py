"""AuthDb"""
import sqlite3

UserId = int
Token = str

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

