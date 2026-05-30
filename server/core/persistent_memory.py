from __future__ import annotations
import sqlite3
import threading
from pathlib import Path
from datetime import datetime
from utils.logger import get_logger

logger = get_logger("persistent_memory")

import sys as _sys
def _resolve_db_path() -> Path:
    if getattr(_sys, "frozen", False):
        return Path(_sys.executable).parent / "data" / "jarvis_memory.db"
    return Path(__file__).parent.parent / "data" / "jarvis_memory.db"
_DB_PATH = _resolve_db_path()
_instance: "PersistentMemory | None" = None


def get_memory() -> "PersistentMemory":
    global _instance
    if _instance is None:
        _instance = PersistentMemory()
    return _instance


class PersistentMemory:
    """SQLite-backed persistent memory — JARVIS remembers across sessions."""

    def __init__(self) -> None:
        _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(_DB_PATH), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_db()
        logger.info(f"Mémoire persistante initialisée: {_DB_PATH}")

    def _init_db(self) -> None:
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key TEXT NOT NULL,
                value TEXT NOT NULL,
                category TEXT NOT NULL DEFAULT 'general',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(key)
            );
            CREATE TABLE IF NOT EXISTS episodes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                summary TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_memories_category ON memories(category);
            CREATE INDEX IF NOT EXISTS idx_memories_updated ON memories(updated_at DESC);
        """)
        self._conn.commit()

    def save(self, key: str, value: str, category: str = "general") -> str:
        now = datetime.utcnow().isoformat()
        with self._lock:
            self._conn.execute(
                """INSERT INTO memories(key, value, category, created_at, updated_at)
                   VALUES(?, ?, ?, ?, ?)
                   ON CONFLICT(key) DO UPDATE SET
                     value=excluded.value,
                     category=excluded.category,
                     updated_at=excluded.updated_at""",
                (key.strip(), value.strip(), category.strip(), now, now),
            )
            self._conn.commit()
        logger.info(f"Mémoire sauvée: [{category}] {key}")
        return f"✓ Mémorisé: {key} = {value}"

    def recall(self, query: str) -> str:
        with self._lock:
            rows = self._conn.execute(
                """SELECT key, value, category FROM memories
                   WHERE key LIKE ? OR value LIKE ?
                   ORDER BY updated_at DESC LIMIT 10""",
                (f"%{query}%", f"%{query}%"),
            ).fetchall()
        if not rows:
            return f"Aucun souvenir trouvé pour: {query}"
        return "\n".join(f"[{r['category']}] {r['key']}: {r['value']}" for r in rows)

    def list_all(self, category: str = "") -> str:
        with self._lock:
            if category:
                rows = self._conn.execute(
                    "SELECT key, value, category FROM memories WHERE category=? ORDER BY updated_at DESC",
                    (category,),
                ).fetchall()
            else:
                rows = self._conn.execute(
                    "SELECT key, value, category FROM memories ORDER BY category, updated_at DESC"
                ).fetchall()
        if not rows:
            return "Aucun souvenir enregistré pour le moment."
        return "\n".join(f"[{r['category']}] {r['key']}: {r['value']}" for r in rows)

    def count(self) -> int:
        with self._lock:
            return self._conn.execute("SELECT COUNT(*) FROM memories").fetchone()[0]

    def add_episode(self, summary: str) -> None:
        now = datetime.utcnow().isoformat()
        with self._lock:
            self._conn.execute(
                "INSERT INTO episodes(summary, created_at) VALUES(?, ?)", (summary, now)
            )
            self._conn.commit()

    def get_context_summary(self) -> str:
        """Returns formatted memories for injection into the system prompt."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT key, value, category FROM memories ORDER BY updated_at DESC LIMIT 25"
            ).fetchall()
        if not rows:
            return ""
        lines = ["\n\n## CE QUE JARVIS SAIT SUR MONSIEUR (mémoire persistante)\n"]
        for r in rows:
            lines.append(f"- [{r['category']}] {r['key']}: {r['value']}")
        return "\n".join(lines)
