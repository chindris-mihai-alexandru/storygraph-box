import fcntl
import json
import runpy
import sys
from datetime import UTC, datetime
from unittest.mock import Mock

import pytest

import sync_monitor as monitor

NOW = datetime(2026, 11, 8, 10, tzinfo=UTC)


@pytest.mark.parametrize("data", [
    None, [], {}, {"status": "failed"},
    {"status": "verified"}, {"status": "verified", "at": None},
    {"status": "verified", "at": "invalid"},
    {"status": "verified", "at": "2026-11-01T07:00:00"},
    {"status": "verified", "at": "2026-10-01T07:00:00Z"},
    {"status": "verified", "at": "2026-11-09T07:00:00Z"},
])
def test_invalid_or_stale_heartbeat_is_due(tmp_path, data):
    monitor.atomic_write(tmp_path / "success.json", json.dumps(data))
    assert not monitor.success_this_month(tmp_path, NOW)


def test_missing_or_corrupt_heartbeat_is_due(tmp_path):
    assert not monitor.success_this_month(tmp_path, NOW)
    (tmp_path / "success.json").write_bytes(b"\xff")
    assert not monitor.success_this_month(tmp_path, NOW)


def test_verified_heartbeat_has_no_private_payload(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["monitor", "record", "--state-dir", str(tmp_path), "--now", NOW.isoformat()])
    assert monitor.main() == 0
    assert capsys.readouterr().out.strip() == "RECORDED"
    data = json.loads((tmp_path / "success.json").read_text())
    assert data == {"at": NOW.isoformat(), "status": "verified"}
    assert monitor.success_this_month(tmp_path, NOW)


def test_watchdog_alerts_once_per_day_and_clears_on_recovery(tmp_path, monkeypatch):
    notify = Mock()
    monkeypatch.setattr(monitor.subprocess, "run", notify)
    assert monitor.check(tmp_path, NOW) == "OVERDUE"
    assert (tmp_path / "needs-attention.txt").exists()
    assert monitor.check(tmp_path, NOW) == "OVERDUE"
    assert notify.call_count == 1
    assert monitor.check(tmp_path, NOW.replace(day=9)) == "OVERDUE"
    assert notify.call_count == 2
    monitor.atomic_write(tmp_path / "success.json", json.dumps({"status": "verified", "at": NOW.isoformat()}))
    assert monitor.check(tmp_path, NOW) == "OK"
    assert not (tmp_path / "needs-attention.txt").exists()


def test_notification_failure_preserves_alert_and_retries(tmp_path, monkeypatch):
    monkeypatch.setattr(monitor.subprocess, "run", Mock(side_effect=OSError("unavailable")))
    assert monitor.check(tmp_path, NOW) == "OVERDUE"
    assert (tmp_path / "needs-attention.txt").exists()
    assert not (tmp_path / "notified.txt").exists()


def test_check_can_be_silent_and_first_week_is_not_overdue(tmp_path):
    assert monitor.check(tmp_path, NOW, notify=False) == "OVERDUE"
    assert monitor.check(tmp_path, NOW.replace(day=7), notify=False) == "OK"
    assert not (tmp_path / "needs-attention.txt").exists()


@pytest.mark.parametrize("command,expected", [("due", "DUE"), ("check", "OVERDUE")])
def test_cli_due_and_check(tmp_path, monkeypatch, capsys, command, expected):
    monkeypatch.setattr(sys, "argv", ["monitor", command, "--state-dir", str(tmp_path), "--now", NOW.isoformat(), "--no-notify"])
    assert monitor.main() == 0
    assert capsys.readouterr().out.strip() == expected


def test_cli_due_after_success(tmp_path, monkeypatch, capsys):
    monitor.atomic_write(tmp_path / "success.json", json.dumps({"status": "verified", "at": NOW.isoformat()}))
    monkeypatch.setattr(sys, "argv", ["monitor", "due", "--state-dir", str(tmp_path), "--now", NOW.isoformat()])
    assert monitor.main() == 0
    assert capsys.readouterr().out.strip() == "NOT_DUE"


def test_cli_rejects_naive_time(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "argv", ["monitor", "due", "--state-dir", str(tmp_path), "--now", "2026-11-01T00:00:00"])
    with pytest.raises(SystemExit) as result:
        monitor.main()
    assert result.value.code == 2


def test_lock_prevents_overlap(tmp_path, monkeypatch, capsys):
    with (tmp_path / "monitor.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        monkeypatch.setattr(sys, "argv", ["monitor", "check", "--state-dir", str(tmp_path), "--now", NOW.isoformat()])
        assert monitor.main() == 0
        assert capsys.readouterr().out.strip() == "BUSY"


def test_entry_point_uses_real_clock(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["monitor", "due", "--state-dir", str(tmp_path)])
    with pytest.raises(SystemExit) as result:
        runpy.run_path(monitor.__file__, run_name="__main__")
    assert result.value.code == 0
    assert capsys.readouterr().out.strip() == "DUE"


def test_atomic_write_failure_cleans_temporary_file(tmp_path, monkeypatch):
    monkeypatch.setattr(monitor.os, "replace", Mock(side_effect=OSError("disk failure")))
    with pytest.raises(OSError, match="disk failure"):
        monitor.atomic_write(tmp_path / "success.json", "test")
    assert not list(tmp_path.iterdir())
