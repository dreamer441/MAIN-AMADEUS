# Habit Tracker

`habit_tracker` ports the standalone Task Manager Personal workspace into an
independent AMADEUS module window.

It provides local routine and one-time tasks, calendar events, an Eisenhower
task list, focus timers, and due-alarm notifications. Its SQLite database lives
at `data/habit_tracker/habit_tracker.db` and is separate from chat, memory, and
other AMADEUS storage.

The module intentionally has no embedded AMADEUS chat UI or chat dependency.
