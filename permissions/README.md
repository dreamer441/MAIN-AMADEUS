# Permissions

PermissionGuard validates existing proposed writes using process-local pending
records. Startup registers public owner callbacks; Core only forwards approval
operations. PendingActionService retains the existing expiry, integrity checking,
bounded registry and single-use semantics.

Decline performs no owner action. Approval consumes the record before dispatch;
failed owner execution does not make the same approval replayable. This is not a
general filesystem, shell or operating-system sandbox. Direct user edits retain
their existing module validation and confirmation flows.
