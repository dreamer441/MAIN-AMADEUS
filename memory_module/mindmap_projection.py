"""Build safe source-backed Mind Map metadata for structured memory bricks."""

from typing import Any

from memory_module.models import MemoryBrick


def memory_brick_projection(brick: MemoryBrick) -> dict[str, Any]:
    """Return a Mind Map-compatible source reference without owning graph storage."""
    return {
        "source_module": "memory_module",
        "source_id": brick.memory_id,
        "node_type": "memory",
        "source_type": "memory",
        "source_locator": brick.scope_ref or "",
        "metadata": {
            "memory_scope": brick.scope_level,
            "domains": list(brick.domains),
            "kinds": list(brick.kinds),
            "categories": list(brick.categories),
            "workspace_backed": True,
        },
    }
