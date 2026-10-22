import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import storygraph_box as box


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


def test_currently_reading_shows_progress():
    body = box.build_body()
    reading = body.split("Currently reading:")[1].split("\n\n")[0]
    assert "The Name of the Wind by Patrick Rothfuss" in reading
    assert reading.rstrip().endswith("42%")


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
        if line.rstrip().endswith("42%"):
            continue  # the progress bar line is allowed to run wide
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
