from pathlib import Path

import pytest

import storygraph_box as box


@pytest.fixture(autouse=True)
def settings(monkeypatch):
    monkeypatch.setattr(box, "CSV_PATH", str(Path(__file__).with_name("sample_export.csv")))
    monkeypatch.setattr(box, "WRAP_WIDTH", 0)
    monkeypatch.setattr(box, "TITLE_MAX", 0)
    monkeypatch.setattr(box, "GOAL_BOOKS", "12")
    monkeypatch.setattr(box, "OUTPUT_STYLE", "compact")
    monkeypatch.setattr(box, "current_year", lambda: 2026)
    monkeypatch.setattr(box, "audible_listening_line", lambda: None)


def test_compact_parallel_reading_is_not_truncated(monkeypatch):
    rows = box.load_rows()
    rows.extend({"Title": f"Parallel {n}", "Read Status": "currently-reading"} for n in range(3))
    monkeypatch.setattr(box, "load_rows", lambda: rows)
    body = box.build_body()
    assert "📖 Reading: The Name of the Wind by Patrick Rothfuss" in body
    assert body.count("📚 Also reading:") == 3
    assert "🏁 Last read: Project Hail Mary by Andy Weir" in body
    assert "🎧 Audio: Dune by Frank Herbert" in body
    assert "📅 2026: 3/12 books" in body
    assert "📊 Export: 6 finished books" in body
    assert "pages" not in body and "Infinite Jest" not in body


def test_compact_empty_is_an_explicit_export_count(monkeypatch):
    monkeypatch.setattr(box, "load_rows", list)
    monkeypatch.setattr(box, "GOAL_BOOKS", "")
    assert box.build_body() == "📅 2026: 0 books\n📊 Export: 0 finished books"


def test_compact_includes_audible_when_available(monkeypatch):
    monkeypatch.setattr(box, "audible_listening_line", lambda: "listened 1h 02m in 2026 on Audible")
    assert box.build_body().endswith("⏱️ listened 1h 02m in 2026 on Audible")


def test_documented_compact_example_matches_renderer(monkeypatch):
    monkeypatch.setattr(box, "audible_listening_line", lambda: "listened 18h 05m in 2026 on Audible")
    readme = Path(box.__file__).with_name("README.md").read_text(encoding="utf-8")
    sample = readme.split("### Compact summary")[1].split("```text\n")[1].split("```")[0].rstrip("\n")
    assert box.build_body() == sample


def test_bad_output_style_never_writes(monkeypatch, capsys):
    monkeypatch.setattr(box, "OUTPUT_STYLE", "typo")
    monkeypatch.setattr(box, "update_gist", lambda _: pytest.fail("must not write"))
    assert box.main() == 1
    assert "output_style must be" in capsys.readouterr().err


@pytest.mark.parametrize("payload", [
    {}, {"aggregated_monthly_listening_stats": None},
    {"aggregated_monthly_listening_stats": {}},
    {"aggregated_monthly_listening_stats": [{}]},
    {"aggregated_monthly_listening_stats": [{"aggregated_sum": None}]},
    {"aggregated_monthly_listening_stats": [{"aggregated_sum": -1}]},
    {"aggregated_monthly_listening_stats": [{"aggregated_sum": "bad"}]},
])
def test_broken_stats_never_become_plausible_zero(payload, monkeypatch, capsys):
    import audible

    monkeypatch.undo()
    monkeypatch.setattr(box, "audible_auth", lambda: object())

    class Client:
        def __init__(self, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def get(self, *args, **kwargs):
            return payload

    monkeypatch.setattr(audible, "Client", Client)
    assert box.audible_listening_line() is None
    assert "Audible stats unavailable" in capsys.readouterr().err
