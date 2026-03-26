import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.auto_assign_scheduler import JiraAutoAssignScheduler


def test_scheduler_persists_processed_tickets(tmp_path, monkeypatch):
    state_file = tmp_path / "processed.json"
    monkeypatch.setenv("PROCESSED_TICKETS_STATE_FILE", str(state_file))

    scheduler = JiraAutoAssignScheduler(interval_seconds=5)
    scheduler.processed_tickets.add("NFSAAS-1")
    scheduler._save_processed_tickets()

    assert state_file.exists()
    data = json.loads(state_file.read_text(encoding="utf-8"))
    assert "NFSAAS-1" in data["tickets"]

    reloaded = JiraAutoAssignScheduler(interval_seconds=5)
    assert "NFSAAS-1" in reloaded.processed_tickets


def test_scheduler_loads_legacy_list_state(tmp_path, monkeypatch):
    state_file = tmp_path / "processed.json"
    state_file.write_text(json.dumps(["NFSAAS-2"]), encoding="utf-8")
    monkeypatch.setenv("PROCESSED_TICKETS_STATE_FILE", str(state_file))

    scheduler = JiraAutoAssignScheduler(interval_seconds=5)
    assert "NFSAAS-2" in scheduler.processed_tickets
