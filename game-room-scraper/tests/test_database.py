from pathlib import Path

from scraper.database import MachineStore
from scraper.models import MachineRecord


def test_upsert_and_list(tmp_path: Path):
    store = MachineStore(tmp_path / "t.db")
    machines = [
        MachineRecord(machine_id="001", percent=61.15, occupied=True, locked=False),
        MachineRecord(
            machine_id="207",
            percent=58.86,
            today_bet=3240847.40,
            today_rate=58.86,
            days30_bet=535849997.60,
            days30_rate=95.62,
            spins_since_win=0,
            prev1_spins=71,
            prev2_spins=1,
        ),
    ]
    store.upsert_machines(machines, source="test", ok=True)
    rows = store.list_machines()
    assert len(rows) == 2
    one = store.get_machine("207")
    assert one is not None
    assert one["today_rate"] == 58.86
    assert one["prev1_spins"] == 71
    run = store.latest_run()
    assert run is not None
    assert run["count"] == 2
    assert run["ok"] is True
