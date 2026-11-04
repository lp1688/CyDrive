from scraper.parse_utils import (
    machine_from_api_item,
    normalize_machine_id,
    parse_int,
    parse_number,
    parse_percent,
)


def test_parse_percent():
    assert parse_percent("61.15%") == 61.15
    assert parse_percent(120.72) == 120.72
    assert parse_percent(None) is None


def test_parse_number_with_commas():
    assert parse_number("3,240,847.40") == 3240847.40
    assert parse_number("535,849,997.60") == 535849997.60


def test_normalize_machine_id():
    assert normalize_machine_id("12") == "012"
    assert normalize_machine_id("207 機台") == "207"


def test_machine_from_api_item_aliases():
    item = {
        "machineNo": "7",
        "rtp": "88.5%",
        "isOccupied": True,
        "isLocked": False,
        "todayBet": "1,000.50",
        "todayRate": "70%",
    }
    mapped = machine_from_api_item(item)
    assert mapped["machine_id"] == "007"
    assert mapped["percent"] == 88.5
    assert mapped["occupied"] is True
    assert mapped["locked"] is False
    assert mapped["today_bet"] == 1000.50
    assert mapped["today_rate"] == 70.0
    assert parse_int("71") == 71
