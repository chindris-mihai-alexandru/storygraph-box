# Changelog

All notable changes are listed here, newest first. The release workflow publishes the section matching a pushed tag as the release notes, so every version needs one.

## [Unreleased]

## [1.2.0] - 2026-10-24

### Added
- Optional `compact` output with emoji labels, every parallel current read, latest print and audio finishes, and a clearly scoped finished-book count from the export. Classic output remains the default.
- A model-free monthly sync monitor that can run from an internal-disk installation with only a verified-success timestamp. It persists overdue alerts, retries failed notifications and avoids overlapping checks.

### Fixed
- Invalid or incomplete Audible responses no longer render as plausible zero listening time.
- Test configuration is reset for every test without leaking changes into the caller's environment.

### Verification
- Branch coverage now includes both the renderer and the monitor, with a 100% gate. CI tests Python 3.12 and 3.14 with read-only repository permissions.
- An intentionally incomplete run fails the coverage gate, and the full suite passes in reverse order.

## [1.1.1] - 2026-10-24

### Fixed
- Reject malformed CSV rows, duplicate or empty headers and invalid UTF-8 before updating a gist. Quoted multiline reviews remain supported.
- Normalize embedded whitespace in titles and authors and keep a single blank line before an audio-only section.
- Verify gist content after a write, skip unchanged content and reject ambiguous multi-file targets.
- Treat optional Audible auth-file write failures as warnings.

### Tests
- CI and releases require 100% line and branch coverage of `storygraph_box.py`. The 75-test suite includes the command-line entry point, malformed input and gist API boundaries.
- Six representative regressions were injected in memory and caught by the tests, without changing the working copy.

## [1.1.0] - 2026-10-24

### Added
- `title_max` input. When a line is longer than the limit and cutting after the first `: ` makes it fit, the subtitle is dropped. A line that already fits, or one that would still be too long, keeps its full title. The pinned card clips near 55 characters, so about 52 keeps every visible line whole. It is off by default.

## [1.0.4] - 2026-10-24

### Added
- `CHANGELOG.md` and a release workflow. Pushing a `vX.Y.Z` tag now runs the tests, publishes the release from the matching changelog section and moves the floating `vX` tag. A tag with a suffix such as `v1.1.0-rc1` becomes a prerelease and leaves `v1` alone.
- README section on keeping the export fresh and on running the tool from your own machine.

## [1.0.3] - 2026-10-23

### Changed
- Dependencies are pinned. `requirements.in` compiles to `requirements.txt`, which the Docker image and CI both install. Dependabot proposes the bumps.
- CI runs weekly and has an audit job that runs `pip-audit` on the pinned set.
- A Read Status the tool does not recognise is reported on stderr with its row count instead of being dropped silently.

## [1.0.2] - 2026-10-23

### Fixed
- A wrong `csv_path` wrote a placeholder over the real gist. A missing file, or a CSV without the Title and Read Status columns, now stops the run with an error and leaves the gist untouched.
- A malformed Audible secret crashed the whole run. It now degrades to a stderr warning like every other Audible failure.
- The goal line and the tests hard-coded the year. A test now covers 1 January, when the goal restarts.

### Added
- `dry_run` input, prints the rendered gist to the log without touching the gist.
- A CI job that builds the Docker image and runs it from a consumer-shaped workspace.

## [1.0.1] - 2026-10-23

### Fixed
- A currently-reading book rendered a bogus 0% progress bar. StoryGraph exports carry no progress column, so the bar is removed and the book shows as a title only.
- Statuses are normalised, so `currently-reading`, `currently reading` and `did-not-finish` all behave the same. To-read and did-not-finish books are left out on purpose.
- HTML entities in titles and authors are unescaped. A real export contains `&amp;` in an author field.

### Changed
- The README no longer claims the export drops moods and pace. It carries both. It lacks reading progress, journal entries and aggregate stats.

## [1.0.0] - 2026-10-22

### Added
- First public release. Renders a StoryGraph CSV export into a pinned gist in the layout of ashtom's book-box, with optional Audible listening time.
