"""Focused response-mode policy, persistence, Core, and Ollama adapter checks."""

import json
import tempfile
import unittest
from pathlib import Path

from amadeus_core import AmadeusCore
from llm_client import OllamaClient
from response_modes import ResponseMode, resolve_response_mode
from storage import ChatHistoryStore


class CapturingClient:
    """LLM boundary double that records policy-adjusted requests."""

    def __init__(self, response: str = "Generated reply.") -> None:
        self.response = response
        self.calls: list[dict[str, object]] = []

    def generate(self, prompt: str, system_prompt: str | None = None, num_predict: int | None = None) -> str:
        self.calls.append({"prompt": prompt, "system_prompt": system_prompt, "num_predict": num_predict})
        return self.response


class ResponseModeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_invalid_and_missing_saved_modes_migrate_to_normal(self) -> None:
        store = ChatHistoryStore(self.root)
        index = json.loads(store.index_path.read_text(encoding="utf-8"))
        index["chats"][0].pop("response_mode", None)
        store.index_path.write_text(json.dumps(index), encoding="utf-8")
        self.assertEqual("normal", store.get_current_chat().response_mode)
        saved = json.loads(store.index_path.read_text(encoding="utf-8"))
        self.assertEqual("normal", saved["chats"][0]["response_mode"])
        store.update_chat_metadata("main", response_mode="not-a-mode")
        self.assertEqual("normal", store.get_current_chat().response_mode)

    def test_resolution_priority_and_full_send_policy(self) -> None:
        decision = resolve_response_mode("short", "large", "normal")
        self.assertEqual(ResponseMode.SHORT, decision.mode)
        self.assertEqual("send_override", decision.source)
        self.assertTrue(resolve_response_mode(chat_mode="full_send").policy.allow_continuation)

    def test_dedicated_request_uses_chat_mode_prompt_and_token_budget(self) -> None:
        client = CapturingClient()
        core = AmadeusCore(llm_client=client, project_root=self.root)
        core.update_chat_metadata("main", response_mode="large")
        payload = core.handle_user_message("Explain this")
        self.assertEqual("large", payload["response_mode"])
        self.assertEqual(3200, client.calls[0]["num_predict"])
        self.assertIn("Response mode: large", str(client.calls[0]["system_prompt"]))
        events = payload["trace_events"]
        self.assertTrue(any(event.get("title") == "Response Mode Resolved" for event in events))

    def test_none_preserves_user_message_but_suppresses_assistant_message(self) -> None:
        client = CapturingClient("This must not be visible.")
        core = AmadeusCore(llm_client=client, project_root=self.root)
        core.update_chat_metadata("main", response_mode="none")
        payload = core.handle_user_message("Process this")
        self.assertTrue(payload["suppress_visible_output"])
        self.assertEqual("", payload["response"])
        self.assertEqual(0, client.calls[0]["num_predict"])
        self.assertEqual(["User"], [message.speaker for message in core.load_chat_history()])

    def test_full_send_exposes_continuation_state_when_budget_is_reached(self) -> None:
        client = CapturingClient("x" * 48000)
        core = AmadeusCore(llm_client=client, project_root=self.root)
        core.update_chat_metadata("main", response_mode="full_send")
        payload = core.handle_user_message("Write the complete report")
        self.assertEqual(12000, client.calls[0]["num_predict"])
        self.assertTrue(payload["response_completion"]["limit_reached"])
        self.assertTrue(payload["response_completion"]["continuation_available"])

    def test_ollama_maps_num_predict_to_options(self) -> None:
        client = OllamaClient()
        captured: dict[str, object] = {}
        client._post_json = lambda _path, payload: captured.update(payload) or {"response": "ok"}  # type: ignore[method-assign]
        self.assertEqual("ok", client.generate("Prompt", num_predict=350))
        self.assertEqual(350, captured["options"]["num_predict"])  # type: ignore[index]

    def test_ollama_clamps_full_send_budget_to_remaining_context(self) -> None:
        client = OllamaClient()
        captured: dict[str, object] = {}
        client._post_json = lambda _path, payload: captured.update(payload) or {"response": "ok"}  # type: ignore[method-assign]
        client.generate("Prompt", system_prompt="System", num_predict=12000)
        self.assertLess(captured["options"]["num_predict"], 8192)  # type: ignore[index]


if __name__ == "__main__":
    unittest.main()
