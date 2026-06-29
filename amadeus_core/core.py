from amadeus_chat import AmadeusChatModule
from amadeus_core.module_registry import ModuleRegistry
from llm_client import OllamaClient


class AmadeusCore:
    """Lightweight coordinator for AMADEUS modules."""

    def __init__(self, llm_client: object | None = None) -> None:
        # Core owns coordination and routing. Modules own their own behavior.
        self.module_registry = ModuleRegistry()
        self.llm_client = llm_client or OllamaClient()
        self._register_builtin_modules()

    def _register_builtin_modules(self) -> None:
        """Register the first built-in modules needed by the shell."""
        self.module_registry.register("chat", AmadeusChatModule(llm_client=self.llm_client))

    def handle_user_message(self, message: str) -> str:
        """Route user text to the chat module and return the module response."""
        chat_module = self.module_registry.get("chat")
        if chat_module is None:
            return "AMADEUS error: chat module is not registered."

        # Core routes the message but does not generate the chat response itself.
        return chat_module.handle_message(message)  # type: ignore[attr-defined]
