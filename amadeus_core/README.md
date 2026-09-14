# AMADEUS Core

Core exposes the stable `AmadeusCore` entry point, resolves registered modules and
forwards explicit public requests. Feature execution is owned elsewhere.

| File | Responsibility |
|---|---|
| `core.py` | Stable public class |
| `core_coordinator.py` | Existing public API as owner forwarding methods |
| `module_registry.py` | Named registration, optional lookup and required lookup |
| `module_routes.py` | Explicit Canvas and Habit routes used by module views |
| `pending_actions.py` | Compatibility export from Permissions |
| `creation_workspace_adapter.py` | Compatibility export from Workspace Integration |

Application setup lives in `amadeus_app`. Chat execution lives in `chat_workspace`;
Flow and Canvas own their request handlers. Core contains no prompts, annotation
parsing, metadata generation, exchange writes or approval-policy implementation.
Constructor model/root injection remains supported; registry injection allows
routing tests without constructing storage or importing Qt.

Existing service accessors remain for compatibility. New GUI operations use Core
methods or `core.canvas` / `core.habits`. No arbitrary attribute-based command
routing is exposed. See `docs/ARCHITECTURE.md` for the complete map.
