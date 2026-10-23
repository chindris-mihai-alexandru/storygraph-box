import os
import sys
from typing import ClassVar

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import storygraph_box as box


@pytest.fixture(autouse=True)
def pinned_year(monkeypatch):
    """The fixture dates are 2026, so pin the clock and keep January 1st harmless."""
    monkeypatch.setattr(box, "current_year", lambda: 2026)
    # setenv records the original state, so anything a test leaks is undone afterwards
    for name in ("AUDIBLE_AUTH_FILE", "AUDIBLE_AUTH", "AUDIBLE_ADP_TOKEN", "AUDIBLE_DEVICE_PRIVATE_KEY", "INPUT_DRY_RUN"):
        monkeypatch.setenv(name, "")


def setup_module(module):
    box.CSV_PATH = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "sample_export.csv"
    )
    box.WRAP_WIDTH = 50
    box.GOAL_BOOKS = "12"
    box.AUDIBLE_AUTH_FILE = ""
    os.environ.pop("AUDIBLE_AUTH_FILE", None)


def test_header_and_sections_present():
    body = box.build_body()
    assert body.startswith("latest reads")
    assert "Currently reading:" in body
    assert "Recently read:" in body
    assert "Recently listened:" in body


def test_currently_reading_lists_the_book_without_a_bogus_progress_bar():
    """Real exports carry no progress column, so no bar and no 0% may appear."""
    body = box.build_body()
    reading = body.split("Currently reading:")[1].split("\n\n")[0]
    assert reading.strip() == "The Name of the Wind by Patrick Rothfuss"
    assert "%" not in body
    assert "\u2591" not in body


def test_fixture_mirrors_the_real_export_header():
    import csv

    with open(box.CSV_PATH, newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        rows = list(reader)
    assert len(reader.fieldnames) == 23
    assert {"Moods", "Pace", "Star Rating", "Review", "Tags"} <= set(reader.fieldnames)
    for row in rows:
        assert None not in row and None not in row.values(), row


def test_audio_format_goes_to_listened():
    body = box.build_body()
    listened = body.split("Recently listened:")[1]
    assert "Dune by Frank Herbert" in listened
    assert "The Way of Kings by Brandon Sanderson" in listened
    assert "The Remains of the Day" not in listened


def test_print_and_digital_go_to_read():
    body = box.build_body()
    read = body.split("Recently read:")[1].split("Recently listened:")[0]
    assert "The Remains of the Day by Kazuo Ishiguro" in read
    assert "Project Hail Mary by Andy Weir" in read
    assert "Dune by Frank Herbert" not in read


def test_goal_line_counts_current_year():
    body = box.build_body()
    assert "read 3 of 12 books in 2026" in body


def test_no_audible_line_without_auth():
    body = box.build_body()
    assert "on Audible" not in body


def test_wrapped_lines_respect_width():
    body = box.build_body()
    for line in body.split("\n"):
        assert len(line.rstrip()) <= 50 + 2, line


def test_audiobook_prefix_is_stripped():
    rows = [{"title": "Audiobook Dune", "authors": "Frank Herbert", "format": "audio"}]
    assert box.book_line(rows[0]) == "Dune by Frank Herbert"


def test_unknown_format_defaults_to_read():
    rows = [{"title": "Some Book", "authors": "Someone", "format": "", "read status": "read", "last date read": "2026/01/01"}]
    read_books, listened_books = [], []
    for row in rows:
        fmt = box.pick(row, "format").lower()
        (listened_books if "audio" in fmt else read_books).append(row)
    assert len(read_books) == 1 and not listened_books

def test_did_not_finish_is_left_out_everywhere():
    body = box.build_body()
    assert "Infinite Jest" not in body


def test_to_read_pile_is_left_out():
    assert "Piranesi" not in box.build_body()


def test_html_entities_are_unescaped():
    body = box.build_body()
    assert "Pride & Prejudice by Jane Austen" in body
    assert "&amp;" not in body


def test_undated_finished_book_sorts_last_without_crashing():
    read = box.build_body().split("Recently read:")[1].split("Recently listened:")[0]
    lines = [line for line in read.split("\n") if line]
    assert lines[-1] == "The Hobbit by J.R.R. Tolkien"


def test_status_spellings_are_folded_together():
    for spelling in ("currently-reading", "currently_reading", "Currently reading", " CURRENTLY  READING "):
        assert box.normalize_status(spelling) == "currently reading"
    assert box.normalize_status("did-not-finish") == "did not finish"


def test_readme_sample_matches_the_real_output():
    """The documented sample is generated from the fixture, so it cannot drift."""
    readme = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "README.md")
    with open(readme, encoding="utf-8") as fh:
        text = fh.read()
    block = text.split("## Sample output")[1].split("```")[1].strip("\n")
    documented = [line for line in block.split("\n") if "on Audible" not in line]
    rendered = box.build_body().rstrip("\n").split("\n")
    assert documented == rendered


def test_two_field_auth_builds_without_network(monkeypatch):
    monkeypatch.delenv("AUDIBLE_AUTH_FILE", raising=False)
    fake_adp = "{enc:enc}{key:key}{iv:iv}{name:name}{serial:Mg==}"
    monkeypatch.setenv("AUDIBLE_ADP_TOKEN", fake_adp)
    fake_key = "-----BEGIN RSA PRIVATE KEY-----\nMIIB\n-----END RSA PRIVATE KEY-----\n"
    monkeypatch.setenv("AUDIBLE_DEVICE_PRIVATE_KEY", fake_key)
    monkeypatch.setenv("INPUT_AUDIBLE_LOCALE", "uk")
    auth = box.audible_auth()
    assert auth.adp_token == fake_adp
    assert auth.locale.country_code == "uk"


def test_no_auth_returns_none(monkeypatch):
    monkeypatch.delenv("AUDIBLE_AUTH_FILE", raising=False)
    monkeypatch.delenv("AUDIBLE_ADP_TOKEN", raising=False)
    monkeypatch.delenv("AUDIBLE_DEVICE_PRIVATE_KEY", raising=False)
    assert box.audible_auth() is None


def test_zero_wrap_keeps_one_line_per_book(monkeypatch):
    monkeypatch.setattr(box, "WRAP_WIDTH", 0)
    long_line = "Reality Check: The Irreverent Guide to Outsmarting, Outmanaging, and Outmarketing Your Competition by Guy Kawasaki"
    rows = [{"title": long_line.replace(" by Guy Kawasaki", ""), "authors": "Guy Kawasaki", "format": "paperback", "read status": "read", "last date read": "2026/01/15"}]
    line = box.book_line(rows[0])
    assert line == long_line
    assert "\n" not in line


class FakeClient:
    """Stands in for audible.Client so the Audible path runs without a network."""

    payload: ClassVar[dict] = {
        "aggregated_monthly_listening_stats": [{"aggregated_sum": 127_680_000}]
    }
    error = None

    def __init__(self, auth):
        self.auth = auth

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def get(self, path, **kwargs):
        if FakeClient.error:
            raise FakeClient.error
        return FakeClient.payload


def test_audible_line_converts_milliseconds(monkeypatch):
    import audible

    monkeypatch.setattr(box, "audible_auth", lambda: object())
    monkeypatch.setattr(audible, "Client", FakeClient)
    monkeypatch.setattr(FakeClient, "error", None)
    year = box.current_year()
    assert box.audible_listening_line() == f"listened 35h 28m in {year} on Audible"


def test_audible_failure_warns_and_skips(monkeypatch, capsys):
    import audible

    monkeypatch.setattr(box, "audible_auth", lambda: object())
    monkeypatch.setattr(audible, "Client", FakeClient)
    monkeypatch.setattr(FakeClient, "error", RuntimeError("boom"))
    assert box.audible_listening_line() is None
    assert "Audible stats unavailable, boom" in capsys.readouterr().err


def test_auth_file_path_is_read_from_the_live_environment(monkeypatch, tmp_path):
    """Regression, the path used to be captured at import time and stayed empty."""
    import audible

    auth_file = tmp_path / "auth.json"
    auth_file.write_text("{}")
    sentinel = object()
    monkeypatch.setattr(box, "AUDIBLE_AUTH_FILE", "")
    monkeypatch.setattr(audible.Authenticator, "from_file", lambda path: sentinel)
    monkeypatch.setenv("AUDIBLE_AUTH_FILE", str(auth_file))
    assert box.audible_auth() is sentinel


def test_restore_audible_auth_decodes_the_secret(monkeypatch, tmp_path):
    import base64

    dest = tmp_path / "restored.json"
    monkeypatch.delenv("AUDIBLE_AUTH_FILE", raising=False)
    monkeypatch.setenv("AUDIBLE_AUTH", base64.b64encode(b'{"k": 1}').decode())
    box.restore_audible_auth(str(dest))
    assert dest.read_bytes() == b'{"k": 1}'
    assert os.environ["AUDIBLE_AUTH_FILE"] == str(dest)


def test_corrupt_audible_secret_degrades_instead_of_crashing(monkeypatch, tmp_path, capsys):
    dest = tmp_path / "restored.json"
    monkeypatch.delenv("AUDIBLE_AUTH_FILE", raising=False)
    monkeypatch.setenv("AUDIBLE_AUTH", "!!! not base64 !!!")
    box.restore_audible_auth(str(dest))
    assert not dest.exists()
    assert "AUDIBLE_AUTH is not valid base64" in capsys.readouterr().err


def test_footer_follows_the_calendar_year(monkeypatch):
    """On 1 January the goal restarts, it must not keep counting last year."""
    monkeypatch.setattr(box, "current_year", lambda: 2027)
    assert box.build_body().splitlines()[-1] == "read 0 of 12 books in 2027"


def test_missing_export_stops_the_run_and_never_touches_the_gist(monkeypatch, capsys):
    calls = []
    monkeypatch.setattr(box, "CSV_PATH", "typo/storygraph_export.csv")
    monkeypatch.setattr(box, "update_gist", lambda body: calls.append(body))
    monkeypatch.delenv("INPUT_DRY_RUN", raising=False)
    assert box.main() == 1
    assert calls == []
    assert "StoryGraph export not found" in capsys.readouterr().err


def test_a_foreign_csv_is_rejected_before_it_can_overwrite_the_gist(monkeypatch, tmp_path, capsys):
    calls = []
    other = tmp_path / "goodreads.csv"
    other.write_text("Book Id,Title,Author\n1,Dune,Frank Herbert\n")
    monkeypatch.setattr(box, "CSV_PATH", str(other))
    monkeypatch.setattr(box, "update_gist", lambda body: calls.append(body))
    monkeypatch.delenv("INPUT_DRY_RUN", raising=False)
    assert box.main() == 1
    assert calls == []
    assert "does not look like a StoryGraph export" in capsys.readouterr().err


def test_dry_run_prints_the_body_and_skips_the_gist(monkeypatch, capsys):
    calls = []
    monkeypatch.setattr(box, "update_gist", lambda body: calls.append(body))
    monkeypatch.setenv("INPUT_DRY_RUN", "true")
    assert box.main() == 0
    assert calls == []
    assert capsys.readouterr().out.startswith("latest reads\n")


def test_a_real_run_updates_the_gist_once(monkeypatch):
    calls = []
    monkeypatch.setattr(box, "update_gist", lambda body: calls.append(body))
    monkeypatch.delenv("INPUT_DRY_RUN", raising=False)
    assert box.main() == 0
    assert len(calls) == 1 and calls[0].startswith("latest reads\n")


def test_header_only_export_renders_an_empty_gist(monkeypatch, tmp_path):
    empty = tmp_path / "empty.csv"
    empty.write_text("Title,Authors,Read Status\n")
    monkeypatch.setattr(box, "CSV_PATH", str(empty))
    monkeypatch.setattr(box, "GOAL_BOOKS", "")
    assert box.build_body().strip() == "latest reads"


def test_a_malformed_audible_secret_degrades_instead_of_crashing(monkeypatch, tmp_path, capsys):
    """Valid base64 that is not an auth file used to raise outside the try block."""
    bad = tmp_path / "auth.json"
    bad.write_text('{"k": 1}')
    monkeypatch.setenv("AUDIBLE_AUTH_FILE", str(bad))
    body = box.build_body()
    assert body.startswith("latest reads")
    assert "on Audible" not in body
    assert "Audible stats unavailable" in capsys.readouterr().err
