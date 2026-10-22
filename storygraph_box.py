#!/usr/bin/env python3
"""storygraph-box, update a pinned gist with your latest StoryGraph reads,
listens and Audible listening time, in plain ashtom-style text.

Reads a StoryGraph library CSV export (user menu, Account Settings,
Export Data) committed into the consumer's repository, optionally reads
Audible listening stats via mkb79/Audible, and rewrites a single-file gist.

Inputs come from environment variables, which GitHub Actions populates
from action.yml inputs (INPUT_*) and secrets.
"""

import base64
import csv
import os
import sys
import textwrap
from datetime import datetime

from github import Auth, Github, InputFileContent

WRAP_WIDTH = int(os.environ.get("INPUT_WRAP_WIDTH", "50"))
CSV_PATH = os.environ.get("INPUT_CSV_PATH", "storygraph_export.csv")
GIST_ID = os.environ.get("INPUT_GIST_ID") or os.environ.get("GIST_ID", "")
GH_TOKEN = os.environ.get("GH_TOKEN", "")
AUDIBLE_AUTH_FILE = os.environ.get("AUDIBLE_AUTH_FILE", "")
AUDIBLE_LOCALE = os.environ.get("INPUT_AUDIBLE_LOCALE", "uk")
GOAL_BOOKS = os.environ.get("INPUT_GOAL_BOOKS", "").strip()
HEADER_HINTS = ("Read Status", "Dates Read")


def pick(row: dict, *names: str) -> str:
    lowered = {k.strip().lower(): (k, v) for k, v in row.items()}
    for name in names:
        if name in lowered and lowered[name][1]:
            return str(lowered[name][1]).strip()
    return ""


def bar(percent: int, size: int = 20) -> str:
    syms = "░▏▎▍▌▋▊▉█"
    percent = max(0, min(100, percent))
    frac = (size * 8 * percent) // 100
    full = frac // 8
    if full >= size:
        return syms[8] * size
    semi = syms[frac % 8] if percent > 0 else ""
    return (syms[8] * full + semi).ljust(size, syms[0])


def load_rows() -> list[dict]:
    if CSV_PATH and os.path.exists(CSV_PATH):
        with open(CSV_PATH, newline="", encoding="utf-8-sig") as fh:
            return list(csv.DictReader(fh))
    return []


def book_line(row: dict) -> str:
    title = pick(row, "title") or "Unknown title"
    if title.lower().startswith("audiobook "):
        title = title[len("audiobook "):]
    authors = pick(row, "authors", "author")
    line = f"{title} by {authors}" if authors else title
    if WRAP_WIDTH <= 0:
        return line
    return "\n".join(textwrap.wrap(line, WRAP_WIDTH) or [line])


def parse_date(value: str):
    for fmt in ("%Y/%m/%d", "%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d %b %Y", "%d/%m/%y"):
        try:
            return datetime.strptime(value.strip(), fmt)
        except ValueError:
            continue
    return None


def build_body() -> str:
    rows = load_rows()
    lines = ["latest reads", ""]

    if not rows:
        lines.append("⏳ waiting for the StoryGraph CSV export")
        return "\n".join(lines)

    finished, reading = [], []
    for row in rows:
        status = pick(row, "read status", "status").lower()
        if "currently" in status:
            reading.append(row)
        elif status in ("read", "finished", "did not finish"):
            date_value = pick(row, "date finished", "last date read", "date read")
            date = parse_date(date_value) if date_value else None
            finished.append((date or datetime.min, row))

    if reading:
        lines.append("Currently reading:")
        for row in reading:
            progress = pick(row, "progress", "progress %", "percent complete")
            digits = "".join(ch for ch in progress if ch.isdigit())
            pct = int(digits[:2] or 0) if digits else 0
            lines.append(book_line(row))
            lines.append(f"{bar(pct)} {pct}%")
        lines.append("")

    finished.sort(key=lambda pair: pair[0], reverse=True)
    read_books, listened_books = [], []
    for _, row in finished:
        fmt = pick(row, "format").lower()
        (listened_books if "audio" in fmt else read_books).append(row)

    if read_books:
        lines.append("Recently read:")
        for row in read_books[:5]:
            lines.append(book_line(row))
    if listened_books:
        lines.append("")
        lines.append("Recently listened:")
        for row in listened_books[:3]:
            lines.append(book_line(row))

    stats_footer = []
    if GOAL_BOOKS:
        year = datetime.now().year
        done = sum(1 for d, _ in finished if d.year == year)
        stats_footer.append(f"read {done} of {GOAL_BOOKS} books in {year}")
    listening = audible_listening_line()
    if listening:
        stats_footer.append(listening)
    if stats_footer:
        lines.append("")
        lines.extend(stats_footer)
    return "\n".join(lines)


def audible_auth():
    """Build an Authenticator from the full auth file or the two-field pattern.

    The two-field pattern (adp_token plus device_private_key) follows
    mkb79's setup-audible-cli convention, so only those two values ever
    need to live in secrets.
    """
    auth_file = os.environ.get("AUDIBLE_AUTH_FILE") or AUDIBLE_AUTH_FILE
    if auth_file and os.path.exists(auth_file):
        import audible

        return audible.Authenticator.from_file(auth_file)
    adp = os.environ.get("AUDIBLE_ADP_TOKEN", "")
    key = os.environ.get("AUDIBLE_DEVICE_PRIVATE_KEY", "")
    if adp and key:
        import audible

        return audible.Authenticator.from_dict(
            {
                "adp_token": adp,
                "device_private_key": key,
                "locale_code": os.environ.get("INPUT_AUDIBLE_LOCALE", "uk"),
            }
        )
    return None


def audible_listening_line():
    auth = audible_auth()
    if auth is None:
        return None
    try:
        import audible

        with audible.Client(auth=auth) as client:
            stats = client.get(
                "1.0/stats/aggregates",
                monthly_listening_interval_duration="12",
                monthly_listening_interval_start_date=f"{datetime.now().year}-01",
                store="Audible",
            )
        months = stats.get("aggregated_monthly_listening_stats", [])
        total_minutes = sum(int(m.get("aggregated_sum") or 0) for m in months) // 60000
        hours, minutes = divmod(total_minutes, 60)
        year = datetime.now().year
        return f"listened {hours}h {minutes:02d}m in {year} on Audible"
    except Exception as error:  # noqa: BLE001, any failure means skip the line gracefully
        print(f"storygraph-box, Audible stats unavailable, {error}", file=sys.stderr)
        return None


def update_gist(body: str) -> None:
    gh = Github(auth=Auth.Token(GH_TOKEN))
    gist = gh.get_gist(GIST_ID)
    filename = next(iter(gist.files))
    gist.edit(files={filename: InputFileContent(body)})


if __name__ == "__main__":
    auth_b64 = os.environ.get("AUDIBLE_AUTH", "")
    if auth_b64:
        with open("/tmp/audible_auth.json", "wb") as fh:
            fh.write(base64.b64decode(auth_b64))
        os.environ["AUDIBLE_AUTH_FILE"] = "/tmp/audible_auth.json"
    update_gist(build_body())