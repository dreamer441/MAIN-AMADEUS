"""Process-local, integrity-checked approval records owned by Permissions."""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from types import MappingProxyType
from typing import Any, Callable, Mapping
from uuid import uuid4


ALLOWED_PENDING_ACTION_KINDS = frozenset(("chat", "sheet", "comment", "memory", "export", "habit_tracker"))


@dataclass(frozen=True, slots=True)
class PendingAction:
    """One immutable, non-persistent request waiting for GUI confirmation."""

    action_id: str
    kind: str
    fields: Mapping[str, Any]
    scope: str
    linked_chat_id: str
    issued_at: str
    integrity_hash: str

    def approval_payload(self) -> dict[str, Any]:
        """Return the safe display contract consumed by GUI adapters."""
        return {
            "action_id": self.action_id,
            "kind": self.kind,
            "display_fields": dict(self.fields),
            "scope": self.scope,
            "linked_chat_id": self.linked_chat_id,
        }


class PendingActionService:
    """Keep a small, expiring, single-use registry without durable storage."""

    def __init__(
        self,
        *,
        max_records: int = 100,
        ttl_seconds: int = 300,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        if max_records < 1 or ttl_seconds < 1:
            raise ValueError("Pending action limits must be positive.")
        self._max_records = max_records
        self._ttl = timedelta(seconds=ttl_seconds)
        self._now = now or (lambda: datetime.now(timezone.utc))
        self._records: OrderedDict[str, PendingAction] = OrderedDict()

    def create(self, *, kind: str, fields: Mapping[str, Any], scope: str = "global", linked_chat_id: str = "") -> PendingAction:
        """Register one allowed action after converting fields to safe JSON values."""
        if kind not in ALLOWED_PENDING_ACTION_KINDS:
            raise ValueError(f"Unsupported pending action kind: {kind}")
        safe_fields = self._safe_fields(fields)
        issued_at = self._now().astimezone(timezone.utc).isoformat()
        action_id = f"action-{uuid4().hex}"
        record = PendingAction(
            action_id=action_id,
            kind=kind,
            fields=MappingProxyType(safe_fields),
            scope=str(scope).strip() or "global",
            linked_chat_id=str(linked_chat_id).strip(),
            issued_at=issued_at,
            integrity_hash="",
        )
        record = replace(record, integrity_hash=self._hash(record))
        self._purge_expired()
        self._records[action_id] = record
        while len(self._records) > self._max_records:
            self._records.popitem(last=False)
        return record

    def consume(self, action_id: str) -> PendingAction:
        """Validate and remove an approved record before Core dispatches it."""
        record = self._records.get(action_id)
        if record is None:
            raise ValueError("Unknown or already used pending action.")
        if self._is_expired(record):
            del self._records[action_id]
            raise ValueError("Pending action has expired.")
        if record.integrity_hash != self._hash(record):
            del self._records[action_id]
            raise ValueError("Pending action integrity check failed.")
        del self._records[action_id]
        return record

    def decline(self, action_id: str) -> None:
        """Discard a valid pending record without performing an owner action."""
        record = self._records.get(action_id)
        if record is None:
            raise ValueError("Unknown or already used pending action.")
        if self._is_expired(record):
            del self._records[action_id]
            raise ValueError("Pending action has expired.")
        del self._records[action_id]

    def _purge_expired(self) -> None:
        for action_id, record in tuple(self._records.items()):
            if self._is_expired(record):
                del self._records[action_id]

    def _is_expired(self, record: PendingAction) -> bool:
        return self._now().astimezone(timezone.utc) > datetime.fromisoformat(record.issued_at) + self._ttl

    @staticmethod
    def _safe_fields(fields: Mapping[str, Any]) -> dict[str, Any]:
        if not isinstance(fields, Mapping):
            raise ValueError("Pending action fields must be a mapping.")
        try:
            value = json.loads(json.dumps(dict(fields), ensure_ascii=True, sort_keys=True))
        except (TypeError, ValueError) as error:
            raise ValueError("Pending action fields must be JSON-safe.") from error
        if not isinstance(value, dict):
            raise ValueError("Pending action fields must be an object.")
        return value

    @staticmethod
    def _hash(record: PendingAction) -> str:
        canonical = json.dumps(
            {
                "action_id": record.action_id,
                "kind": record.kind,
                "fields": dict(record.fields),
                "scope": record.scope,
                "linked_chat_id": record.linked_chat_id,
                "issued_at": record.issued_at,
            },
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        )
        return sha256(canonical.encode("utf-8")).hexdigest()
