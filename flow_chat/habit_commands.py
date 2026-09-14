"""Deterministic Flow parsing for the public Habit Tracker action surface."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, Protocol

from creation_module import propose_habit_task
from habit_tracker.service import WEEKDAYS


class HabitReader(Protocol):
    """The read-only Habit Tracker facade Flow may use without Core internals."""
    def day_overview(self, selected_date: str) -> dict[str, Any]: ...
    def matrix_tasks(self) -> list[dict[str, Any]]: ...
    def active_alarms(self) -> list[dict[str, Any]]: ...


@dataclass(frozen=True, slots=True)
class HabitCommandResult:
    """A local Flow response or a Core-owned action proposal."""
    response: str = ""
    action: dict[str, Any] | None = None


class FlowHabitCommandInterpreter:
    """Parse explicit, bounded-natural-language Habit Tracker commands without an LLM."""

    def __init__(self, habit_tracker: HabitReader, *, today: callable | None = None) -> None:
        self._habit_tracker = habit_tracker
        self._today = today or date.today

    def execute(self, message: str) -> HabitCommandResult | None:
        """Return None when text is not a Habit request and should remain normal Flow."""
        command = self._normalize(message)
        if command is None:
            return None
        if command in {"help", ""}:
            return HabitCommandResult(self._help())
        if command.startswith("show") or command in {"list tasks", "list habits", "what are my habits"}:
            return self._read(command)
        return self._write(command)

    @staticmethod
    def _normalize(message: str) -> str | None:
        clean = message.strip()
        is_habit_command = clean.lower().startswith("/habit")
        if is_habit_command:
            if len(clean) > 6 and not clean[6].isspace():
                return None
            clean = clean[6:].strip()
        else:
            # Natural aliases stay deterministic: any supported Habit Tracker noun
            # belongs to this interpreter rather than advisory or LLM routing.
            clean = re.sub(r"^(?:please\s+)?(?:(?:can|could|would)\s+you\s+)?", "", clean, flags=re.I)
        lowered = clean.lower()
        if not is_habit_command and not re.search(r"\b(?:tasks?|calendar|events?|eisenhower|matrix|alarms?|timers?|routines?|habits?)\b", lowered):
            return None
        natural_read = not is_habit_command and (
            re.search(r"\b(?:what|show|list|view|display|do i have|are there)\b", lowered) or lowered.startswith("my ")
        )
        if natural_read:
            if "eisenhower" in lowered or "matrix" in lowered:
                return "show matrix"
            if "alarm" in lowered or "timer" in lowered:
                return "show alarms"
            date_value = FlowHabitCommandInterpreter._natural_date(clean)
            return f"show; date: {date_value}" if date_value else "show"
        normalized = re.sub(
            r"^(add|create|start|set)\s+(?:a|an|my)\s+(?=(?:one[- ]time\s+)?(?:task|routine|event|calendar event|matrix|eisenhower|timer|alarm)\b)",
            r"\1 ",
            clean,
            flags=re.I,
        )
        normalized = re.sub(r"^(add|create)\s+calendar\s+event\b", r"\1 event", normalized, flags=re.I)
        if not is_habit_command and re.match(r"^(?:add|create)\s+(?:(?:one[- ]time\s+)?task|event|matrix|eisenhower|alarm)\b", normalized, re.I):
            def schedule_replacer(match: re.Match[str]) -> str:
                scheduled = f"; date: {match.group(1)}"
                return scheduled + (f"; time: {match.group(2)}" if match.group(2) else "")

            normalized = re.sub(
                r"\s+(?:(?:for|on)\s+)?(today|tomorrow|next\s+(?:" + "|".join(WEEKDAYS) + r")|\d{4}-\d{2}-\d{2})(?:\s+at\s+([0-2]\d:[0-5]\d))?(?=\s*(?:;|$))",
                schedule_replacer,
                normalized,
                flags=re.I,
            )
        return normalized

    @staticmethod
    def _natural_date(command: str) -> str | None:
        """Extract the supported natural read date while ignoring question punctuation."""
        match = re.search(
            r"\b(today|tomorrow|next\s+(?:" + "|".join(WEEKDAYS) + r")|\d{4}-\d{2}-\d{2})\b",
            command,
            re.I,
        )
        return match.group(1) if match else None

    def _read(self, command: str) -> HabitCommandResult:
        lowered = command.lower()
        if "matrix" in lowered or "eisenhower" in lowered:
            tasks = self._habit_tracker.matrix_tasks()
            return HabitCommandResult("No Eisenhower tasks." if not tasks else "\n".join(
                f"#{task['id']} [{task['quadrant']}] {'done' if task['is_completed'] else 'open'}: {task['title']}"
                + (f" on {task['scheduled_date']} {task['scheduled_time'] or ''}" if task.get("scheduled_date") else "")
                for task in tasks
            ))
        if "alarm" in lowered or "timer" in lowered:
            alarms = self._habit_tracker.active_alarms()
            return HabitCommandResult("No active alarms or timers." if not alarms else "\n".join(
                f"#{alarm['id']} {alarm['alarm_type']}: {alarm['title']} at {alarm['target_datetime']}" for alarm in alarms
            ))
        value = self._field(command, "date") or self._tail_date(command) or "today"
        selected = self._resolve_date(value)
        overview = self._habit_tracker.day_overview(selected)
        lines = [f"{overview['date']} ({overview['weekday']}):"]
        for key, label, completion in (("routine_tasks", "routine", "is_completed_today"), ("one_time_tasks", "task", "is_completed")):
            lines.extend(f"{label} #{item['id']} {'done' if item[completion] else 'open'}: {item['title']}" for item in overview[key])
        lines.extend(f"event #{item['id']}: {item['title']} {item['event_time'] or ''}" for item in overview["calendar_events"])
        return HabitCommandResult("\n".join(lines) if len(lines) > 1 else lines[0] + " no scheduled items.")

    def _write(self, command: str) -> HabitCommandResult:
        lowered = command.lower()
        if lowered.startswith(("add task ", "create task ", "add one-time task ", "create one-time task ", "add one time task ", "create one time task ")):
            return self._task("one_time", command)
        if lowered.startswith(("add routine ", "create routine ")):
            return self._routine(command)
        if lowered.startswith(("add event ", "create event ")):
            return self._event(command)
        if lowered.startswith(("add matrix ", "create matrix ", "add eisenhower ", "create eisenhower ")):
            return self._matrix(command)
        if lowered.startswith(("update matrix ", "update eisenhower ")):
            return self._matrix_update(command)
        if lowered.startswith(("complete matrix ", "complete eisenhower ", "uncomplete matrix ", "reopen matrix ")):
            return self._id_action("matrix_complete", command, "is_completed", not lowered.startswith(("uncomplete", "reopen")))
        if lowered.startswith(("delete matrix ", "delete eisenhower ")):
            return self._id_action("matrix_delete", command)
        if lowered.startswith(("complete task ", "uncomplete task ", "reopen task ")):
            return self._id_action("one_time_complete", command, "is_completed", lowered.startswith("complete"))
        if lowered.startswith("delete task "):
            return self._id_action("one_time_delete", command)
        if lowered.startswith(("complete routine ", "uncomplete routine ")):
            result = self._id_action("routine_complete", command, "is_completed", lowered.startswith("complete"))
            assert result.action is not None
            result.action["date"] = self._resolve_date(self._field(command, "date") or "today")
            return result
        if lowered.startswith(("archive routine ", "delete routine ")):
            return self._id_action("routine_archive", command)
        if lowered.startswith("delete event "):
            return self._id_action("event_delete", command)
        if lowered.startswith(("start timer ", "create timer ")):
            return self._timer(command)
        if lowered.startswith(("set alarm ", "create alarm ")):
            return self._alarm(command)
        if lowered.startswith(("cancel alarm ", "cancel timer ")):
            return self._id_action("alarm_cancel", command)
        if lowered.startswith(("delete alarm ", "delete timer ")):
            return self._id_action("alarm_delete", command)
        raise ValueError("Use /habit help for supported commands. Dates need ISO YYYY-MM-DD, today, tomorrow, or next <weekday>; times need HH:MM.")

    def _task(self, kind: str, command: str) -> HabitCommandResult:
        title = self._title(command)
        proposal = propose_habit_task(title, self._field(command, "description"))
        return self._action(kind, title=proposal.title, description=proposal.description, date=self._resolve_date(self._field(command, "date") or "today"))

    def _routine(self, command: str) -> HabitCommandResult:
        proposal = propose_habit_task(self._title(command), self._field(command, "description"))
        repeat = (self._field(command, "repeat") or "daily").lower()
        fields: dict[str, Any] = {"title": proposal.title, "description": proposal.description, "repeat_type": "daily"}
        if repeat in {"daily"}:
            pass
        elif repeat in {"every other day", "every-other-day"}:
            fields.update(repeat_type="every_other_day", every_other_day_start=self._resolve_date(self._required(command, "start")))
        else:
            days = [day.strip() for day in repeat.split(",")]
            if not days or any(day not in WEEKDAYS for day in days):
                raise ValueError("Routine repeat must be daily, every-other-day, or comma-separated weekday names.")
            fields.update(repeat_type="custom_days", days_of_week=",".join(days))
        return self._action("routine", **fields)

    def _event(self, command: str) -> HabitCommandResult:
        proposal = propose_habit_task(self._title(command), self._field(command, "description"))
        return self._action("event", title=proposal.title, description=proposal.description, date=self._resolve_date(self._required(command, "date")), time=self._time(self._field(command, "time")))

    def _matrix(self, command: str) -> HabitCommandResult:
        proposal = propose_habit_task(self._title(command), self._field(command, "description"))
        urgent, important = self._boolean(self._field(command, "urgent")), self._boolean(self._field(command, "important"))
        quadrant = {(True, True): "urgent_important", (False, True): "important_not_urgent", (True, False): "urgent_not_important", (False, False): "not_urgent_not_important"}[urgent, important]
        scheduled = self._field(command, "date")
        return self._action("matrix", title=proposal.title, description=proposal.description, quadrant=quadrant, scheduled_date=self._resolve_date(scheduled) if scheduled else None, scheduled_time=self._time(self._field(command, "time")))

    def _matrix_update(self, command: str) -> HabitCommandResult:
        task_id = self._id(command)
        fields: dict[str, Any] = {"id": task_id}
        title = self._field(command, "title")
        if title is not None:
            fields["title"] = propose_habit_task(title).title
        for field in ("description",):
            if self._field(command, field) is not None:
                fields[field] = self._field(command, field)
        urgent, important = self._field(command, "urgent"), self._field(command, "important")
        if urgent is not None or important is not None:
            current = next((item for item in self._habit_tracker.matrix_tasks() if item["id"] == task_id), None)
            if current is None:
                raise ValueError("Matrix task was not found.")
            u = self._boolean(urgent) if urgent is not None else current["quadrant"] in {"urgent_important", "urgent_not_important"}
            i = self._boolean(important) if important is not None else current["quadrant"] in {"urgent_important", "important_not_urgent"}
            fields["quadrant"] = {(True, True): "urgent_important", (False, True): "important_not_urgent", (True, False): "urgent_not_important", (False, False): "not_urgent_not_important"}[u, i]
        if self._field(command, "date") is not None:
            fields["scheduled_date"] = self._resolve_date(self._field(command, "date") or "") if self._field(command, "date") else ""
        if self._field(command, "time") is not None:
            fields["scheduled_time"] = self._time(self._field(command, "time")) or ""
        return self._action("matrix_update", **fields)

    def _timer(self, command: str) -> HabitCommandResult:
        match = re.search(r"\b(\d+)\s*(?:minutes?|mins?|m)\b", command, re.I)
        if not match:
            raise ValueError("Timer needs a positive duration, for example: /habit start timer Focus; minutes: 25.")
        minutes = int(match.group(1))
        title = self._title(command, strip_duration=True) or "Timer"
        return self._action("timer", title=title, minutes=minutes)

    def _alarm(self, command: str) -> HabitCommandResult:
        proposal = propose_habit_task(self._title(command), self._field(command, "description"))
        return self._action("alarm", title=proposal.title, target_datetime=f"{self._resolve_date(self._required(command, 'date'))} {self._time(self._required(command, 'time'))}")

    def _id_action(self, action: str, command: str, key: str | None = None, value: Any = None) -> HabitCommandResult:
        fields: dict[str, Any] = {"id": self._id(command)}
        if key:
            fields[key] = value
        return self._action(action, **fields)

    @staticmethod
    def _field(command: str, name: str) -> str | None:
        match = re.search(rf"(?:^|;)\s*{re.escape(name)}\s*:\s*([^;]*)(?=;|$)", command, re.I)
        return match.group(1).strip() if match else None

    def _title(self, command: str, *, strip_duration: bool = False) -> str:
        body = command.split(";", 1)[0]
        body = re.sub(r"^(?:add|create|start|set)\s+(?:one[- ]time\s+)?(?:matrix\s+|eisenhower\s+(?:task\s+)?|routine\s+|task\s+|event\s+|timer\s+|alarm\s+)?", "", body, flags=re.I).strip()
        if strip_duration:
            body = re.sub(r"\b(?:for\s+)?\d+\s*(?:minutes?|mins?|m)\b", "", body, flags=re.I).strip(" -")
        return body

    @staticmethod
    def _id(command: str) -> int:
        match = re.search(r"\b(\d+)\b", command.split(";", 1)[0])
        if not match:
            raise ValueError("Specify the item ID, for example: /habit delete task 12.")
        return int(match.group(1))

    def _resolve_date(self, value: str) -> str:
        clean = value.strip().lower()
        if clean == "today": return self._today().isoformat()
        if clean == "tomorrow": return (self._today() + timedelta(days=1)).isoformat()
        if clean.startswith("next ") and clean[5:] in WEEKDAYS:
            target = WEEKDAYS.index(clean[5:]); delta = (target - self._today().weekday()) % 7 or 7
            return (self._today() + timedelta(days=delta)).isoformat()
        try:
            return date.fromisoformat(value.strip()).isoformat()
        except ValueError as error:
            raise ValueError("Date is ambiguous. Use YYYY-MM-DD, today, tomorrow, or next <weekday>.") from error

    @staticmethod
    def _time(value: str | None) -> str | None:
        if value is None or not value.strip(): return None
        if not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", value.strip()):
            raise ValueError("Time is ambiguous. Use 24-hour HH:MM, for example 14:30.")
        return value.strip()

    @staticmethod
    def _boolean(value: str | None) -> bool:
        if value is None: return False
        if value.lower() in {"yes", "true", "1"}: return True
        if value.lower() in {"no", "false", "0"}: return False
        raise ValueError("Urgent and important must be yes or no.")

    def _required(self, command: str, name: str) -> str:
        value = self._field(command, name)
        if value is None or not value:
            raise ValueError(f"{name.capitalize()} is required. Use {name}: ...")
        return value

    @staticmethod
    def _action(kind: str, **fields: Any) -> HabitCommandResult:
        return HabitCommandResult(action={"kind": kind, **fields})

    @staticmethod
    def _tail_date(command: str) -> str | None:
        match = re.search(r"\b(today|tomorrow|next\s+(?:" + "|".join(WEEKDAYS) + r")|\d{4}-\d{2}-\d{2})\s*$", command, re.I)
        return match.group(1) if match else None

    @staticmethod
    def _help() -> str:
        return ("Habit commands: /habit show [date: today|YYYY-MM-DD]; /habit show matrix|alarms; "
                "/habit add task <title>; date: YYYY-MM-DD; /habit add routine <title>; repeat: daily|monday,wednesday|every-other-day; start: YYYY-MM-DD; "
                "/habit add event <title>; date: YYYY-MM-DD; time: HH:MM; /habit add matrix <title>; urgent: yes; important: no; date: YYYY-MM-DD; "
                "/habit update matrix <id>; title: ...; urgent: yes; complete/delete task|routine|matrix <id>; start timer <title> for 25 minutes; set alarm <title>; date: YYYY-MM-DD; time: HH:MM; cancel alarm <id>.")
