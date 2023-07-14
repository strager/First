"""PointsDb"""
import sqlite3
import threading
import typing
from datetime import datetime
from first.config import cfg
from first.db import DbBase
from first.errors import RowNotFoundError
from first.twitch import TwitchUserId

RewardId = str
StreamerId = str
Date = datetime

points_config = cfg["pointsdb"]

class PointsDb(DbBase):
    db: sqlite3.Connection

    def __init__(self, db=points_config["db"]):
        super().__init__()
        self.db = sqlite3.connect(
            db,
            # See NOTE[DbBase-lock].
            check_same_thread=False,
        )
        cur = self.db.cursor()
        cur.execute(
            (
                "CREATE TABLE IF NOT EXISTS "
                "redemptions("
                    "broadcaster_id, "
                    "redemption_id UNIQUE, "
                    "user_id, "
                    "redeemed_at, "
                    "points, "
                    "level"
                ")"
            )
        )

        self._lock = threading.Lock()

    def insert_new_redemption(self, broadcaster_id: StreamerId,
                              redemption_id: RewardId, user_id: TwitchUserId,
                              redeemed_at: Date, points: int, level: int):
        with self._lock:
            cur = self.db.cursor()
            data = {
                "broadcaster_id": broadcaster_id,
                "redemption_id": redemption_id,
                "user_id": user_id,
                "redeemed_at": redeemed_at,
                "points": points,
                "level": level,
            }
            cur.execute(
                (
                    "INSERT INTO redemptions "
                    "(broadcaster_id, redemption_id, user_id, redeemed_at, points, level) "
                    "VALUES(:broadcaster_id, :redemption_id, :user_id, :redeemed_at, :points, :level)"
                ), data)

            self.db.commit()

    def get_monthly_channel_points(self, broadcaster_id: StreamerId) -> typing.List[typing.Tuple[TwitchUserId, int]]:
        with self._lock:
            cur = self.db.cursor()
            data = {
                "broadcaster_id": broadcaster_id,
            }
            result = cur.execute(
                (
                    "SELECT user_id, SUM(points) FROM redemptions "
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

    def get_lifetime_channel_points(self, broadcaster_id: StreamerId) -> typing.List[typing.Tuple[TwitchUserId, int]]:
        with self._lock:
            cur = self.db.cursor()
            data = {
                "broadcaster_id": broadcaster_id,
            }
            result = cur.execute(
                (
                    "SELECT user_id, SUM(points) FROM redemptions "
                    "WHERE broadcaster_id = :broadcaster_id "
                    "GROUP BY user_id"
                ),
                data
            )
            result_fetched = result.fetchall()
        if result_fetched is None:
            raise RowNotFoundError
        return result_fetched

    def get_monthly_user_points(self, user_id: TwitchUserId) -> int:
        with self._lock:
            cur = self.db.cursor()
            data = {
                "user_id": user_id,
            }
            result = cur.execute(
                (
                    "SELECT SUM(points) FROM redemptions "
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

    def get_lifetime_user_points(self, user_id: TwitchUserId) -> int:
        with self._lock:
            cur = self.db.cursor()
            data = {
                "user_id": user_id,
            }
            result = cur.execute(
                (
                    "SELECT SUM(points) FROM redemptions "
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

    def get_streamers_monthly_leaderboard(self) -> typing.List[typing.Tuple[StreamerId, int]]:
        with self._lock:
            cur = self.db.cursor()
            result = cur.execute(
                (
                    "SELECT broadcaster_id, COUNT(points) FROM redemptions "
                    "WHERE level = 1 "
                    "AND redeemed_at >= date('now', 'start of month') "
                    "AND redeemed_at < date('now', 'start of month', '+1 month') "
                    "GROUP BY broadcaster_id"
                ),
            )
            result_fetched = result.fetchall()
        if result_fetched is None:
            raise RowNotFoundError
        return result_fetched

    def get_streamers_lifetime_leaderboard(self) -> typing.List[typing.Tuple[StreamerId, int]]:
        with self._lock:
            cur = self.db.cursor()
            result = cur.execute(
                (
                    "SELECT broadcaster_id, COUNT(points) FROM redemptions "
                    "WHERE level = 1 "
                    "GROUP BY broadcaster_id"
                ),
            )
            result_fetched = result.fetchall()
        if result_fetched is None:
            raise RowNotFoundError
        return result_fetched
