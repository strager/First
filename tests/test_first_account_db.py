import pytest
from first.accountdb import FirstAccountDb, FirstAccountNotFoundError

def test_create_new_account():
    account_db = FirstAccountDb(":memory:")
    account_1_id = account_db.create_or_get_account(
        twitch_user_id="1234",
    )
    assert account_db.get_account_twitch_user_id(account_id=account_1_id) == "1234"
    account_2_id = account_db.create_or_get_account(
        twitch_user_id="5678",
    )
    assert account_db.get_account_twitch_user_id(account_id=account_1_id) == "1234"
    assert account_db.get_account_twitch_user_id(account_id=account_2_id) == "5678"

def test_create_account_with_existing_twitch_user_id_should_reuse_account():
    account_db = FirstAccountDb(":memory:")
    account_id = account_db.create_or_get_account(
        twitch_user_id="1234",
    )
    # Create another unrelated account to try to trick FirstAccountDb.
    account_db.create_or_get_account(
        twitch_user_id="5678",
    )
    account_id_again = account_db.create_or_get_account(
        twitch_user_id="1234",
    )
    assert account_id == account_id_again

def test_getting_existing_account_by_twitch_user_id_succeeds():
    account_db = FirstAccountDb(":memory:")
    account_id = account_db.create_or_get_account(
        twitch_user_id="1234",
    )
    assert account_db.get_account_id_by_twitch_user_id(
        twitch_user_id="1234",
    ) == account_id

def test_getting_missing_account_by_twitch_user_id_fails():
    account_db = FirstAccountDb(":memory:")
    with pytest.raises(FirstAccountNotFoundError):
        account_db.get_account_id_by_twitch_user_id(
            twitch_user_id="1234",
        )

def test_get_twitch_user_for_non_existing_account():
    account_db = FirstAccountDb(":memory:")
    with pytest.raises(FirstAccountNotFoundError):
        account_db.get_account_twitch_user_id(account_id=420)
def test_set_account_reward_id():
    account_db = FirstAccountDb(":memory:")
    account_id = account_db.create_or_get_account(
        twitch_user_id="1234",
    )
    account_db.set_account_reward_id(account_id=account_id, reward_id="9999")
    assert account_db.get_account_reward_id(account_id) == "9999"
