# Permissions Features

- Existing chat, sheet, comment, memory, export and Habit proposals use PermissionGuard.
- Owner callbacks are explicitly registered at application startup.
- Pending records are bounded, expiring, integrity-checked and process-local.
- Request fields and chat scope are captured before approval.
- Decline never dispatches; approval consumes a record before owner execution.
- Unknown, expired, altered or already-used approvals are rejected.
- Legacy pending-action imports remain compatible.
