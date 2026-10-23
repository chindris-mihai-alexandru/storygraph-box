"""Model-free monthly sync monitoring; installed with its state on the internal disk."""

import argparse
import fcntl
import json
import os
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path


def atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        temporary = Path(handle.name)
        try:
            handle.write(text)
            handle.flush()
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)


def success_this_month(base: Path, now: datetime) -> bool:
    try:
        data = json.loads((base / "success.json").read_text(encoding="utf-8"))
        if not isinstance(data, dict) or data.get("status") != "verified":
            return False
        stamp = datetime.fromisoformat(data["at"].replace("Z", "+00:00"))
        if stamp.tzinfo is None:
            return False
        stamp = stamp.astimezone(timezone.utc)
        return (stamp.year, stamp.month) == (now.year, now.month) and stamp <= now
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return False


def check(base: Path, now: datetime, notify: bool = True) -> str:
    alert = base / "needs-attention.txt"
    if now.day < 8 or success_this_month(base, now):
        alert.unlink(missing_ok=True)
        return "OK"
    atomic_write(alert, f"{now.isoformat()} No verified StoryGraph sync for {now:%Y-%m}.\n")
    marker = base / "notified.txt"
    try:
        notified = marker.read_text(encoding="utf-8").strip() == now.strftime("%Y-%m-%d")
    except (OSError, UnicodeError):
        notified = False
    if notify and not notified:
        try:
            subprocess.run([
                "/usr/bin/osascript", "-e",
                'display notification "Monthly StoryGraph sync needs attention" with title "storygraph-box"',
            ], check=True, capture_output=True, timeout=15)
        except (OSError, subprocess.SubprocessError):
            return "OVERDUE"
        atomic_write(marker, now.strftime("%Y-%m-%d"))
    return "OVERDUE"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("due", "check", "record"))
    parser.add_argument("--state-dir", type=Path, required=True)
    parser.add_argument("--now", help="UTC ISO timestamp for reproducible tests")
    parser.add_argument("--no-notify", action="store_true")
    args = parser.parse_args()
    now = datetime.fromisoformat(args.now.replace("Z", "+00:00")) if args.now else datetime.now(timezone.utc)
    if now.tzinfo is None:
        parser.error("--now must include a timezone")
    now = now.astimezone(timezone.utc)
    base = args.state_dir
    base.mkdir(parents=True, exist_ok=True)
    if args.command == "record":
        atomic_write(base / "success.json", json.dumps({"at": now.isoformat(), "status": "verified"}) + "\n")
        (base / "needs-attention.txt").unlink(missing_ok=True)
        print("RECORDED")
    elif args.command == "due":
        print("NOT_DUE" if success_this_month(base, now) else "DUE")
    else:
        with (base / "monitor.lock").open("a") as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                print("BUSY")
                return 0
            print(check(base, now, not args.no_notify))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
