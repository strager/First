import pytest
import threading
from datetime import datetime, timedelta
from first.pointsdb import PointsDb
from first.config import cfg

points_config = cfg["pointsdb"]

def get_current_year_month():
    today = datetime.now()
    return f"{today.year}-{today.month:02d}-"

def insert_data():
    pointsdb = PointsDb(":memory:")
    pointsdb.insert_new_redemption(
            broadcaster_id = "274637212",
            reward_id = "92af127c-7326-4483-a52b-b0da0be61c01",
            user_id = "user_1",
            redeemed_at = datetime.fromisoformat(get_current_year_month()+"01T18:37:32Z"),
            level = 5,
    )
    pointsdb.insert_new_redemption(
            broadcaster_id = "274637212",
            reward_id = "84fc127c-7326-1213-a52b-b0da0be61d03",
            user_id = "user_1",
            redeemed_at = datetime.fromisoformat(get_current_year_month()+"15T10:25:02Z"),
            level = 3,
    )
    pointsdb.insert_new_redemption(
            broadcaster_id = "274637212",
            reward_id = "cf8cda1d-3b5f-4acf-8f79-d4382113cbec",
            user_id = "user_2",
            redeemed_at = datetime.fromisoformat(get_current_year_month()+"16T18:37:32Z"),
            level = 1,
    )
    pointsdb.insert_new_redemption(
            broadcaster_id = "013456789",
            reward_id = "c6fc26fe-3593-4f39-98c1-921ecb48c8ca",
            user_id = "user_1",
            redeemed_at = datetime.fromisoformat(get_current_year_month()+"03T18:37:32Z"),
            level = 5,
    )
    pointsdb.insert_new_redemption(
            broadcaster_id = "013456789",
            reward_id = "886572f1-f29a-4067-b3a0-7fd8f2f44735",
            user_id = "user_1",
            redeemed_at = datetime.fromisoformat(get_current_year_month()+"03T18:37:32Z")-timedelta(days=60),
            level = 5,
    )
    return pointsdb

def test_get_monthly_redemptions():
    pointsdb = insert_data()
    assert [("user_1", 8), ("user_2", 1)] == pointsdb.get_monthly_channel_points("274637212")
    assert [("user_1", 5)] == pointsdb.get_monthly_channel_points("013456789")

def test_get_lifetime_redemptions():
    pointsdb = insert_data()
    assert [("user_1", 8), ("user_2", 1)] == pointsdb.get_lifetime_channel_points("274637212")
    assert [("user_1", 10)] == pointsdb.get_lifetime_channel_points("013456789")

def test_get_monthly_user_points():
    pointsdb = insert_data()
    assert 13 == pointsdb.get_monthly_user_points("user_1")
    assert 1 == pointsdb.get_monthly_user_points("user_2")

def test_get_lifetime_user_points():
    pointsdb = insert_data()
    assert 18 == pointsdb.get_lifetime_user_points("user_1")
    assert 1 == pointsdb.get_lifetime_user_points("user_2")
