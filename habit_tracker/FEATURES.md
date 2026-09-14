# Habit Tracker Features

- Independent reusable Habit Tracker module window.
- Local SQLite persistence for routines, one-time tasks, calendar events,
  Eisenhower tasks, timers, and alarms.
- Daily task overview with completion, archival, and deletion actions.
- Routine-task creation with one or more weekday selections; the same routine
  appears on every selected weekday in each future week.
- Calendar date selection and task/event highlighting.
- The current calendar day has a light green marker distinct from task/event dates.
- Matrix task creation, update, completion, deletion, urgency/importance priority,
  and scheduled date/time fields that also highlight the calendar date.
- Eisenhower tasks render in Urgent, Important, and Task columns, sorted by the selected priority combination.
- Countdown timers, explicit scheduled alarms, active-alarm management, and due notifications.
- Public service actions are available to Flow only through Core-approved requests;
  the module remains the sole owner of Habit Tracker SQLite state.
- No embedded AMADEUS chat controls, imports, or storage dependencies.

## Core ownership cleanup — 2026-09-12

- The application window receives core.habits, forwarding to the same Habit Tracker service used by application workflows. Standalone views can still explicitly supply a service.
