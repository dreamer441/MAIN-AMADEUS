from identity_module.identity_service import IdentityService


class IdentityPromptBuilder:
    """Chooses how strongly AMADEUS identity should be injected."""

    NORMAL_MODE = "normal"
    PROJECT_MODE = "project"

    def __init__(self, identity_service: IdentityService) -> None:
        self.identity_service = identity_service

    def build_for_chat(self, *, project_context_active: bool = False) -> str:
        """Return the identity prompt appropriate for the current chat context."""
        if project_context_active:
            return self.identity_service.build_project_prompt()

        return self.identity_service.build_compact_prompt()
