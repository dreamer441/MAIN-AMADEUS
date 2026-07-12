"""Prompt helpers for AMADEUS Side Ask.

Side Ask is a lightweight secondary question flow. It can use selected chat text
as temporary context, but it does not save anything to the main chat unless Dato
presses Save to Chat or creates a new chat from the answer.
"""

from __future__ import annotations


class SideAskService:
    """Builds clean context blocks for side questions."""

    def build_callable_context(self, selected_text: str = "") -> str:
        """Return temporary Side Ask context for one request.

        The context may come from selected visible chat text, the manual Side Ask
        context box, or both. The block is intentionally explicit so the model
        does not treat it as permanent memory or hidden thinking.
        """
        clean_selected = selected_text.strip()
        if not clean_selected:
            return (
                "SIDE ASK CONTEXT:\n"
                "No temporary side context was provided. Answer the side question normally using available active context."
            )
        return (
            "SIDE ASK TEMPORARY CONTEXT:\n"
            "The following visible/pasted text was provided by Dato for this Side Ask only. Use it as temporary context.\n\n"
            f"{clean_selected}"
        )

    def build_chat_save_text(self, question: str, answer: str, selected_text: str = "") -> tuple[str, str]:
        """Format a side ask Q&A pair for insertion into the main chat history."""
        user_text = f"Side Ask: {question.strip()}"
        if selected_text.strip():
            user_text += "\n\nSide Ask temporary context:\n" + selected_text.strip()
        assistant_text = f"Side Ask Answer:\n{answer.strip()}"
        return user_text, assistant_text
