"""SQLite persistence for the AMADEUS Mind Map / Relevance Graph."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable, Mapping
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from mindmap.models import GraphLink, GraphNode, SourceReference

MAX_RECENT_NODE_LIMIT = 100


class SQLiteMindMapRepository:
    """Store graph objects locally without requiring an external graph server.

    A fresh SQLite connection is opened per operation. This avoids cross-thread
    connection ownership problems when future background AMADEUS processes create
    graph objects while the PyQt GUI is open.
    """

    def __init__(self, project_root: Path, relative_path: str = "data/mindmap/mind_map.sqlite3") -> None:
        self.project_root = project_root.resolve()
        requested_path = Path(relative_path)
        if requested_path.is_absolute():
            raise ValueError("Mind map database path must be relative to the project root")
        self.database_path = (self.project_root / requested_path).resolve()
        try:
            self.database_path.relative_to(self.project_root)
        except ValueError as error:
            raise ValueError("Mind map database path must stay within the project root") from error
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize_schema()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.database_path, timeout=10.0)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 10000")
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _initialize_schema(self) -> None:
        with self._connect() as connection:
            connection.execute("PRAGMA journal_mode = WAL")
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS mindmap_meta (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );

                INSERT OR IGNORE INTO mindmap_meta(key, value) VALUES ('schema_version', '1');

                CREATE TABLE IF NOT EXISTS mindmap_nodes (
                    node_id TEXT PRIMARY KEY,
                    graph_id TEXT NOT NULL,
                    node_type TEXT NOT NULL,
                    title TEXT NOT NULL,
                    description TEXT NOT NULL DEFAULT '',
                    content TEXT NOT NULL DEFAULT '',
                    importance REAL NOT NULL DEFAULT 0.5,
                    confidence REAL NOT NULL DEFAULT 1.0,
                    status TEXT NOT NULL DEFAULT 'active',
                    position_x REAL NOT NULL DEFAULT 0.0,
                    position_y REAL NOT NULL DEFAULT 0.0,
                    position_locked INTEGER NOT NULL DEFAULT 0,
                    source_type TEXT NOT NULL DEFAULT '',
                    source_id TEXT NOT NULL DEFAULT '',
                    source_locator TEXT NOT NULL DEFAULT '',
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS mindmap_links (
                    link_id TEXT PRIMARY KEY,
                    graph_id TEXT NOT NULL,
                    source_node_id TEXT NOT NULL,
                    target_node_id TEXT NOT NULL,
                    link_type TEXT NOT NULL,
                    label TEXT NOT NULL DEFAULT '',
                    strength REAL NOT NULL DEFAULT 0.5,
                    confidence REAL NOT NULL DEFAULT 1.0,
                    permanence REAL NOT NULL DEFAULT 0.5,
                    usage_count INTEGER NOT NULL DEFAULT 0,
                    reward_score REAL NOT NULL DEFAULT 0.0,
                    punishment_score REAL NOT NULL DEFAULT 0.0,
                    evidence TEXT NOT NULL DEFAULT '',
                    is_temporary INTEGER NOT NULL DEFAULT 0,
                    expires_at TEXT NOT NULL DEFAULT '',
                    decay_rate REAL NOT NULL DEFAULT 0.0,
                    source_type TEXT NOT NULL DEFAULT '',
                    source_id TEXT NOT NULL DEFAULT '',
                    source_locator TEXT NOT NULL DEFAULT '',
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(source_node_id) REFERENCES mindmap_nodes(node_id) ON DELETE CASCADE,
                    FOREIGN KEY(target_node_id) REFERENCES mindmap_nodes(node_id) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_mindmap_nodes_graph
                    ON mindmap_nodes(graph_id);
                CREATE INDEX IF NOT EXISTS idx_mindmap_nodes_title
                    ON mindmap_nodes(graph_id, title);
                CREATE INDEX IF NOT EXISTS idx_mindmap_nodes_recent
                    ON mindmap_nodes(graph_id, updated_at DESC, node_id DESC);
                CREATE INDEX IF NOT EXISTS idx_mindmap_links_graph
                    ON mindmap_links(graph_id);
                CREATE INDEX IF NOT EXISTS idx_mindmap_links_source
                    ON mindmap_links(graph_id, source_node_id);
                CREATE INDEX IF NOT EXISTS idx_mindmap_links_target
                    ON mindmap_links(graph_id, target_node_id);
                CREATE UNIQUE INDEX IF NOT EXISTS idx_mindmap_node_source_unique
                    ON mindmap_nodes(graph_id, source_type, source_id)
                    WHERE source_type <> '' AND source_id <> '';
                """
            )

    def create_node(self, node: GraphNode) -> GraphNode:
        with self._connect() as connection:
            self._insert_node(connection, node)
        return node

    def _insert_node(self, connection: sqlite3.Connection, node: GraphNode) -> None:
        connection.execute(
                """
                INSERT INTO mindmap_nodes (
                    node_id, graph_id, node_type, title, description, content,
                    importance, confidence, status, position_x, position_y,
                    position_locked, source_type, source_id, source_locator,
                    metadata_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
            self._node_values(node),
        )

    def update_node(self, node: GraphNode) -> GraphNode:
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE mindmap_nodes SET
                    graph_id = ?, node_type = ?, title = ?, description = ?, content = ?,
                    importance = ?, confidence = ?, status = ?, position_x = ?, position_y = ?,
                    position_locked = ?, source_type = ?, source_id = ?, source_locator = ?,
                    metadata_json = ?, created_at = ?, updated_at = ?
                WHERE node_id = ?
                """,
                (*self._node_values(node)[1:], node.node_id),
            )
            if cursor.rowcount != 1:
                raise KeyError(f"Unknown mind map node: {node.node_id}")
        return node

    def update_node_positions(self, graph_id: str, positions: Mapping[str, tuple[float, float]]) -> None:
        """Persist all requested coordinates in one transaction."""
        if not positions:
            return
        with self._connect() as connection:
            for node_id, (position_x, position_y) in positions.items():
                cursor = connection.execute(
                    """
                    UPDATE mindmap_nodes
                    SET position_x = ?, position_y = ?, updated_at = ?
                    WHERE node_id = ? AND graph_id = ?
                    """,
                    (position_x, position_y, datetime.now(timezone.utc).isoformat(), node_id, graph_id),
                )
                if cursor.rowcount != 1:
                    raise KeyError(f"Unknown mind map node in graph '{graph_id}': {node_id}")

    def delete_node(self, node_id: str) -> None:
        with self._connect() as connection:
            cursor = connection.execute("DELETE FROM mindmap_nodes WHERE node_id = ?", (node_id,))
            if cursor.rowcount != 1:
                raise KeyError(f"Unknown mind map node: {node_id}")

    def get_node(self, node_id: str) -> GraphNode | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM mindmap_nodes WHERE node_id = ?", (node_id,)
            ).fetchone()
        return self._node_from_row(row) if row else None

    def find_node_by_source(self, graph_id: str, source_type: str, source_id: str) -> GraphNode | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT * FROM mindmap_nodes
                WHERE graph_id = ? AND source_type = ? AND source_id = ?
                """,
                (graph_id, source_type, source_id),
            ).fetchone()
        return self._node_from_row(row) if row else None

    def list_nodes(self, graph_id: str) -> list[GraphNode]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM mindmap_nodes WHERE graph_id = ? ORDER BY created_at, node_id",
                (graph_id,),
            ).fetchall()
        return [self._node_from_row(row) for row in rows]

    def list_recent_nodes(self, graph_id: str, limit: int) -> list[GraphNode]:
        """Return a bounded, newest-first node window for one graph."""
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= MAX_RECENT_NODE_LIMIT:
            raise ValueError(f"limit must be between 1 and {MAX_RECENT_NODE_LIMIT}")
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM mindmap_nodes
                WHERE graph_id = ?
                ORDER BY updated_at DESC, node_id DESC
                LIMIT ?
                """,
                (graph_id, limit),
            ).fetchall()
        return [self._node_from_row(row) for row in rows]

    def search_nodes(self, graph_id: str, query: str, limit: int = 50) -> list[GraphNode]:
        pattern = f"%{query.strip()}%"
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM mindmap_nodes
                WHERE graph_id = ? AND (
                    title LIKE ? COLLATE NOCASE OR
                    description LIKE ? COLLATE NOCASE OR
                    content LIKE ? COLLATE NOCASE OR
                    node_type LIKE ? COLLATE NOCASE
                )
                ORDER BY importance DESC, updated_at DESC
                LIMIT ?
                """,
                (graph_id, pattern, pattern, pattern, pattern, limit),
            ).fetchall()
        return [self._node_from_row(row) for row in rows]

    def create_link(self, link: GraphLink) -> GraphLink:
        with self._connect() as connection:
            self._insert_link(connection, link)
        return link

    def _insert_link(self, connection: sqlite3.Connection, link: GraphLink) -> None:
        connection.execute(
                """
                INSERT INTO mindmap_links (
                    link_id, graph_id, source_node_id, target_node_id, link_type,
                    label, strength, confidence, permanence, usage_count,
                    reward_score, punishment_score, evidence, is_temporary,
                    expires_at, decay_rate, source_type, source_id, source_locator,
                    metadata_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
            self._link_values(link),
        )

    def update_link(self, link: GraphLink) -> GraphLink:
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE mindmap_links SET
                    graph_id = ?, source_node_id = ?, target_node_id = ?, link_type = ?,
                    label = ?, strength = ?, confidence = ?, permanence = ?, usage_count = ?,
                    reward_score = ?, punishment_score = ?, evidence = ?, is_temporary = ?,
                    expires_at = ?, decay_rate = ?, source_type = ?, source_id = ?,
                    source_locator = ?, metadata_json = ?, created_at = ?, updated_at = ?
                WHERE link_id = ?
                """,
                (*self._link_values(link)[1:], link.link_id),
            )
            if cursor.rowcount != 1:
                raise KeyError(f"Unknown mind map link: {link.link_id}")
        return link

    def delete_link(self, link_id: str) -> None:
        with self._connect() as connection:
            cursor = connection.execute("DELETE FROM mindmap_links WHERE link_id = ?", (link_id,))
            if cursor.rowcount != 1:
                raise KeyError(f"Unknown mind map link: {link_id}")

    def get_link(self, link_id: str) -> GraphLink | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM mindmap_links WHERE link_id = ?", (link_id,)
            ).fetchone()
        return self._link_from_row(row) if row else None

    def list_links(self, graph_id: str) -> list[GraphLink]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM mindmap_links WHERE graph_id = ? ORDER BY created_at, link_id",
                (graph_id,),
            ).fetchall()
        return [self._link_from_row(row) for row in rows]

    def list_links_for_nodes(self, graph_id: str, node_ids: Iterable[str]) -> list[GraphLink]:
        unique_ids = tuple(dict.fromkeys(node_ids))
        if not unique_ids:
            return []
        placeholders = ",".join("?" for _ in unique_ids)
        parameters = (graph_id, *unique_ids, *unique_ids)
        with self._connect() as connection:
            rows = connection.execute(
                f"""
                SELECT * FROM mindmap_links
                WHERE graph_id = ? AND (
                    source_node_id IN ({placeholders}) OR target_node_id IN ({placeholders})
                )
                ORDER BY created_at, link_id
                """,
                parameters,
            ).fetchall()
        return [self._link_from_row(row) for row in rows]

    def clear_graph(self, graph_id: str) -> None:
        with self._connect() as connection:
            connection.execute("DELETE FROM mindmap_links WHERE graph_id = ?", (graph_id,))
            connection.execute("DELETE FROM mindmap_nodes WHERE graph_id = ?", (graph_id,))

    def import_graph(
        self,
        graph_id: str,
        nodes: Iterable[GraphNode],
        links: Iterable[GraphLink],
        *,
        replace_graph: bool,
    ) -> None:
        """Persist a validated import in one transaction, or leave the graph unchanged."""
        with self._connect() as connection:
            if replace_graph:
                connection.execute("DELETE FROM mindmap_links WHERE graph_id = ?", (graph_id,))
                connection.execute("DELETE FROM mindmap_nodes WHERE graph_id = ?", (graph_id,))
            for node in nodes:
                self._insert_node(connection, node)
            for link in links:
                self._insert_link(connection, link)

    def _node_values(self, node: GraphNode) -> tuple[object, ...]:
        source_type, source_id, source_locator = self._source_values(node.source_reference)
        return (
            node.node_id,
            node.graph_id,
            node.node_type,
            node.title,
            node.description,
            node.content,
            node.importance,
            node.confidence,
            node.status,
            node.position_x,
            node.position_y,
            int(node.position_locked),
            source_type,
            source_id,
            source_locator,
            self._dump_metadata(node.metadata),
            node.created_at,
            node.updated_at,
        )

    def _link_values(self, link: GraphLink) -> tuple[object, ...]:
        source_type, source_id, source_locator = self._source_values(link.source_reference)
        return (
            link.link_id,
            link.graph_id,
            link.source_node_id,
            link.target_node_id,
            link.link_type,
            link.label,
            link.strength,
            link.confidence,
            link.permanence,
            link.usage_count,
            link.reward_score,
            link.punishment_score,
            link.evidence,
            int(link.is_temporary),
            link.expires_at,
            link.decay_rate,
            source_type,
            source_id,
            source_locator,
            self._dump_metadata(link.metadata),
            link.created_at,
            link.updated_at,
        )

    def _node_from_row(self, row: sqlite3.Row) -> GraphNode:
        return GraphNode(
            node_id=row["node_id"],
            graph_id=row["graph_id"],
            node_type=row["node_type"],
            title=row["title"],
            description=row["description"],
            content=row["content"],
            importance=float(row["importance"]),
            confidence=float(row["confidence"]),
            status=row["status"],
            position_x=float(row["position_x"]),
            position_y=float(row["position_y"]),
            position_locked=bool(row["position_locked"]),
            source_reference=self._source_from_row(row),
            metadata=self._load_metadata(row["metadata_json"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def _link_from_row(self, row: sqlite3.Row) -> GraphLink:
        return GraphLink(
            link_id=row["link_id"],
            graph_id=row["graph_id"],
            source_node_id=row["source_node_id"],
            target_node_id=row["target_node_id"],
            link_type=row["link_type"],
            label=row["label"],
            strength=float(row["strength"]),
            confidence=float(row["confidence"]),
            permanence=float(row["permanence"]),
            usage_count=int(row["usage_count"]),
            reward_score=float(row["reward_score"]),
            punishment_score=float(row["punishment_score"]),
            evidence=row["evidence"],
            is_temporary=bool(row["is_temporary"]),
            expires_at=row["expires_at"],
            decay_rate=float(row["decay_rate"]),
            source_reference=self._source_from_row(row),
            metadata=self._load_metadata(row["metadata_json"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def _source_values(self, source: SourceReference | None) -> tuple[str, str, str]:
        if source is None:
            return "", "", ""
        return source.source_type, source.source_id, source.source_locator

    def _source_from_row(self, row: sqlite3.Row) -> SourceReference | None:
        if not row["source_type"] or not row["source_id"]:
            return None
        return SourceReference(
            source_type=row["source_type"],
            source_id=row["source_id"],
            source_locator=row["source_locator"],
        )

    def _dump_metadata(self, metadata: Mapping[str, Any]) -> str:
        try:
            return json.dumps(dict(metadata), ensure_ascii=False, sort_keys=True)
        except (TypeError, ValueError) as error:
            raise ValueError("Mind map metadata must be JSON serializable") from error

    def _load_metadata(self, raw_metadata: str) -> dict[str, Any]:
        try:
            value = json.loads(raw_metadata)
        except (TypeError, json.JSONDecodeError):
            return {}
        return value if isinstance(value, dict) else {}
