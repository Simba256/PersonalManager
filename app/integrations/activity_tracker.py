"""Activity Tracker integration - queries the existing ActivityTracker SQLite database."""

from __future__ import annotations
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
from loguru import logger
from app.config import settings


class ActivityTracker:
    """Read-only interface to the existing Activity Tracker database."""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = Path(db_path or settings.activity_tracker_db)

    @property
    def available(self) -> bool:
        """Check if Activity Tracker database is accessible."""
        return self.db_path.exists()

    def _connect(self) -> sqlite3.Connection:
        """Get read-only connection to Activity Tracker database."""
        # Open read-only via URI
        uri = f"file:{self.db_path}?mode=ro"
        return sqlite3.connect(uri, uri=True, check_same_thread=False)

    def get_coding_time(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        project_path: Optional[str] = None
    ) -> list[dict]:
        """Get coding time aggregated by working directory.

        Returns:
            List of dicts with working_directory and total_minutes
        """
        if not self.available:
            logger.warning("Activity Tracker database not available")
            return []

        start = start_date or (datetime.now() - timedelta(days=7))
        end = end_date or datetime.now()

        where_clauses = [
            "start_time >= ?",
            "start_time <= ?",
            "end_time IS NOT NULL",
            "working_directory IS NOT NULL"
        ]
        params = [start.isoformat(), end.isoformat()]

        if project_path:
            where_clauses.append("working_directory LIKE ?")
            params.append(f"{project_path}%")

        query = f"""
            SELECT
                working_directory,
                ROUND(SUM(
                    (julianday(end_time) - julianday(start_time)) * 24 * 60
                ), 1) as total_minutes
            FROM terminal_activity
            WHERE {' AND '.join(where_clauses)}
            GROUP BY working_directory
            ORDER BY total_minutes DESC
        """

        try:
            with self._connect() as conn:
                cursor = conn.execute(query, params)
                return [
                    {"working_directory": row[0], "total_minutes": row[1]}
                    for row in cursor.fetchall()
                ]
        except Exception as e:
            logger.error(f"Error querying coding time: {e}")
            return []

    def get_app_usage(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> list[dict]:
        """Get app usage aggregated by app name.

        Returns:
            List of dicts with app_name, app_class, total_minutes
        """
        if not self.available:
            return []

        start = start_date or (datetime.now() - timedelta(days=1))
        end = end_date or datetime.now()

        query = """
            SELECT
                app_name,
                app_class,
                ROUND(SUM(
                    (julianday(COALESCE(end_time, datetime('now'))) - julianday(start_time)) * 24 * 60
                ), 1) as total_minutes
            FROM window_activity
            WHERE start_time >= ?
              AND start_time <= ?
              AND app_name IS NOT NULL
            GROUP BY app_name, app_class
            ORDER BY total_minutes DESC
        """

        try:
            with self._connect() as conn:
                cursor = conn.execute(query, [start.isoformat(), end.isoformat()])
                return [
                    {"app_name": row[0], "app_class": row[1], "total_minutes": row[2]}
                    for row in cursor.fetchall()
                ]
        except Exception as e:
            logger.error(f"Error querying app usage: {e}")
            return []

    def get_browser_domains(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 20
    ) -> list[dict]:
        """Get browser activity aggregated by domain.

        Returns:
            List of dicts with domain and visit_count
        """
        if not self.available:
            return []

        start = start_date or (datetime.now() - timedelta(days=1))
        end = end_date or datetime.now()

        query = """
            SELECT
                domain,
                COUNT(*) as visits
            FROM browser_activity
            WHERE timestamp >= ?
              AND timestamp <= ?
              AND domain IS NOT NULL
            GROUP BY domain
            ORDER BY visits DESC
            LIMIT ?
        """

        try:
            with self._connect() as conn:
                cursor = conn.execute(query, [start.isoformat(), end.isoformat(), limit])
                return [
                    {"domain": row[0], "visits": row[1]}
                    for row in cursor.fetchall()
                ]
        except Exception as e:
            logger.error(f"Error querying browser domains: {e}")
            return []

    def get_daily_summary(self, date: Optional[datetime] = None) -> dict:
        """Get a complete daily summary for a given date.

        Returns:
            Dict with coding_time, top_apps, browser_domains, focus_periods
        """
        target = date or datetime.now()
        day_start = target.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = target.replace(hour=23, minute=59, second=59, microsecond=999999)

        return {
            "date": target.date().isoformat(),
            "coding_time": self.get_coding_time(day_start, day_end),
            "app_usage": self.get_app_usage(day_start, day_end),
            "browser_domains": self.get_browser_domains(day_start, day_end),
            "focus_metrics": self._calculate_focus_metrics(day_start, day_end)
        }

    def _calculate_focus_metrics(self, start: datetime, end: datetime) -> dict:
        """Calculate focus and context switching metrics."""
        if not self.available:
            return {}

        # Count context switches (app changes per hour)
        switch_query = """
            SELECT COUNT(*) as switches
            FROM window_activity
            WHERE start_time >= ?
              AND start_time <= ?
              AND end_time IS NOT NULL
        """

        # Total active time
        active_query = """
            SELECT
                ROUND(SUM(
                    (julianday(end_time) - julianday(start_time)) * 24 * 60
                ), 1) as active_minutes
            FROM window_activity
            WHERE start_time >= ?
              AND start_time <= ?
              AND end_time IS NOT NULL
        """

        try:
            with self._connect() as conn:
                switches = conn.execute(
                    switch_query, [start.isoformat(), end.isoformat()]
                ).fetchone()[0]

                active = conn.execute(
                    active_query, [start.isoformat(), end.isoformat()]
                ).fetchone()[0] or 0

                return {
                    "context_switches": switches,
                    "active_minutes": round(active, 1),
                    "active_hours": round(active / 60, 1)
                }
        except Exception as e:
            logger.error(f"Error calculating focus metrics: {e}")
            return {}

    def get_peak_hours(self, days: int = 14) -> list[dict]:
        """Identify peak productivity hours based on recent coding time.

        Returns:
            List of dicts with hour (0-23) and avg_minutes per hour
        """
        if not self.available:
            return []

        since = datetime.now() - timedelta(days=days)

        query = """
            SELECT
                CAST(strftime('%H', start_time) AS INTEGER) as hour,
                ROUND(AVG(
                    (julianday(end_time) - julianday(start_time)) * 24 * 60
                ), 1) as avg_minutes
            FROM terminal_activity
            WHERE start_time >= ?
              AND end_time IS NOT NULL
              AND working_directory IS NOT NULL
            GROUP BY hour
            ORDER BY avg_minutes DESC
        """

        try:
            with self._connect() as conn:
                cursor = conn.execute(query, [since.isoformat()])
                return [
                    {"hour": row[0], "avg_minutes": row[1]}
                    for row in cursor.fetchall()
                ]
        except Exception as e:
            logger.error(f"Error querying peak hours: {e}")
            return []
