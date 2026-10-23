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
import html
import os
import re
import sys
import textwrap
from datetime import datetime

from github import Auth, Github, InputFileContent

WRAP_WIDTH = int(os.environ.get("INPUT_WRAP_WIDTH", "50"))
TITLE_MAX = int(os.environ.get("INPUT_TITLE_MAX", "0") or 0)
CSV_PATH = os.environ.get("INPUT_CSV_PATH", "storygraph_export.csv")
GIST_ID = os.environ.get("INPUT_GIST_ID") or os.environ.get("GIST_ID", "")
GH_TOKEN = os.environ.get("GH_TOKEN", "")
AUDIBLE_AUTH_FILE = os.environ.get("AUDIBLE_AUTH_FILE", "")
GOAL_BOOKS = os.environ.get("INPUT_GOAL_BOOKS", "").strip()
REQUIRED_COLUMNS = ("title", "read status")
KNOWN_STATUSES = {"read", "finished", "currently reading", "to read", "did not finish"}


def current_year() -> int:
    return datetime.now().year


def pick(row: dict, *names: str) -> str:
    lowered = {k.strip().lower(): (k, v) for k, v in row.items()}
    for name in names:
        if name in lowered and lowered[name][1]:
            return str(lowered[name][1]).strip()
    return ""


def load_rows() -> list[dict]:
    if not os.path.exists(CSV_PATH):
        raise FileNotFoundError(f"StoryGraph export not found at {CSV_PATH!r}, check csv_path")
    with open(CSV_PATH, newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        columns = {name.strip().lower() for name in (reader.fieldnames or []) if name}
        if not all(column in columns for column in REQUIRED_COLUMNS):
            raise ValueError(
                f"{CSV_PATH!r} does not look like a StoryGraph export, "
                f"expected the columns {', '.join(REQUIRED_COLUMNS)}"
            )
        return list(reader)


def shorten(line: str, title: str, authors: str) -> str:
    """Drop a subtitle only when the line is too long and the short form fits.

    StoryGraph titles carry their subtitle, the pinned card clips a line near
    55 characters. If cutting after the first ": " still does not fit, the full
    title is kept, a clipped title beats a dangling fragment.
    """
    if TITLE_MAX <= 0 or len(line) <= TITLE_MAX or ": " not in title:
        return line
    short = title.split(": ", 1)[0].strip()
    if not short:
        return line
    candidate = f"{short} by {authors}" if authors else short
    return candidate if len(candidate) <= TITLE_MAX else line


def book_line(row: dict) -> str:
    title = html.unescape(pick(row, "title")) or "Unknown title"
    if title.lower().startswith("audiobook "):
        title = title[len("audiobook "):]
    authors = html.unescape(pick(row, "authors", "author"))
    line = f"{title} by {authors}" if authors else title
    line = shorten(line, title, authors)
    if WRAP_WIDTH <= 0:
        return line
    return "\n".join(textwrap.wrap(line, WRAP_WIDTH) or [line])


def normalize_status(value: str) -> str:
    """Fold "currently-reading", "currently_reading" and "Currently reading" together."""
    return re.sub(r"[-_\s]+", " ", value.strip().lower())


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

    finished, reading, unknown = [], [], {}
    for row in rows:
        status = normalize_status(pick(row, "read status", "status"))
        if status == "currently reading":
            reading.append(row)
        elif status in ("read", "finished"):
            date_value = pick(row, "date finished", "last date read", "date read")
            date = parse_date(date_value) if date_value else None
            finished.append((date or datetime.min, row))
        elif status and status not in KNOWN_STATUSES:
            unknown[status] = unknown.get(status, 0) + 1
        # to-read and did-not-finish rows are deliberately left out

    for status, count in unknown.items():
        print(f"storygraph-box, ignoring {count} row(s) with the unrecognized Read Status {status!r}", file=sys.stderr)

    if reading:
        lines.append("Currently reading:")
        for row in reading:
            lines.append(book_line(row))
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
        year = current_year()
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
    try:
        auth = audible_auth()
        if auth is None:
            return None
        import audible

        with audible.Client(auth=auth) as client:
            stats = client.get(
                "1.0/stats/aggregates",
                monthly_listening_interval_duration="12",
                monthly_listening_interval_start_date=f"{current_year()}-01",
                store="Audible",
            )
        months = stats.get("aggregated_monthly_listening_stats", [])
        total_minutes = sum(int(m.get("aggregated_sum") or 0) for m in months) // 60000
        hours, minutes = divmod(total_minutes, 60)
        year = current_year()
        return f"listened {hours}h {minutes:02d}m in {year} on Audible"
    except Exception as error:  # noqa: BLE001, any failure means skip the line gracefully
        print(f"storygraph-box, Audible stats unavailable, {error}", file=sys.stderr)
        return None


def update_gist(body: str) -> None:
    gh = Github(auth=Auth.Token(GH_TOKEN))
    gist = gh.get_gist(GIST_ID)
    filename = next(iter(gist.files))
    gist.edit(files={filename: InputFileContent(body)})


def restore_audible_auth(dest: str = "/tmp/audible_auth.json") -> None:
    """Decode the AUDIBLE_AUTH secret to a file and point AUDIBLE_AUTH_FILE at it.

    A malformed secret must not take the whole run down, the Audible line is
    optional, so it degrades to a warning like every other Audible failure.
    """
    auth_b64 = os.environ.get("AUDIBLE_AUTH", "")
    if not auth_b64:
        return
    try:
        data = base64.b64decode(auth_b64, validate=True)
    except ValueError as error:
        print(f"storygraph-box, AUDIBLE_AUTH is not valid base64, {error}", file=sys.stderr)
        return
    with open(dest, "wb") as fh:
        fh.write(data)
    os.environ["AUDIBLE_AUTH_FILE"] = dest


def main() -> int:
    restore_audible_auth()
    try:
        body = build_body()
    except (FileNotFoundError, ValueError) as error:
        print(f"storygraph-box, {error}", file=sys.stderr)
        return 1
    if os.environ.get("INPUT_DRY_RUN", "").strip().lower() == "true":
        print(body)
        return 0
    update_gist(body)
    return 0


if __name__ == "__main__":
    sys.exit(main())
