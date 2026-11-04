from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class MachineRecord(BaseModel):
    """One machine from the grid, optionally enriched with detail panel stats."""

    machine_id: str
    percent: float | None = None
    occupied: bool = False
    locked: bool = False

    # Detail panel (optional until card is opened / API returns it)
    spins_since_win: int | None = None
    prev1_spins: int | None = None
    prev2_spins: int | None = None
    today_bet: float | None = None
    today_rate: float | None = None
    days30_bet: float | None = None
    days30_rate: float | None = None

    raw: dict[str, Any] = Field(default_factory=dict)
    scraped_at: str = Field(default_factory=utc_now_iso)


class ScrapeResult(BaseModel):
    ok: bool
    count: int
    scraped_at: str = Field(default_factory=utc_now_iso)
    source: str = "unknown"
    machines: list[MachineRecord] = Field(default_factory=list)
    error: str | None = None
