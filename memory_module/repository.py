"""SQLite repository for structured memory metadata and derived-layer state."""

import hashlib
import json
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from memory_module.models import KNOWLEDGE_LAYER_NAMES, KnowledgeLayer, KnowledgeSource, MemoryBrick


class SQLiteMemoryRepository:
    """Own structured Memory Module data while retaining legacy JSONL separately."""

    def __init__(self, project_root: Path, relative_path: str = "data/memory/memory.sqlite") -> None:
        root = project_root.resolve()
        database_path = (root / relative_path).resolve()
        if root not in database_path.parents:
            raise ValueError("Memory database path must remain inside the project root.")
        database_path.parent.mkdir(parents=True, exist_ok=True)
        self.database_path = database_path
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with closing(self._connect()) as connection, connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS memory_bricks (
                    memory_id TEXT PRIMARY KEY, content TEXT NOT NULL,
                    scope_level TEXT NOT NULL, scope_ref TEXT,
                    evidence_json TEXT NOT NULL, importance REAL NOT NULL,
                    confidence REAL NOT NULL, creation_source TEXT NOT NULL,
                    extra_json TEXT NOT NULL, created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL, status TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS memory_brick_labels (
                    memory_id TEXT NOT NULL REFERENCES memory_bricks(memory_id) ON DELETE CASCADE,
                    label_type TEXT NOT NULL, label TEXT NOT NULL,
                    PRIMARY KEY (memory_id, label_type, label)
                );
                CREATE INDEX IF NOT EXISTS memory_labels_lookup
                    ON memory_brick_labels(label_type, label, memory_id);
                CREATE TABLE IF NOT EXISTS knowledge_sources (
                    source_id TEXT PRIMARY KEY, source_type TEXT NOT NULL,
                    owner_module TEXT NOT NULL, title TEXT NOT NULL,
                    raw_locator TEXT NOT NULL, content_hash TEXT,
                    created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                    raw_content TEXT NOT NULL DEFAULT '', metadata_json TEXT NOT NULL DEFAULT '{}',
                    categorization_json TEXT NOT NULL DEFAULT '{}'
                );
                CREATE TABLE IF NOT EXISTS knowledge_layers (
                    source_id TEXT NOT NULL REFERENCES knowledge_sources(source_id) ON DELETE CASCADE,
                    layer_name TEXT NOT NULL, source_hash TEXT,
                    status TEXT NOT NULL, updated_at TEXT NOT NULL,
                    PRIMARY KEY (source_id, layer_name)
                );
                CREATE TABLE IF NOT EXISTS creation_placeholders (
                    placeholder_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_id TEXT NOT NULL, layer_name TEXT NOT NULL,
                    status TEXT NOT NULL, created_at TEXT NOT NULL,
                    UNIQUE(source_id, layer_name)
                );
                """
            )
            self._ensure_source_columns(connection)
            try:
                connection.execute("CREATE VIRTUAL TABLE IF NOT EXISTS memory_bricks_fts USING fts5(memory_id UNINDEXED, content)")
            except sqlite3.OperationalError:
                pass

    def upsert_brick(self, brick: MemoryBrick) -> MemoryBrick:
        """Insert or replace one brick and its multi-value labels atomically."""
        with closing(self._connect()) as connection, connection:
            connection.execute(
                """INSERT INTO memory_bricks VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(memory_id) DO UPDATE SET content=excluded.content, scope_level=excluded.scope_level,
                scope_ref=excluded.scope_ref, evidence_json=excluded.evidence_json, importance=excluded.importance,
                confidence=excluded.confidence, creation_source=excluded.creation_source, extra_json=excluded.extra_json,
                updated_at=excluded.updated_at, status=excluded.status""",
                self._brick_values(brick),
            )
            connection.execute("DELETE FROM memory_brick_labels WHERE memory_id = ?", (brick.memory_id,))
            for label_type, labels in (("domain", brick.domains), ("kind", brick.kinds), ("category", brick.categories)):
                connection.executemany(
                    "INSERT OR IGNORE INTO memory_brick_labels(memory_id, label_type, label) VALUES (?, ?, ?)",
                    [(brick.memory_id, label_type, label) for label in labels],
                )
            try:
                connection.execute("DELETE FROM memory_bricks_fts WHERE memory_id = ?", (brick.memory_id,))
                connection.execute("INSERT INTO memory_bricks_fts(memory_id, content) VALUES (?, ?)", (brick.memory_id, brick.content))
            except sqlite3.OperationalError:
                pass
        return brick

    def get_brick(self, memory_id: str) -> MemoryBrick | None:
        with closing(self._connect()) as connection, connection:
            row = connection.execute("SELECT * FROM memory_bricks WHERE memory_id = ?", (memory_id,)).fetchone()
            return self._row_to_brick(connection, row) if row else None

    def search_bricks(
        self, query: str = "", *, domains: Iterable[str] = (), kinds: Iterable[str] = (),
        categories: Iterable[str] = (), scope_level: str | None = None, scope_ref: str | None = None,
        limit: int = 20,
    ) -> list[MemoryBrick]:
        """Search structured bricks with FTS when available and LIKE otherwise."""
        filters, parameters = ["b.status = 'active'"], []
        if scope_level:
            filters.append("b.scope_level = ?")
            parameters.append(scope_level)
        if scope_ref:
            filters.append("b.scope_ref = ?")
            parameters.append(scope_ref)
        for label_type, labels in (("domain", domains), ("kind", kinds), ("category", categories)):
            for label in self._clean_labels(labels):
                filters.append("EXISTS (SELECT 1 FROM memory_brick_labels l WHERE l.memory_id = b.memory_id AND l.label_type = ? AND l.label = ?)")
                parameters.extend((label_type, label))
        clean_query = query.strip()
        with closing(self._connect()) as connection, connection:
            rows: list[sqlite3.Row]
            if clean_query:
                try:
                    rows = connection.execute(
                        "SELECT b.* FROM memory_bricks b JOIN memory_bricks_fts f ON f.memory_id = b.memory_id "
                        f"WHERE f.content MATCH ? AND {' AND '.join(filters)} ORDER BY bm25(f), b.updated_at DESC LIMIT ?",
                        [clean_query, *parameters, max(1, limit)],
                    ).fetchall()
                except sqlite3.OperationalError:
                    rows = connection.execute(
                        f"SELECT b.* FROM memory_bricks b WHERE b.content LIKE ? ESCAPE '\\' AND {' AND '.join(filters)} ORDER BY b.updated_at DESC LIMIT ?",
                        [f"%{self._escape_like(clean_query)}%", *parameters, max(1, limit)],
                    ).fetchall()
            else:
                rows = connection.execute(
                    f"SELECT b.* FROM memory_bricks b WHERE {' AND '.join(filters)} ORDER BY b.updated_at DESC LIMIT ?",
                    [*parameters, max(1, limit)],
                ).fetchall()
            return [self._row_to_brick(connection, row) for row in rows]

    def register_source(self, source: KnowledgeSource) -> KnowledgeSource:
        """Register a locator and create all pending derived-layer placeholders."""
        with closing(self._connect()) as connection, connection:
            connection.execute(
                """INSERT INTO knowledge_sources
                (source_id, source_type, owner_module, title, raw_locator, content_hash, created_at, updated_at, raw_content, metadata_json, categorization_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(source_id) DO UPDATE SET source_type=excluded.source_type, owner_module=excluded.owner_module,
                title=excluded.title, raw_locator=excluded.raw_locator, content_hash=excluded.content_hash, updated_at=excluded.updated_at,
                raw_content=excluded.raw_content""",
                (source.source_id, source.source_type, source.owner_module, source.title, source.raw_locator,
                 source.content_hash, source.created_at, source.updated_at, source.raw_content,
                 json.dumps(source.metadata, sort_keys=True), json.dumps(source.categorization, sort_keys=True)),
            )
            for layer_name in KNOWLEDGE_LAYER_NAMES:
                connection.execute(
                    "INSERT OR IGNORE INTO knowledge_layers VALUES (?, ?, ?, 'pending', ?)",
                    (source.source_id, layer_name, source.content_hash, source.updated_at),
                )
                connection.execute(
                    "INSERT OR IGNORE INTO creation_placeholders(source_id, layer_name, status, created_at) VALUES (?, ?, 'pending', ?)",
                    (source.source_id, layer_name, source.created_at),
                )
        return source

    def get_source(self, source_id: str) -> KnowledgeSource | None:
        """Return a registered source and its stored derived metadata."""
        with closing(self._connect()) as connection, connection:
            row = connection.execute("SELECT * FROM knowledge_sources WHERE source_id = ?", (source_id,)).fetchone()
            if row is None:
                return None
            values = dict(row)
            values["metadata"] = json.loads(values.pop("metadata_json", "{}"))
            values["categorization"] = json.loads(values.pop("categorization_json", "{}"))
            return KnowledgeSource(**values)

    def update_source_derivatives(self, source: KnowledgeSource, *, expected_hash: str) -> KnowledgeSource:
        """Write derived fields only when registered raw content remains unchanged."""
        with closing(self._connect()) as connection, connection:
            row = connection.execute("SELECT raw_content FROM knowledge_sources WHERE source_id = ?", (source.source_id,)).fetchone()
            current_hash = hashlib.sha256(row["raw_content"].encode("utf-8")).hexdigest() if row else None
            if current_hash != expected_hash:
                raise ValueError("Knowledge source changed during update.")
            connection.execute("UPDATE knowledge_sources SET metadata_json = ?, categorization_json = ?, updated_at = ? WHERE source_id = ?", (json.dumps(source.metadata, sort_keys=True), json.dumps(source.categorization, sort_keys=True), source.updated_at, source.source_id))
        return source

    def list_layers(self, source_id: str) -> list[KnowledgeLayer]:
        with closing(self._connect()) as connection, connection:
            return [KnowledgeLayer(**dict(row)) for row in connection.execute(
                "SELECT source_id, layer_name, source_hash, status, updated_at FROM knowledge_layers WHERE source_id = ? ORDER BY layer_name", (source_id,)
            )]

    def stale_layers(self, source_id: str, current_hash: str | None) -> list[KnowledgeLayer]:
        """Mark layers stale if a known source hash no longer matches their input."""
        if current_hash is None:
            return []
        now = self._now()
        with closing(self._connect()) as connection, connection:
            connection.execute(
                "UPDATE knowledge_sources SET content_hash = ?, updated_at = ? WHERE source_id = ?",
                (current_hash, now, source_id),
            )
            connection.execute(
                "UPDATE knowledge_layers SET status = 'stale', updated_at = ? WHERE source_id = ? AND source_hash IS NOT ?",
                (now, source_id, current_hash),
            )
        return self.list_layers(source_id)

    @staticmethod
    def _brick_values(brick: MemoryBrick) -> tuple[Any, ...]:
        return (brick.memory_id, brick.content, brick.scope_level, brick.scope_ref, json.dumps(brick.evidence, sort_keys=True),
                brick.importance, brick.confidence, brick.creation_source, json.dumps(brick.extra, sort_keys=True),
                brick.created_at, brick.updated_at, brick.status)

    def _row_to_brick(self, connection: sqlite3.Connection, row: sqlite3.Row) -> MemoryBrick:
        labels = connection.execute("SELECT label_type, label FROM memory_brick_labels WHERE memory_id = ? ORDER BY label", (row["memory_id"],)).fetchall()
        grouped = {name: tuple(label["label"] for label in labels if label["label_type"] == name) for name in ("domain", "kind", "category")}
        return MemoryBrick(row["memory_id"], row["content"], grouped["domain"], grouped["kind"], grouped["category"], row["scope_level"], row["scope_ref"], json.loads(row["evidence_json"]), row["importance"], row["confidence"], row["creation_source"], json.loads(row["extra_json"]), row["created_at"], row["updated_at"], row["status"])

    @staticmethod
    def _clean_labels(labels: Iterable[str]) -> tuple[str, ...]:
        return tuple(dict.fromkeys(str(label).strip() for label in labels if str(label).strip()))

    @staticmethod
    def _escape_like(query: str) -> str:
        return query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _ensure_source_columns(connection: sqlite3.Connection) -> None:
        """Migrate pre-Creation V1 source records in the existing Memory database."""
        existing = {row[1] for row in connection.execute("PRAGMA table_info(knowledge_sources)")}
        for name, definition in (("raw_content", "TEXT NOT NULL DEFAULT ''"), ("metadata_json", "TEXT NOT NULL DEFAULT '{}'"), ("categorization_json", "TEXT NOT NULL DEFAULT '{}'")):
            if name not in existing:
                connection.execute(f"ALTER TABLE knowledge_sources ADD COLUMN {name} {definition}")
