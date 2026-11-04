from __future__ import annotations

import re
from typing import Any


_NUM_RE = re.compile(r"-?\d+(?:[.,]\d+)?")


def parse_percent(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace("%", "").replace(",", "")
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        match = _NUM_RE.search(text)
        return float(match.group().replace(",", "")) if match else None


def parse_number(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace(",", "").replace("，", "")
    if not text:
        return None
    match = _NUM_RE.search(text)
    if not match:
        return None
    try:
        return float(match.group().replace(",", ""))
    except ValueError:
        return None


def parse_int(value: Any) -> int | None:
    num = parse_number(value)
    return int(num) if num is not None else None


def normalize_machine_id(value: Any) -> str:
    text = str(value or "").strip()
    digits = re.sub(r"\D", "", text)
    return digits.zfill(3) if digits else text


def machine_from_api_item(item: dict[str, Any]) -> dict[str, Any]:
    """Map common API field aliases into our MachineRecord-shaped dict."""
    mid = (
        item.get("machine_id")
        or item.get("machineId")
        or item.get("id")
        or item.get("no")
        or item.get("machineNo")
        or item.get("seat")
    )
    percent = (
        item.get("percent")
        or item.get("rtp")
        or item.get("rate")
        or item.get("scoreRate")
        or item.get("percentage")
    )
    occupied = bool(
        item.get("occupied")
        or item.get("isOccupied")
        or item.get("inUse")
        or item.get("hasPlayer")
    )
    locked = bool(item.get("locked") or item.get("isLocked") or item.get("lock"))
    return {
        "machine_id": normalize_machine_id(mid),
        "percent": parse_percent(percent),
        "occupied": occupied,
        "locked": locked,
        "spins_since_win": parse_int(
            item.get("spins_since_win") or item.get("unopened") or item.get("sinceWin")
        ),
        "prev1_spins": parse_int(item.get("prev1_spins") or item.get("prev1")),
        "prev2_spins": parse_int(item.get("prev2_spins") or item.get("prev2")),
        "today_bet": parse_number(item.get("today_bet") or item.get("todayBet")),
        "today_rate": parse_percent(item.get("today_rate") or item.get("todayRate")),
        "days30_bet": parse_number(item.get("days30_bet") or item.get("bet30") or item.get("days30Bet")),
        "days30_rate": parse_percent(
            item.get("days30_rate") or item.get("rate30") or item.get("days30Rate")
        ),
        "raw": item,
    }
