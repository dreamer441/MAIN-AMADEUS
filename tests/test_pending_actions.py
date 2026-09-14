"""Lifecycle tests for Core-owned, process-local action approvals."""

import tempfile
import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

from amadeus_core import AmadeusCore
from amadeus_core.pending_actions import PendingActionService


class _FakeLLM:
    def generate(self, *_args, **_kwargs) -> str:
        return '{"title": "Generated"}'


class PendingActionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.core = AmadeusCore(llm_client=_FakeLLM(), project_root=Path(self.directory.name))

    def tearDown(self) -> None:
        self.directory.cleanup()

    def test_registered_actions_do_not_write_until_single_use_approval(self) -> None:
        pending = self.core.create_pending_action(
            kind="sheet", fields={"request": "Plan"}, scope="global"
        )
        self.assertEqual([], self.core.sheet_service.list_sheets(scope="global"))

        result = self.core.approve_pending_action(pending.action_id)

        self.assertTrue(result.created_ids)
        with self.assertRaises(ValueError):
            self.core.approve_pending_action(pending.action_id)

    def test_decline_unknown_expired_and_tampered_actions_never_dispatch(self) -> None:
        pending = self.core.create_pending_action(kind="memory", fields={"request": "Do not save"})
        self.core.decline_pending_action(pending.action_id)
        self.assertEqual([], self.core.memory_service.list_chat_memory(self.core.get_current_chat_id()))
        with self.assertRaises(ValueError):
            self.core.decline_pending_action(pending.action_id)
        with self.assertRaises(ValueError):
            self.core.approve_pending_action("missing")

        clock = [datetime(2026, 8, 2, tzinfo=timezone.utc)]
        service = PendingActionService(now=lambda: clock[0], ttl_seconds=1)
        expired = service.create(kind="sheet", fields={"request": "Later"})
        clock[0] += timedelta(seconds=2)
        with self.assertRaisesRegex(ValueError, "expired"):
            service.consume(expired.action_id)

        tampered = self.core.create_pending_action(kind="sheet", fields={"request": "Original"})
        record = self.core.pending_actions._records[tampered.action_id]
        self.core.pending_actions._records[tampered.action_id] = replace(record, scope="chat")
        with self.assertRaisesRegex(ValueError, "integrity"):
            self.core.approve_pending_action(tampered.action_id)

    def test_all_registered_kinds_are_dispatched_only_by_core(self) -> None:
        chat = self.core.create_pending_action(kind="chat", fields={"title": "Approved chat"})
        sheet = self.core.create_pending_action(kind="sheet", fields={"request": "Approved sheet"})
        comment = self.core.create_pending_action(kind="comment", fields={"request": "Approved comment"})
        memory = self.core.create_pending_action(kind="memory", fields={"request": "Approved memory"})
        export = self.core.create_pending_action(
            kind="export", fields={"chat_id": self.core.get_current_chat_id()}
        )

        self.assertEqual(1, len(self.core.list_chats()))
        self.assertEqual([], self.core.sheet_service.list_sheets(scope="global"))
        self.assertEqual([], self.core.comment_service.store.list_all())
        self.assertEqual([], self.core.memory_service.list_chat_memory(self.core.get_current_chat_id()))
        self.core.approve_pending_action(chat.action_id)
        self.core.approve_pending_action(sheet.action_id)
        self.core.approve_pending_action(comment.action_id)
        self.core.approve_pending_action(memory.action_id)
        self.core.approve_pending_action(export.action_id)

        self.assertEqual(2, len(self.core.list_chats()))
        self.assertEqual(1, len(self.core.sheet_service.list_sheets(scope="global")))
        self.assertEqual(1, len(self.core.comment_service.store.list_all()))
        self.assertTrue(self.core.memory_service.list_global_memory())
        main_chat = self.core.chat_history_store.get_chat("main")
        assert main_chat is not None and main_chat.inner_brain_analysis is not None
        self.assertTrue(main_chat.inner_brain_analysis.export_id)

    def test_unregistered_actions_are_rejected(self) -> None:
        with self.assertRaises(ValueError):
            self.core.create_pending_action(kind="filesystem", fields={"path": "x"})


if __name__ == "__main__":
    unittest.main()
