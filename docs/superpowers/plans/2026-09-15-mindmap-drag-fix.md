# Mind Map Drag Responsiveness Fix

**Goal:** Restore smooth dragging and retain final positions during slow background saves.

**Architecture:** GUI owns transient gesture/queue state; Core remains the sole route to graph persistence. Existing service validation still enforces locked and pinned nodes.

## Constraints

- Preserve data formats, source ownership, pin/lock protection and Core APIs.
- Keep physics available outside manual dragging and for explicit layout.
- Never render stale snapshots into an active gesture or an unsaved position.
- Serialize queued position writes; coalesce only unsent updates to the same node.
- Preserve failure reporting and recover interaction after failed writes.

## Work

- [x] Pause physics during pointer gestures; defer snapshot refresh until gesture/save queue completion.
- [x] Save through existing worker lifecycle without disabling Canvas for position writes; drain latest queued moves before refreshing.
- [x] Compute the projected position map once per snapshot rather than once per node.
- [x] Verify regressions in tests/test_mindmap_drag.py: pointer movement, paused physics, deferred refresh, slow/failed saves, latest-position persistence and single map construction. Run existing Mind Map and synchronization tests, full suite and compileall.
- Delivery: stage reviewed task paths and commit/push to the already approved remote; record the resulting commit in the completion message.

## Validation

- Full suite: 341 tests passed in 79.395 seconds.
- Targeted drag suite: all six tests passed, including the additional shutdown regression added after full-suite discovery.
- Python compileall passed after the final test addition.
- Independent code review found no blocking issue; its requested shutdown test passed.

## Manual check

Restart AMADEUS, open Mind Map and drag an unlocked node several times quickly. It should follow the pointer and remain at its last released position after save/reopen. Repeat with a connected node and confirm graph links remain attached. Pinned/locked nodes should remain immovable.
