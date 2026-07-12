"""Prompt-strength selector for AMADEUS identity.

The full charter is long, so Chat normally receives a compact identity prompt. When
Dato asks about AMADEUS project files/modules, this builder chooses the stronger
project identity prompt.
"""

from identity_module.identity_service import IdentityService


class IdentityPromptBuilder:
    """Chooses how strongly AMADEUS identity should be injected."""

    NORMAL_MODE = "normal"
    PROJECT_MODE = "project"

    def __init__(self, identity_service: IdentityService) -> None:
        self.identity_service = identity_service

    def build_for_chat(self, *, project_context_active: bool = False) -> str:
        """Return the identity prompt appropriate for the current chat context."""
        # Project context means the conversation is probably about AMADEUS herself, so the
        # stronger project identity prompt is appropriate. Otherwise keep the prompt lighter.
        if project_context_active:
            return self.identity_service.build_project_prompt()

        return self.identity_service.build_compact_prompt()
