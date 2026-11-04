from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from scraper.models import MachineRecord, utc_now_iso

SCHEMA = """
CREATE TABLE IF NOT EXISTS machines (
    machine_id TEXT PRIMARY KEY,
    percent REAL,
    occupied INTEGER NOT NULL DEFAULT 0,
    locked INTEGER NOT NULL DEFAULT 0,
    spins_since_win INTEGER,
    prev1_spins INTEGER,
    prev2_spins INTEGER,
    today_bet REAL,
    today_rate REAL,
    days30_bet REAL,
    days30_rate REAL,
    raw_json TEXT NOT NULL DEFAULT '{}',
    scraped_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS scrape_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scraped_at TEXT NOT NULL,
    source TEXT NOT NULL,
    count INTEGER NOT NULL,
    ok INTEGER NOT NULL,
    error TEXT
);
"""


class MachineStore:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript(SCHEMA)

    def upsert_machines(self, machines: list[MachineRecord], source: str, ok: bool, error: str | None = None) -> None:
        now = utc_now_iso()
        with self._connect() as conn:
            for m in machines:
                conn.execute(
                    """
                    INSERT INTO machines (
                        machine_id, percent, occupied, locked,
                        spins_since_win, prev1_spins, prev2_spins,
                        today_bet, today_rate, days30_bet, days30_rate,
                        raw_json, scraped_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(machine_id) DO UPDATE SET
                        percent=excluded.percent,
                        occupied=excluded.occupied,
                        locked=excluded.locked,
                        spins_since_win=excluded.spins_since_win,
                        prev1_spins=excluded.prev1_spins,
                        prev2_spins=excluded.prev2_spins,
                        today_bet=excluded.today_bet,
                        today_rate=excluded.today_rate,
                        days30_bet=excluded.days30_bet,
                        days30_rate=excluded.days30_rate,
                        raw_json=excluded.raw_json,
                        scraped_at=excluded.scraped_at,
                        updated_at=excluded.updated_at
                    """,
                    (
                        m.machine_id,
                        m.percent,
                        int(m.occupied),
                        int(m.locked),
                        m.spins_since_win,
                        m.prev1_spins,
                        m.prev2_spins,
                        m.today_bet,
                        m.today_rate,
                        m.days30_bet,
                        m.days30_rate,
                        json.dumps(m.raw, ensure_ascii=False),
                        m.scraped_at,
                        now,
                    ),
                )
            conn.execute(
                """
                INSERT INTO scrape_runs (scraped_at, source, count, ok, error)
                VALUES (?, ?, ?, ?, ?)
                """,
                (now, source, len(machines), int(ok), error),
            )

    def list_machines(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM machines ORDER BY machine_id COLLATE NOCASE"
            ).fetchall()
        return [self._row_to_dict(r) for r in rows]

    def get_machine(self, machine_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM machines WHERE machine_id = ?",
                (machine_id,),
            ).fetchone()
        return self._row_to_dict(row) if row else None

    def latest_run(self) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM scrape_runs ORDER BY id DESC LIMIT 1"
            ).fetchone()
        if not row:
            return None
        return {
            "id": row["id"],
            "scraped_at": row["scraped_at"],
            "source": row["source"],
            "count": row["count"],
            "ok": bool(row["ok"]),
            "error": row["error"],
        }

    @staticmethod
    def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
        raw = row["raw_json"]
        try:
            raw_obj = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            raw_obj = {"_raw": raw}
        return {
            "machine_id": row["machine_id"],
            "percent": row["percent"],
            "occupied": bool(row["occupied"]),
            "locked": bool(row["locked"]),
            "spins_since_win": row["spins_since_win"],
            "prev1_spins": row["prev1_spins"],
            "prev2_spins": row["prev2_spins"],
            "today_bet": row["today_bet"],
            "today_rate": row["today_rate"],
            "days30_bet": row["days30_bet"],
            "days30_rate": row["days30_rate"],
            "raw": raw_obj,
            "scraped_at": row["scraped_at"],
            "updated_at": row["updated_at"],
        }
