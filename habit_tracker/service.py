"""Local SQLite persistence and task operations for the Habit Tracker module."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any


WEEKDAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")
QUADRANTS = ("unsorted", "urgent_important", "important_not_urgent", "urgent_not_important", "not_urgent_not_important")


class HabitTrackerService:
    """Own the Habit Tracker database without depending on chat or Core storage."""

    def __init__(self, project_root: Path | None = None) -> None:
        root = project_root or Path(__file__).resolve().parents[1]
        self.database_path = root / "data" / "habit_tracker" / "habit_tracker.db"
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize_database()

    def _connection(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        return connection

    @contextmanager
    def _database(self):
        """Yield one connection and always release its Windows file handle."""
        connection = self._connection()
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def _initialize_database(self) -> None:
        with self._database() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS routine_tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, description TEXT,
                    repeat_type TEXT NOT NULL DEFAULT 'daily', days_of_week TEXT,
                    every_other_day_start TEXT, is_active INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS one_time_tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, description TEXT,
                    task_date TEXT NOT NULL, is_completed INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS task_completions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, routine_task_id INTEGER NOT NULL,
                    completion_date TEXT NOT NULL, is_completed INTEGER NOT NULL DEFAULT 1,
                    completed_at TEXT NOT NULL, UNIQUE(routine_task_id, completion_date)
                );
                CREATE TABLE IF NOT EXISTS calendar_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, description TEXT,
                    event_date TEXT NOT NULL, event_time TEXT, created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS eisenhower_tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, description TEXT,
                    quadrant TEXT NOT NULL DEFAULT 'unsorted', is_completed INTEGER NOT NULL DEFAULT 0,
                    scheduled_date TEXT, scheduled_time TEXT, created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS alarms (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, alarm_type TEXT NOT NULL DEFAULT 'timer',
                    target_datetime TEXT NOT NULL, duration_minutes INTEGER, is_active INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL
                );
                """
            )
            # Existing local databases predate scheduling fields; migrations stay additive.
            columns = {row[1] for row in connection.execute("PRAGMA table_info(eisenhower_tasks)")}
            if "scheduled_date" not in columns:
                connection.execute("ALTER TABLE eisenhower_tasks ADD COLUMN scheduled_date TEXT")
            if "scheduled_time" not in columns:
                connection.execute("ALTER TABLE eisenhower_tasks ADD COLUMN scheduled_time TEXT")

    @staticmethod
    def _date(value: str | date | datetime) -> str:
        if isinstance(value, datetime):
            return value.date().isoformat()
        if isinstance(value, date):
            return value.isoformat()
        return datetime.strptime(value, "%Y-%m-%d").date().isoformat()

    @staticmethod
    def _timestamp() -> str:
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    @staticmethod
    def _title(value: str, label: str = "Task") -> str:
        clean = value.strip()
        if not clean:
            raise ValueError(f"{label} title cannot be empty.")
        return clean

    def add_routine_task(self, title: str, repeat_type: str = "daily", description: str | None = None, days_of_week: str | None = None, every_other_day_start: str | None = None) -> int:
        if repeat_type not in {"daily", "custom_days", "every_other_day"}:
            raise ValueError(f"Invalid repeat type: {repeat_type}")
        if repeat_type == "custom_days":
            days = [day.strip().lower() for day in (days_of_week or "").split(",") if day.strip()]
            if not days or any(day not in WEEKDAYS for day in days):
                raise ValueError("Custom routines need valid weekdays.")
            days_of_week = ",".join(days)
        if repeat_type == "every_other_day":
            if not every_other_day_start:
                raise ValueError("Every-other-day routines need a start date.")
            every_other_day_start = self._date(every_other_day_start)
        with self._database() as connection:
            cursor = connection.execute(
                "INSERT INTO routine_tasks (title, description, repeat_type, days_of_week, every_other_day_start, is_active, created_at) VALUES (?, ?, ?, ?, ?, 1, ?)",
                (self._title(title), description, repeat_type, days_of_week, every_other_day_start, self._timestamp()),
            )
            return int(cursor.lastrowid)

    def _routine_matches(self, task: sqlite3.Row, selected_date: str) -> bool:
        if task["repeat_type"] == "daily":
            return True
        if task["repeat_type"] == "custom_days":
            return datetime.strptime(selected_date, "%Y-%m-%d").strftime("%A").lower() in (task["days_of_week"] or "").split(",")
        if task["repeat_type"] == "every_other_day" and task["every_other_day_start"]:
            difference = (datetime.strptime(selected_date, "%Y-%m-%d").date() - datetime.strptime(task["every_other_day_start"], "%Y-%m-%d").date()).days
            return difference >= 0 and difference % 2 == 0
        return False

    def day_overview(self, selected_date: str | date | datetime) -> dict[str, Any]:
        selected = self._date(selected_date)
        with self._database() as connection:
            routine = []
            for task in connection.execute("SELECT * FROM routine_tasks WHERE is_active = 1 ORDER BY id"):
                if self._routine_matches(task, selected):
                    item = dict(task)
                    completion = connection.execute("SELECT is_completed FROM task_completions WHERE routine_task_id = ? AND completion_date = ?", (task["id"], selected)).fetchone()
                    item["is_completed_today"] = completion["is_completed"] if completion else 0
                    routine.append(item)
            one_time = [dict(row) for row in connection.execute("SELECT * FROM one_time_tasks WHERE task_date = ? ORDER BY id", (selected,))]
            events = [dict(row) for row in connection.execute("SELECT * FROM calendar_events WHERE event_date = ? ORDER BY event_time IS NULL, event_time, id", (selected,))]
            events.extend(
                {
                    "id": f"matrix-{row['id']}", "title": row["title"], "description": row["description"],
                    "event_date": row["scheduled_date"], "event_time": row["scheduled_time"], "matrix_task_id": row["id"],
                }
                for row in connection.execute("SELECT * FROM eisenhower_tasks WHERE scheduled_date = ?", (selected,))
            )
        return {"date": selected, "weekday": datetime.strptime(selected, "%Y-%m-%d").strftime("%A").lower(), "routine_tasks": routine, "one_time_tasks": one_time, "calendar_events": events}

    def set_routine_completion(self, task_id: int, selected_date: str, is_completed: bool) -> None:
        with self._database() as connection:
            connection.execute("INSERT INTO task_completions (routine_task_id, completion_date, is_completed, completed_at) VALUES (?, ?, ?, ?) ON CONFLICT(routine_task_id, completion_date) DO UPDATE SET is_completed = excluded.is_completed, completed_at = excluded.completed_at", (task_id, self._date(selected_date), int(is_completed), self._timestamp()))

    def archive_routine_task(self, task_id: int) -> None:
        with self._database() as connection:
            connection.execute("UPDATE routine_tasks SET is_active = 0 WHERE id = ?", (task_id,))

    def add_one_time_task(self, title: str, task_date: str, description: str | None = None) -> int:
        with self._database() as connection:
            cursor = connection.execute("INSERT INTO one_time_tasks (title, description, task_date, is_completed, created_at) VALUES (?, ?, ?, 0, ?)", (self._title(title), description, self._date(task_date), self._timestamp()))
            return int(cursor.lastrowid)

    def set_one_time_completion(self, task_id: int, is_completed: bool) -> None:
        with self._database() as connection:
            connection.execute("UPDATE one_time_tasks SET is_completed = ? WHERE id = ?", (int(is_completed), task_id))

    def delete_one_time_task(self, task_id: int) -> None:
        self._delete("one_time_tasks", task_id)

    def add_calendar_event(self, title: str, event_date: str, description: str | None = None, event_time: str | None = None) -> int:
        with self._database() as connection:
            cursor = connection.execute("INSERT INTO calendar_events (title, description, event_date, event_time, created_at) VALUES (?, ?, ?, ?, ?)", (self._title(title, "Event"), description, self._date(event_date), event_time, self._timestamp()))
            return int(cursor.lastrowid)

    def delete_calendar_event(self, event_id: int) -> None:
        self._delete("calendar_events", event_id)

    def calendar_dates(self) -> set[str]:
        with self._database() as connection:
            return {row[0] for row in connection.execute("SELECT task_date FROM one_time_tasks UNION SELECT event_date FROM calendar_events UNION SELECT scheduled_date FROM eisenhower_tasks WHERE scheduled_date IS NOT NULL")}

    def add_matrix_task(self, title: str, description: str | None = None, quadrant: str = "unsorted") -> int:
        if quadrant not in QUADRANTS:
            raise ValueError(f"Invalid quadrant: {quadrant}")
        with self._database() as connection:
            cursor = connection.execute("INSERT INTO eisenhower_tasks (title, description, quadrant, is_completed, created_at) VALUES (?, ?, ?, 0, ?)", (self._title(title), description, quadrant, self._timestamp()))
            return int(cursor.lastrowid)

    def update_matrix_task(self, task_id: int, *, title: str | None = None, description: str | None = None, quadrant: str | None = None, scheduled_date: str | None = None, scheduled_time: str | None = None) -> None:
        """Update supplied Eisenhower fields while preserving omitted values."""
        if quadrant is not None and quadrant not in QUADRANTS:
            raise ValueError(f"Invalid quadrant: {quadrant}")
        assignments: list[str] = []
        values: list[object] = []
        if title is not None:
            assignments.append("title = ?")
            values.append(self._title(title))
        if description is not None:
            assignments.append("description = ?")
            values.append(description)
        if quadrant is not None:
            assignments.append("quadrant = ?")
            values.append(quadrant)
        if scheduled_date is not None:
            assignments.append("scheduled_date = ?")
            values.append(self._date(scheduled_date) if scheduled_date else None)
        if scheduled_time is not None:
            assignments.append("scheduled_time = ?")
            values.append(scheduled_time or None)
        if not assignments:
            raise ValueError("Provide at least one matrix field to update.")
        values.append(task_id)
        with self._database() as connection:
            if connection.execute(f"UPDATE eisenhower_tasks SET {', '.join(assignments)} WHERE id = ?", values).rowcount != 1:
                raise ValueError("Matrix task was not found.")

    def set_matrix_completion(self, task_id: int, is_completed: bool) -> None:
        with self._database() as connection:
            if connection.execute("UPDATE eisenhower_tasks SET is_completed = ? WHERE id = ?", (int(is_completed), task_id)).rowcount != 1:
                raise ValueError("Matrix task was not found.")

    def matrix_tasks(self) -> list[dict[str, Any]]:
        with self._database() as connection:
            return [dict(row) for row in connection.execute("SELECT * FROM eisenhower_tasks ORDER BY quadrant, is_completed, id")]

    def delete_matrix_task(self, task_id: int) -> None:
        self._delete("eisenhower_tasks", task_id)

    def create_timer(self, title: str, minutes: int) -> int:
        if minutes <= 0:
            raise ValueError("Timer duration must be greater than 0.")
        with self._database() as connection:
            cursor = connection.execute("INSERT INTO alarms (title, alarm_type, target_datetime, duration_minutes, is_active, created_at) VALUES (?, 'timer', ?, ?, 1, ?)", (self._title(title, "Timer"), (datetime.now() + timedelta(minutes=minutes)).strftime("%Y-%m-%d %H:%M:%S"), minutes, self._timestamp()))
            return int(cursor.lastrowid)

    def create_alarm(self, title: str, target_datetime: str) -> int:
        """Create one explicit local alarm at a validated ISO-like local timestamp."""
        try:
            target = datetime.strptime(target_datetime, "%Y-%m-%d %H:%M")
        except ValueError as error:
            raise ValueError("Alarm time must use YYYY-MM-DD HH:MM.") from error
        with self._database() as connection:
            cursor = connection.execute(
                "INSERT INTO alarms (title, alarm_type, target_datetime, duration_minutes, is_active, created_at) VALUES (?, 'alarm', ?, NULL, 1, ?)",
                (self._title(title, "Alarm"), target.strftime("%Y-%m-%d %H:%M:%S"), self._timestamp()),
            )
            return int(cursor.lastrowid)

    def active_alarms(self) -> list[dict[str, Any]]:
        with self._database() as connection:
            return [dict(row) for row in connection.execute("SELECT * FROM alarms WHERE is_active = 1 ORDER BY target_datetime")]

    def due_alarms(self) -> list[dict[str, Any]]:
        with self._database() as connection:
            return [dict(row) for row in connection.execute("SELECT * FROM alarms WHERE is_active = 1 AND target_datetime <= ? ORDER BY target_datetime", (self._timestamp(),))]

    def deactivate_alarm(self, alarm_id: int) -> None:
        with self._database() as connection:
            connection.execute("UPDATE alarms SET is_active = 0 WHERE id = ?", (alarm_id,))

    def delete_alarm(self, alarm_id: int) -> None:
        self._delete("alarms", alarm_id)

    def _delete(self, table: str, item_id: int) -> None:
        with self._database() as connection:
            connection.execute(f"DELETE FROM {table} WHERE id = ?", (item_id,))
