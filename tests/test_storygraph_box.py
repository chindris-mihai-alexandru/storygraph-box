import os
import sys
from typing import ClassVar

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import storygraph_box as box


@pytest.fixture(autouse=True)
def pinned_year(monkeypatch):
    """Reset every setting per test and restore the caller's environment afterwards."""
    monkeypatch.setattr(box, "current_year", lambda: 2026)
    monkeypatch.setattr(box, "CSV_PATH", os.path.join(os.path.dirname(__file__), "sample_export.csv"))
    monkeypatch.setattr(box, "WRAP_WIDTH", 50)
    monkeypatch.setattr(box, "TITLE_MAX", 0)
    monkeypatch.setattr(box, "OUTPUT_STYLE", "classic")
    monkeypatch.setattr(box, "GOAL_BOOKS", "12")
    monkeypatch.setattr(box, "AUDIBLE_AUTH_FILE", "")
    for name in ("AUDIBLE_AUTH_FILE", "AUDIBLE_AUTH", "AUDIBLE_ADP_TOKEN", "AUDIBLE_DEVICE_PRIVATE_KEY", "INPUT_DRY_RUN", "INPUT_OUTPUT_STYLE"):
        monkeypatch.setenv(name, "")


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


def test_unknown_format_defaults_to_read(monkeypatch):
    monkeypatch.setattr(box, "load_rows", lambda: [{
        "title": "Some Book", "authors": "Someone", "format": "",
        "read status": "read", "last date read": "2026/01/01",
    }])
    body = box.build_body()
    assert "Recently read:\nSome Book by Someone" in body
    assert "Recently listened:" not in body

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


def test_unrecognized_status_is_reported_not_silently_dropped(monkeypatch, tmp_path, capsys):
    export = tmp_path / "export.csv"
    export.write_text("Title,Authors,Read Status\nA,B,paused\nC,D,paused\nE,F,read\n")
    monkeypatch.setattr(box, "CSV_PATH", str(export))
    monkeypatch.setattr(box, "GOAL_BOOKS", "")
    body = box.build_body()
    assert "A by B" not in body
    assert "ignoring 2 row(s) with the unrecognized Read Status 'paused'" in capsys.readouterr().err


def test_known_statuses_stay_quiet(capsys):
    box.build_body()
    assert "unrecognized" not in capsys.readouterr().err


def test_non_ascii_titles_survive_the_round_trip(monkeypatch, tmp_path):
    export = tmp_path / "export.csv"
    export.write_bytes("Title,Authors,Read Status,Last Date Read\nŞocul întoarcerii în ţară,Neagu Djuvara,read,2026/05/01\n".encode())
    monkeypatch.setattr(box, "CSV_PATH", str(export))
    monkeypatch.setattr(box, "GOAL_BOOKS", "")
    assert "Şocul întoarcerii în ţară by Neagu Djuvara" in box.build_body()


def line_for(title, authors="Guy Kawasaki"):
    return box.book_line({"title": title, "authors": authors})


def test_subtitles_are_kept_by_default(monkeypatch):
    monkeypatch.setattr(box, "WRAP_WIDTH", 0)
    long_title = "Reality Check: The Irreverent Guide to Outsmarting, Outmanaging, and Outmarketing"
    assert line_for(long_title) == f"{long_title} by Guy Kawasaki"


def test_a_long_subtitle_is_dropped_when_the_short_form_fits(monkeypatch):
    monkeypatch.setattr(box, "WRAP_WIDTH", 0)
    monkeypatch.setattr(box, "TITLE_MAX", 52)
    long_title = "Reality Check: The Irreverent Guide to Outsmarting, Outmanaging, and Outmarketing"
    assert line_for(long_title) == "Reality Check by Guy Kawasaki"


def test_a_line_that_already_fits_is_never_touched(monkeypatch):
    monkeypatch.setattr(box, "WRAP_WIDTH", 0)
    monkeypatch.setattr(box, "TITLE_MAX", 52)
    assert line_for("Star Wars: Thrawn", "Timothy Zahn") == "Star Wars: Thrawn by Timothy Zahn"


def test_the_full_title_stays_when_the_short_form_still_does_not_fit(monkeypatch):
    monkeypatch.setattr(box, "WRAP_WIDTH", 0)
    monkeypatch.setattr(box, "TITLE_MAX", 52)
    title = "Jurnal de razboi 1916-1918 - Maria, Regina Romaniei. Lectura: Oana Pellea"
    assert line_for(title, "Regina Maria") == f"{title} by Regina Maria"


def test_shortening_handles_missing_authors_and_empty_leads(monkeypatch):
    monkeypatch.setattr(box, "WRAP_WIDTH", 0)
    monkeypatch.setattr(box, "TITLE_MAX", 20)
    assert box.book_line({"title": "Short: " + "x" * 40}) == "Short"
    assert box.book_line({"title": ": " + "x" * 40}) == ": " + "x" * 40


def test_only_the_first_colon_splits_the_title(monkeypatch):
    monkeypatch.setattr(box, "WRAP_WIDTH", 0)
    monkeypatch.setattr(box, "TITLE_MAX", 40)
    assert line_for("Life 3.0: Being Human: In the Age of Artificial Intelligence", "Max Tegmark") == "Life 3.0 by Max Tegmark"


@pytest.mark.parametrize("content", [
    "",
    "Title,Read Status, title\nA,read,A\n",
    "Title,Read Status,\nA,read,x\n",
    "Title,Authors,Read Status\nA,B\n",
    "Title,Read Status\nA,read,extra\n",
    'Title,Read Status\n"unfinished,read\n',
])
def test_broken_export_never_updates_the_gist(content, monkeypatch, tmp_path, capsys):
    export = tmp_path / "broken.csv"
    export.write_text(content)
    calls = []
    monkeypatch.setattr(box, "CSV_PATH", str(export))
    monkeypatch.setattr(box, "update_gist", calls.append)
    assert box.main() == 1
    assert not calls
    assert capsys.readouterr().err.startswith("storygraph-box,")


def test_invalid_utf8_export_is_rejected(monkeypatch, tmp_path, capsys):
    export = tmp_path / "broken.csv"
    export.write_bytes(b"Title,Read Status\n\xff,read\n")
    monkeypatch.setattr(box, "CSV_PATH", str(export))
    assert box.main() == 1
    assert "decode" in capsys.readouterr().err


def test_quoted_multiline_review_is_valid(monkeypatch, tmp_path):
    export = tmp_path / "valid.csv"
    export.write_text('Title,Read Status,Review\nDune,read,"two\nlines, and a comma"\n')
    monkeypatch.setattr(box, "CSV_PATH", str(export))
    assert box.load_rows()[0]["Review"] == "two\nlines, and a comma"


def test_bom_export_has_normalized_columns(monkeypatch):
    monkeypatch.setattr(box, "CSV_PATH", os.path.join(
        os.path.dirname(__file__), "bom_export.csv"
    ))
    assert box.pick(box.load_rows()[0], "title")
    assert box.build_body().startswith("latest reads\n\n")


@pytest.mark.parametrize(("value", "expected"), [
    ("2026/10/23", (2026, 10, 23)),
    ("2026-10-23", (2026, 10, 23)),
    ("23/10/2026", (2026, 10, 23)),
    ("10/23/2026", (2026, 10, 23)),
    ("23 Oct 2026", (2026, 10, 23)),
    ("23/10/26", (2026, 10, 23)),
    ("2026/02/30", None),
    ("not a date", None),
    ("", None),
])
def test_date_formats_and_invalid_dates(value, expected):
    result = box.parse_date(value)
    assert ((result.year, result.month, result.day) if result else None) == expected


def test_real_clock_is_used_in_production(monkeypatch):
    monkeypatch.undo()
    assert box.current_year() == box.datetime.now().year


def test_reading_status_variants_use_the_real_renderer(monkeypatch):
    for status in ("currently reading", "currently-reading", "currently_reading"):
        monkeypatch.setattr(box, "load_rows", lambda status=status: [{
            "Title": "A book", "Read Status": status,
        }])
        assert "Currently reading:\nA book" in box.build_body()


def test_audio_only_has_one_blank_line_after_header(monkeypatch):
    monkeypatch.setattr(box, "load_rows", lambda: [{
        "Title": "Dune", "Read Status": "read", "Format": "audio",
    }])
    monkeypatch.setattr(box, "GOAL_BOOKS", "")
    assert box.build_body() == "latest reads\n\nRecently listened:\nDune"


def test_reading_and_audio_sections_have_one_blank_line(monkeypatch):
    monkeypatch.setattr(box, "load_rows", lambda: [
        {"Title": "Reading", "Read Status": "currently reading"},
        {"Title": "Dune", "Read Status": "read", "Format": "audio"},
    ])
    monkeypatch.setattr(box, "GOAL_BOOKS", "")
    assert box.build_body() == (
        "latest reads\n\nCurrently reading:\nReading\n\nRecently listened:\nDune"
    )


def test_embedded_metadata_whitespace_cannot_inject_sections(monkeypatch):
    monkeypatch.setattr(box, "WRAP_WIDTH", 0)
    assert box.book_line({
        "title": "A&#10;Title\t with spaces", "authors": "One\n Author",
    }) == "A Title with spaces by One Author"
    assert box.book_line({"title": "", "authors": ""}) == "Unknown title"


def test_list_limits_and_order_are_applied_in_renderer(monkeypatch):
    rows = [{
        "Title": f"Print{i}", "Read Status": "read", "Last Date Read": f"2026/01/{i:02}",
    } for i in range(1, 8)]
    rows += [{
        "Title": f"Audio{i}", "Read Status": "read", "Format": "audio",
        "Last Date Read": f"2026/01/{i:02}",
    } for i in range(1, 6)]
    monkeypatch.setattr(box, "load_rows", lambda: rows)
    body = box.build_body()
    assert body.index("Print7") < body.index("Print3")
    assert "Print2" not in body and "Audio2" not in body
    assert "read 12 of 12 books in 2026" in body


def test_auth_restore_disk_error_is_optional(monkeypatch, tmp_path, capsys):
    import base64

    monkeypatch.setenv("AUDIBLE_AUTH", base64.b64encode(b"{}").decode())
    box.restore_audible_auth(str(tmp_path / "absent" / "auth.json"))
    assert "could not restore optional Audible auth file" in capsys.readouterr().err
    assert not os.environ["AUDIBLE_AUTH_FILE"]


def test_partial_two_field_auth_does_not_build_an_authenticator(monkeypatch):
    monkeypatch.setenv("AUDIBLE_ADP_TOKEN", "one field only")
    assert box.audible_auth() is None


def test_audible_request_parameters_and_zero_duration(monkeypatch):
    import audible

    seen = []

    class RecordingClient(FakeClient):
        def get(self, path, **kwargs):
            seen.append((path, kwargs))
            return {"aggregated_monthly_listening_stats": [
                {"aggregated_sum": 0}, {"aggregated_sum": "0"},
            ]}

    monkeypatch.setattr(box, "audible_auth", lambda: object())
    monkeypatch.setattr(audible, "Client", RecordingClient)
    assert box.audible_listening_line() == "listened 0h 00m in 2026 on Audible"
    assert seen == [("1.0/stats/aggregates", {
        "monthly_listening_interval_duration": "12",
        "monthly_listening_interval_start_date": "2026-01",
        "store": "Audible",
    })]


def test_gist_update_validates_credentials(monkeypatch):
    monkeypatch.setattr(box, "GH_TOKEN", "")
    monkeypatch.setattr(box, "GIST_ID", "")
    with pytest.raises(ValueError, match="required"):
        box.update_gist("body")


@pytest.fixture
def fake_github(monkeypatch):
    from types import SimpleNamespace

    state = SimpleNamespace(
        files={"latest reads": SimpleNamespace(content="before")},
        writes=[], reads=0, closed=False, mismatch=False,
    )

    class Gist:
        @property
        def files(self):
            return state.files

        def edit(self, *, files):
            state.writes.append(files)
            if not state.mismatch:
                state.files = {name: SimpleNamespace(content=value.content)
                               for name, value in files.items()}

    class Client:
        def __init__(self, *, auth):
            assert auth.token == "fake-token"

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            state.closed = True

        def get_gist(self, gist_id):
            assert gist_id == "test-gist"
            state.reads += 1
            return Gist()

    monkeypatch.setattr(box, "GH_TOKEN", "fake-token")
    monkeypatch.setattr(box, "GIST_ID", "test-gist")
    monkeypatch.setattr(box, "Github", Client)
    monkeypatch.setattr(box, "InputFileContent", lambda content: SimpleNamespace(content=content))
    return state


def test_gist_write_is_verified_and_client_closed(fake_github):
    box.update_gist("expected body")
    assert fake_github.reads == 2
    assert len(fake_github.writes) == 1
    assert fake_github.files["latest reads"].content == "expected body"
    assert fake_github.closed


def test_unchanged_gist_is_not_rewritten(fake_github):
    box.update_gist("before")
    assert not fake_github.writes
    assert fake_github.reads == 1 and fake_github.closed


def test_wrong_gist_readback_fails_without_retrying_write(fake_github):
    fake_github.mismatch = True
    with pytest.raises(RuntimeError, match="readback"):
        box.update_gist("expected body")
    assert len(fake_github.writes) == 1 and fake_github.closed


@pytest.mark.parametrize("filenames", [[], ["one", "two"]])
def test_ambiguous_gist_is_not_modified(fake_github, filenames):
    fake_github.files = dict.fromkeys(filenames)
    with pytest.raises(ValueError, match="exactly one file"):
        box.update_gist("expected body")
    assert not fake_github.writes and fake_github.closed


def test_optional_listening_footer_is_included(monkeypatch):
    monkeypatch.setattr(box, "audible_listening_line", lambda: "listened 1h 02m in 2026 on Audible")
    assert box.build_body().endswith(
        "read 3 of 12 books in 2026\nlistened 1h 02m in 2026 on Audible"
    )


def test_command_line_entry_point(monkeypatch, capsys):
    import runpy

    monkeypatch.setenv("INPUT_CSV_PATH", box.CSV_PATH)
    monkeypatch.setenv("INPUT_DRY_RUN", "true")
    with pytest.raises(SystemExit) as result:
        runpy.run_path(box.__file__, run_name="__main__")
    assert result.value.code == 0
    assert capsys.readouterr().out.startswith("latest reads\n\n")
