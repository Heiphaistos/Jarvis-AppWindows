from __future__ import annotations
import re
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

# Toujours rappelées, quelle que soit la demande.
_CORE_CATEGORIES = {"identite", "preferences"}


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
            CREATE TABLE IF NOT EXISTS lessons (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                context TEXT NOT NULL,
                lesson TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
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

    def record_lesson(self, context: str, lesson: str) -> None:
        """Journal des leçons apprises — alimenté par la boucle agent sur échec outil."""
        now = datetime.utcnow().isoformat()
        with self._lock:
            # Dédoublonne : même leçon déjà connue → rafraîchit la date
            row = self._conn.execute(
                "SELECT id FROM lessons WHERE lesson = ?", (lesson.strip(),)
            ).fetchone()
            if row:
                self._conn.execute(
                    "UPDATE lessons SET created_at = ? WHERE id = ?", (now, row["id"])
                )
            else:
                self._conn.execute(
                    "INSERT INTO lessons(context, lesson, created_at) VALUES(?, ?, ?)",
                    (context.strip()[:200], lesson.strip()[:300], now),
                )
            self._conn.commit()
        logger.info(f"Leçon enregistrée: {lesson[:80]}")

    def get_lessons_summary(self, limit: int = 8) -> str:
        """Dernières leçons pour injection dans le system prompt."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT lesson FROM lessons ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
        if not rows:
            return ""
        lines = ["\n\n## LEÇONS APPRISES (erreurs passées à ne pas répéter)\n"]
        lines += [f"- {r['lesson']}" for r in rows]
        return "\n".join(lines)

    def lessons(self, limit: int = 50) -> list[dict]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT id, lesson, created_at FROM lessons ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(r) for r in rows]

    def forget_lesson(self, lesson_id: int) -> bool:
        with self._lock:
            cur = self._conn.execute("DELETE FROM lessons WHERE id = ?", (lesson_id,))
            self._conn.commit()
        return bool(cur.rowcount)

    def add_episode(self, summary: str) -> None:
        now = datetime.utcnow().isoformat()
        with self._lock:
            self._conn.execute(
                "INSERT INTO episodes(summary, created_at) VALUES(?, ?)", (summary, now)
            )
            self._conn.commit()

    def forget(self, key: str) -> bool:
        """Supprime un souvenir par clé exacte. True si quelque chose a été oublié."""
        with self._lock:
            cur = self._conn.execute("DELETE FROM memories WHERE key = ?", (key.strip(),))
            self._conn.commit()
        if cur.rowcount:
            logger.info(f"Souvenir oublié: {key}")
        return bool(cur.rowcount)

    def facts(self) -> list[dict]:
        """Tous les souvenirs (clé, valeur, catégorie), du plus récent au plus ancien."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT key, value, category, updated_at FROM memories ORDER BY updated_at DESC"
            ).fetchall()
        return [dict(r) for r in rows]

    def get_setting(self, key: str, default: str = "") -> str:
        with self._lock:
            row = self._conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else default

    def set_setting(self, key: str, value: str) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO settings(key, value) VALUES(?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, value),
            )
            self._conn.commit()

    def get_context_summary(self, query: str = "", limit: int = 30) -> str:
        """Souvenirs à injecter dans le system prompt.

        L'identité et les préférences passent toujours ; le reste est trié par
        pertinence avec la demande (mots communs), puis par fraîcheur.
        """
        rows = self.facts()
        if not rows:
            return ""
        words = {w for w in re.findall(r"[a-zà-ÿ0-9]{4,}", (query or "").lower())}

        def score(r: dict) -> int:
            s = 0
            if r["category"] in _CORE_CATEGORIES:
                s += 100
            if words:
                text = f"{r['key']} {r['value']}".lower()
                s += 10 * sum(1 for w in words if w in text)
            return s

        # sorted est stable : à score égal, l'ordre de fraîcheur est conservé.
        chosen = sorted(rows, key=score, reverse=True)[:limit]
        lines = ["\n\n## CE QUE JARVIS SAIT SUR MONSIEUR (mémoire persistante)\n"]
        for r in chosen:
            lines.append(f"- [{r['category']}] {r['key']}: {r['value']}")
        return "\n".join(lines)
