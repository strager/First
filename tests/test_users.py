import pytest
import threading
from first.usersdb import TwitchUsersDb
from first.config import cfg

users_config = cfg["usersdb"]


def test_insert_or_update_user():
    usersdb = TwitchUsersDb(":memory:")
    usersdb.insert_or_update_user(
            user_id="5",
            user_login="potato",
            user_name="Potato"
    )
    assert "potato" == usersdb.get_user_login_from_id(user_id="5")
    assert "Potato" == usersdb.get_user_name_from_id(user_id="5")

def test_update_exisitng_user_login():
    usersdb = TwitchUsersDb(":memory:")
    usersdb.insert_or_update_user(
            user_id="5",
            user_login="potato",
            user_name="Potato"
    )
    assert "potato" == usersdb.get_user_login_from_id(user_id="5")
    assert "Potato" == usersdb.get_user_name_from_id(user_id="5")
    usersdb.insert_or_update_user(
            user_id="5",
            user_login="tomato",
    )
    assert "tomato" == usersdb.get_user_login_from_id(user_id="5")
    assert "Potato" == usersdb.get_user_name_from_id(user_id="5")

def test_update_exisitng_user_name():
    usersdb = TwitchUsersDb(":memory:")
    usersdb.insert_or_update_user(
            user_id="5",
            user_login="potato",
            user_name="Potato"
    )
    assert "potato" == usersdb.get_user_login_from_id(user_id="5")
    assert "Potato" == usersdb.get_user_name_from_id(user_id="5")
    usersdb.insert_or_update_user(
            user_id="5",
            user_name="Tomato",
    )
    assert "potato" == usersdb.get_user_login_from_id(user_id="5")
    assert "Tomato" == usersdb.get_user_name_from_id(user_id="5")
