"""Twitch User Name Cache"""
import sqlite3
import threading
import typing
from first.config import cfg
from first.twitch import Twitch, AuthenticatedTwitch, TwitchUserId
from first.errors import UserNotFoundError
from first.authdb import TwitchAuthDb, TwitchAppTokenProvider

from first.usersdb import TwitchUsersDb

users_config = cfg["usersdb"]
DbPath = str

class TwitchUserNameCache(TwitchUsersDb):

    def __init__(self, db: DbPath = users_config["db"]):
        super().__init__(db=db)
        self.twitch = AuthenticatedTwitch(TwitchAppTokenProvider())

    def get_display_name_from_id(self, user_id: TwitchUserId) -> str:
        """Calls Twitch's /helix/users endpoint if the data is missing from the database.
        https://dev.twitch.tv/docs/api/reference/#get-users
        """
        try:
            display_name = self.get_user_name_from_id(user_id)
        except UserNotFoundError:
            display_name = self.twitch.get_user_display_name_by_user_id(user_id)
            self.set_user_info(user_id=user_id, display_name=display_name)
        return display_name

    # Not needed right now:
    # Twitch's /helix/users endpoint allows multiple IDs. We can leverage this fact to improve performance of batch queries:
    # def get_display_name_from_id_batch(self, ids: typing.List[TwitchUserId]) -> typing.List[str]: ...

    # Not needed right now:
    # Calls Twitch's /helix/users endpoint if the data is missing from the database.
    # https://dev.twitch.tv/docs/api/reference/#get-users
    # def get_user_id_from_user_name(self, user_name: str) -> TwitchUserId: ...

    def set_user_info(self, user_id: TwitchUserId, user_login: typing.Optional[str] = None, display_name: typing.Optional[str] = None):
        """Update the cache if we happen to receive data from some Twitch API
        (such as a redemption notification).
        """
        self.insert_or_update_user(user_id=user_id, user_login=user_login, user_name=display_name)
