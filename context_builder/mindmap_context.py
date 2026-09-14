"""Format bounded, literal graph records for an explicitly selected context."""

from __future__ import annotations
from typing import Any

def format_mindmap_context(
    nodes: list[Any],
    *,
    links: list[Any] | None = None,
    seed_node_ids: tuple[str, ...] = (),
) -> str:
    """Format explicit node fields plus retrieved graph relationships."""
    if not nodes:
        return (
            "[AMADEUS MIND MAP RETRIEVAL]\n"
            "No matching Mind Map nodes were retrieved. Use this explicit no-context result as the source for this request."
        )

    seed_set = set(seed_node_ids)
    title_by_id = {node.node_id: node.title for node in nodes}
    records = []
    for node in nodes:
        source_reference = getattr(node, "source_reference", None)
        source = "manual"
        if source_reference is not None:
            source = f"{source_reference.source_type}:{source_reference.source_id}"
            if source_reference.source_locator:
                source += f" ({source_reference.source_locator})"
        role = "seed result" if node.node_id in seed_set else "connected context"
        records.append(
            "\n".join((
                "--- RETRIEVED NODE ---",
                f"Node ID: {node.node_id}",
                f"Retrieval role: {role}",
                f"Title (literal): {node.title}",
                f"Node type (literal): {node.node_type}",
                f"Description (literal): {node.description or '<empty>'}",
                "Content (literal, between markers):",
                "<<<CONTENT",
                node.content or "<empty>",
                "CONTENT",
                f"Source: {source}",
                f"Safe metadata: importance={node.importance}, confidence={node.confidence}, status={node.status}",
                "--- END RETRIEVED NODE ---",
            ))
        )

    relationship_records = []
    for link in links or []:
        source_title = title_by_id.get(link.source_node_id, link.source_node_id)
        target_title = title_by_id.get(link.target_node_id, link.target_node_id)
        relationship_records.append(
            "\n".join((
                f"{source_title} --{link.link_type}--> {target_title}",
                f"Link ID: {link.link_id}",
                f"Strength: {link.strength} | Confidence: {link.confidence} | Permanence: {link.permanence}",
                f"Evidence: {link.evidence or 'none stored'}",
            ))
        )

    context = (
        "[AMADEUS MIND MAP RETRIEVAL]\n"
        "The following bounded records were retrieved from AMADEUS Mind Map.\n"
        "Grounding rules:\n"
        "- Every title, type, description, content value, ID, and relationship below is literal.\n"
        "- Never invent missing labels, categories, node numbers, relationships, or content.\n"
        "- Do not rename nodes and do not call a node memory unless its literal type is memory.\n"
        "- When asked what is written, use only the literal Description and Content fields.\n"
        "- If a field says <empty>, report it as empty.\n"
        "- These retrieved records override older assistant guesses about the same nodes.\n\n"
        + "\n\n".join(records)
    )
    if relationship_records:
        context += (
            "\n\n=== RETRIEVED RELATIONSHIPS ===\n\n"
            + "\n\n--- LINK ---\n\n".join(relationship_records)
        )
    return context
