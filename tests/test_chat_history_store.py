"""Migration coverage for chat index analysis metadata."""

import json
import tempfile
import unittest
from pathlib import Path

from storage import ChatHistoryStore


class ChatHistoryStoreTests(unittest.TestCase):
    def test_old_index_rows_load_without_inner_brain_analysis(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            chats = root / "data" / "chats"
            chats.mkdir(parents=True)
            (chats / "chats_index.json").write_text(json.dumps({"current_chat_id": "old", "chats": [{
                "chat_id": "old", "title": "Old", "created_at": "now", "updated_at": "now"
            }]}), encoding="utf-8")
            store = ChatHistoryStore(root)

            self.assertIsNone(store.get_chat("old").inner_brain_analysis)


if __name__ == "__main__":
    unittest.main()
