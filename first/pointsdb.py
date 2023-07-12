"""PointsDb"""
import sqlite3
import threading
import typing
from datetime import datetime
from first.config import cfg
from first.errors import RowNotFoundError

RewardId = str
StreamerId = str
UserId = str
Date = datetime
Level = int

points_config = cfg["pointsdb"]

class PointsDb:
    db: sqlite3.Connection

    # See NOTE[AuthDb-lock].
    __lock: threading.Lock

    def __init__(self, db=points_config["db"]):
        self.db = sqlite3.connect(
            db,
            # See NOTE[AuthDb-lock].
            check_same_thread=False,
        )
        cur = self.db.cursor()
        cur.execute(
            (
                "CREATE TABLE IF NOT EXISTS "
                "redemptions("
                    "broadcaster_id, "
                    "reward_id UNIQUE, "
                    "user_id, "
                    "redeemed_at, "
                    "level"
                ")"
            )
        )

        self.__lock = threading.Lock()

    def insert_new_redemption(self, broadcaster_id: StreamerId, reward_id: RewardId, user_id: UserId, redeemed_at: Date, level: Level):
        with self.__lock:
            cur = self.db.cursor()
            data = {
                "broadcaster_id": broadcaster_id,
                "reward_id": reward_id,
                "user_id": user_id,
                "redeemed_at": redeemed_at,
                "level": level,
            }
            cur.execute(
                (
                    "INSERT INTO redemptions "
                    "(broadcaster_id, reward_id, user_id, redeemed_at, level) "
                    "VALUES(:broadcaster_id, :reward_id, :user_id, :redeemed_at, :level)"
                ), data)

            self.db.commit()

    def get_monthly_channel_points(self, broadcaster_id: StreamerId) -> typing.List[typing.Tuple[UserId, int]]:
        with self.__lock:
            cur = self.db.cursor()
            data = {
                "broadcaster_id": broadcaster_id,
            }
            result = cur.execute(
                (
                    "SELECT user_id, SUM(level) FROM redemptions "
                    "WHERE broadcaster_id = :broadcaster_id "
                    "AND redeemed_at >= date('now', 'start of month') "
                    "AND redeemed_at < date('now', 'start of month', '+1 month') "
                    "GROUP BY user_id"
                ),
                data
            )
            result_fetched = result.fetchall()
        if result_fetched is None:
            raise RowNotFoundError
        return result_fetched

    def get_lifetime_channel_points(self, broadcaster_id: StreamerId) -> typing.List[typing.Tuple[UserId, int]]:
        with self.__lock:
            cur = self.db.cursor()
            data = {
                "broadcaster_id": broadcaster_id,
            }
            result = cur.execute(
                (
                    "SELECT user_id, SUM(level) FROM redemptions "
                    "WHERE broadcaster_id = :broadcaster_id "
                    "GROUP BY user_id"
                ),
                data
            )
            result_fetched = result.fetchall()
        if result_fetched is None:
            raise RowNotFoundError
        return result_fetched

    def get_monthly_user_points(self, user_id: UserId) -> int:
        with self.__lock:
            cur = self.db.cursor()
            data = {
                "user_id": user_id,
            }
            result = cur.execute(
                (
                    "SELECT SUM(level) FROM redemptions "
                    "WHERE user_id = :user_id "
                    "AND redeemed_at >= date('now', 'start of month') "
                    "AND redeemed_at < date('now', 'start of month', '+1 month') "
                    "GROUP BY user_id"
                ),
                data
            )
            result_fetched = result.fetchone()
        if result_fetched is None:
            raise RowNotFoundError
        points, = result_fetched
        return points

    def get_lifetime_user_points(self, user_id: UserId) -> int:
        with self.__lock:
            cur = self.db.cursor()
            data = {
                "user_id": user_id,
            }
            result = cur.execute(
                (
                    "SELECT SUM(level) FROM redemptions "
                    "WHERE user_id = :user_id "
                    "GROUP BY user_id"
                ),
                data
            )
            result_fetched = result.fetchone()
        if result_fetched is None:
            raise RowNotFoundError
        points, = result_fetched
        return points
