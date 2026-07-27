"""Metadata-only registry for dedicated AMADEUS chats.

The registry deliberately depends on ``ChatHistoryStore.list_chats()`` alone.
Flow context can learn which dedicated chats exist without loading their message
bodies or depending on dedicated-chat storage internals.
"""

from dataclasses import dataclass

from storage import ChatHistoryStore, ChatPriority, ChatPurpose, ChatScope


@dataclass(frozen=True, slots=True)
class ChatMetadata:
    """The only dedicated-chat fields Flow Chat may receive."""

    chat_id: str
    title: str
    description: str
    priority: ChatPriority
    purpose: ChatPurpose
    scope: ChatScope


class ChatRegistry:
    """Project dedicated-chat metadata from an existing chat history store."""

    def __init__(self, chat_history_store: ChatHistoryStore) -> None:
        self._chat_history_store = chat_history_store

    def list_chat_metadata(self) -> list[ChatMetadata]:
        """Return current dedicated-chat metadata without loading message history."""
        return [
            ChatMetadata(
                chat_id=chat.chat_id,
                title=chat.title,
                description=chat.description,
                priority=chat.priority,
                purpose=chat.purpose,
                scope=chat.scope,
            )
            for chat in self._chat_history_store.list_chats()
        ]

    def get_chat_metadata(self, chat_id: str) -> ChatMetadata | None:
        """Return one current dedicated-chat metadata record when it exists."""
        for metadata in self.list_chat_metadata():
            if metadata.chat_id == chat_id:
                return metadata
        return None

    def get_relevant_chat_metadata(self) -> list[ChatMetadata]:
        """Return the lightweight metadata currently relevant to Flow context.

        V1 exposes all dedicated chats because only their small human-authored
        descriptors are available. Future relevance ranking belongs here, not in
        Flow storage or dedicated-chat message loading.
        """
        return self.list_chat_metadata()
