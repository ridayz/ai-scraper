"""
AI API Scraper - Database layer
"""
import aiosqlite
import os
from typing import List, Optional
from dataclasses import dataclass, asdict

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "ai_apis.db")

CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS ai_apis (
    id TEXT PRIMARY KEY,
    model_name TEXT NOT NULL,
    endpoint TEXT NOT NULL,
    api_key_type TEXT NOT NULL,
    source TEXT NOT NULL,
    response_time REAL,
    alive INTEGER,
    last_checked TEXT,
    speed_label TEXT,
    death_count INTEGER DEFAULT 0,
    context_length INTEGER DEFAULT 0,
    modality TEXT DEFAULT 'text',
    benchmark_score REAL DEFAULT 0,
    is_smart INTEGER DEFAULT 0
);
"""

CREATE_INDEX_ALIVE = "CREATE INDEX IF NOT EXISTS idx_alive ON ai_apis(alive);"
CREATE_INDEX_SOURCE = "CREATE INDEX IF NOT EXISTS idx_source ON ai_apis(source);"


@dataclass
class AIApiEntry:
    id: str
    modelName: str
    endpoint: str
    apiKey: str
    source: str
    responseTime: Optional[float]
    alive: Optional[bool]
    lastChecked: str
    speedLabel: str
    deathCount: int = 0
    contextLength: int = 0
    modality: str = "text"
    benchmarkScore: float = 0.0
    isSmart: bool = False

    def to_dict(self):
        return {
            "id": self.id,
            "modelName": self.modelName,
            "endpoint": self.endpoint,
            "apiKey": self.apiKey,
            "source": self.source,
            "responseTime": self.responseTime,
            "alive": self.alive,
            "lastChecked": self.lastChecked,
            "speedLabel": self.speedLabel,
            "deathCount": self.deathCount,
            "contextLength": self.contextLength,
            "modality": self.modality,
            "benchmarkScore": self.benchmarkScore,
            "isSmart": self.isSmart,
        }


class Database:
    def __init__(self):
        self.db_path = DB_PATH

    async def init_db(self):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(CREATE_TABLE)
            await db.execute(CREATE_INDEX_ALIVE)
            await db.execute(CREATE_INDEX_SOURCE)
            await db.commit()

    async def seed_endpoints(self, endpoints: List[dict]):
        """Insert or update seed endpoints."""
        async with aiosqlite.connect(self.db_path) as db:
            for ep in endpoints:
                await db.execute(
                    """
                    INSERT INTO ai_apis (id, model_name, endpoint, api_key_type, source, alive, last_checked, speed_label, death_count)
                    VALUES (?, ?, ?, ?, ?, NULL, '', '', 0)
                    ON CONFLICT(id) DO NOTHING
                    """,
                    (ep["id"], ep["modelName"], ep["endpoint"], ep["apiKey"], ep["source"]),
                )
            await db.commit()

    async def get_all(self) -> List[AIApiEntry]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM ai_apis ORDER BY alive DESC, is_smart DESC, benchmark_score DESC, model_name") as cursor:
                rows = await cursor.fetchall()
                return [self._row_to_entry(row) for row in rows]

    async def get_smart_free_alive(self) -> List[AIApiEntry]:
        """Get alive, free, smart-ranked models sorted by quality."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                """SELECT * FROM ai_apis
                   WHERE alive = 1 AND api_key_type = 'free'
                   ORDER BY benchmark_score DESC, response_time ASC"""
            ) as cursor:
                rows = await cursor.fetchall()
                return [self._row_to_entry(row) for row in rows]

    async def get_top_alive(self, limit: int = 50) -> List[AIApiEntry]:
        """Top alive models by smart score + speed."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                """SELECT * FROM ai_apis
                   WHERE alive = 1
                   ORDER BY (CASE WHEN api_key_type='free' THEN 0 ELSE 1 END),
                            benchmark_score DESC, response_time ASC
                   LIMIT ?""",
                (limit,),
            ) as cursor:
                rows = await cursor.fetchall()
                return [self._row_to_entry(row) for row in rows]

    async def get_alive(self) -> List[AIApiEntry]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM ai_apis WHERE alive = 1 ORDER BY response_time ASC") as cursor:
                rows = await cursor.fetchall()
                return [self._row_to_entry(row) for row in rows]

    async def get_dead_or_pending(self) -> List[AIApiEntry]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM ai_apis WHERE alive != 1 ORDER BY last_checked ASC"
            ) as cursor:
                rows = await cursor.fetchall()
                return [self._row_to_entry(row) for row in rows]

    async def get_random_candidates(self, limit: int = 20) -> List[dict]:
        """Get random dead/pending entries to re-test."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM ai_apis WHERE alive != 1 ORDER BY RANDOM() LIMIT ?",
                (limit,),
            ) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]

    async def get_all_pending(self) -> List[dict]:
        """Get ALL entries that haven't been tested yet (alive IS NULL) or are dead."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM ai_apis WHERE alive IS NULL OR alive = 0 ORDER BY last_checked ASC"
            ) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]

    async def delete_entry(self, entry_id: str):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM ai_apis WHERE id = ?", (entry_id,))
            await db.commit()

    async def mark_alive(self, entry_id: str, response_time: float, speed_label: str):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """UPDATE ai_apis SET alive = 1, response_time = ?, speed_label = ?, last_checked = ? WHERE id = ?""",
                (response_time, speed_label, _now_iso(), entry_id),
            )
            await db.commit()

    async def mark_dead(self, entry_id: str):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                UPDATE ai_apis
                SET alive = 0, response_time = NULL, speed_label = 'unknown',
                    last_checked = ?, death_count = death_count + 1
                WHERE id = ?
                """,
                (_now_iso(), entry_id),
            )
            await db.commit()

    async def insert_new(self, endpoints: List[dict]):
        """Insert new discovered endpoints with full metadata."""
        if not endpoints:
            return
        async with aiosqlite.connect(self.db_path) as db_conn:
            for ep in endpoints:
                modality = ep.get("modality", "text")
                ctx_len = int(ep.get("contextLength", 0))
                bench_score = float(ep.get("benchmarkScore", 0.0))
                is_free = ep.get("isFree", False)
                # Mark as "smart" if free AND (good benchmark OR large context OR multimodal)
                is_smart = 1 if (is_free and (bench_score >= 10.0 or ctx_len >= 200000 or '+' in modality)) else 0
                await db_conn.execute(
                    """INSERT OR IGNORE INTO ai_apis
                       (id, model_name, endpoint, api_key_type, source, alive, last_checked, speed_label, death_count, context_length, modality, benchmark_score, is_smart)
                       VALUES (?, ?, ?, ?, ?, NULL, '', '', 0, ?, ?, ?, ?)
                    """,
                    (ep["id"], ep["modelName"], ep["endpoint"], ep["apiKey"], ep["source"],
                     ctx_len, modality, bench_score, is_smart),
                )
            await db_conn.commit()

    async def get_stats(self) -> dict:
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT COUNT(*) FROM ai_apis") as c:
                total = (await c.fetchone())[0]
            async with db.execute("SELECT COUNT(*) FROM ai_apis WHERE alive = 1") as c:
                alive_count = (await c.fetchone())[0]
            async with db.execute("SELECT COUNT(*) FROM ai_apis WHERE alive = 0") as c:
                dead_count = (await c.fetchone())[0]
            async with db.execute(
                "SELECT AVG(response_time) FROM ai_apis WHERE alive = 1 AND response_time IS NOT NULL"
            ) as c:
                avg_rt = (await c.fetchone())[0] or 0
            return {
                "totalDiscovered": total,
                "aliveCount": alive_count,
                "deadCount": dead_count,
                "avgResponseTime": round(avg_rt) if avg_rt else 0,
            }

    @staticmethod
    def _row_to_entry(row) -> AIApiEntry:
        return AIApiEntry(
            id=row["id"],
            modelName=row["model_name"],
            endpoint=row["endpoint"],
            apiKey=row["api_key_type"],
            source=row["source"],
            responseTime=row["response_time"],
            alive=bool(row["alive"]) if row["alive"] is not None else None,
            lastChecked=row["last_checked"] or "",
            speedLabel=row["speed_label"] or "",
            deathCount=row["death_count"] if row["death_count"] is not None else 0,
            contextLength=row["context_length"] if row["context_length"] is not None else 0,
            modality=row["modality"] or "text",
            benchmarkScore=float(row["benchmark_score"]) if row["benchmark_score"] is not None else 0.0,
            isSmart=bool(row["is_smart"]) if row["is_smart"] is not None else False,
        )


def _now_iso():
    import datetime
    return datetime.datetime.utcnow().isoformat()
