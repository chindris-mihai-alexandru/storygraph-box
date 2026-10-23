# storygraph-box

![CI](https://github.com/chindris-mihai-alexandru/storygraph-box/actions/workflows/ci.yml/badge.svg)
![Release](https://img.shields.io/github/v/release/chindris-mihai-alexandru/storygraph-box)
![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)
![GitHub Actions](https://img.shields.io/badge/GitHub_Actions-2088FF?logo=githubactions&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-2496ED?logo=docker&logoColor=white)
[![License, MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

![storygraph-box banner](assets/banner.png)

Update a pinned gist with your latest StoryGraph reads, listens and Audible listening time, in plain text.

📚 A pinned-gist tool for the post-Goodreads era. book-box died with the Goodreads API in December 2020. This one runs on the official StoryGraph CSV export, no scraping, no Cloudflare fights, plus optional Audible listening stats from Audible's internal API via [mkb79/Audible](https://github.com/mkb79/Audible).

## Sample output

Fictional data, this block is documentation, not a live readout.

```
latest reads

Currently reading:
The Name of the Wind by Patrick Rothfuss

Recently read:
Project Hail Mary by Andy Weir
The Remains of the Day by Kazuo Ishiguro
Pride & Prejudice by Jane Austen
The Hobbit by J.R.R. Tolkien

Recently listened:
Dune by Frank Herbert
The Way of Kings by Brandon Sanderson

read 3 of 12 books in 2026
listened 18h 05m in 2026 on Audible
```

Books you are reading right now get their own section, finished books are split into read and listened by their StoryGraph format, and the footer carries your yearly reading goal and Audible listening time. To-read and did-not-finish books are left out on purpose.

## Setup

### Prep work

1. Create a new public GitHub Gist. The first file name becomes the gist header, so use something like `latest reads` with no extension. Extensionless files render as plain text, which keeps the layout vertical.
2. Create a token with the `gist` scope (github.com/settings/tokens/new).
3. In StoryGraph, user menu, Manage Account, Export Library. Download the CSV when the email arrives.
4. Optional, for the Audible line, do a one-time login with the `audible` package (`Authenticator.from_login_external`) and base64-encode the resulting auth file.

### Project setup

1. Create a private repo and commit the CSV export as `storygraph_export.csv`, plus this workflow at `.github/workflows/schedule.yml`

```yaml
name: Update reads gist
on:
  schedule:
    - cron: '0 5 * * *'
  workflow_dispatch:
jobs:
  update-reads:
    runs-on: ubuntu-latest
    timeout-minutes: 10
    steps:
      - uses: actions/checkout@v4
      - uses: YOUR_USERNAME/storygraph-box@v1
        with:
          gist_id: YOUR_GIST_ID
          goal_books: '5'
        env:
          GH_TOKEN: ${{ secrets.GH_TOKEN }}
          AUDIBLE_AUTH: ${{ secrets.AUDIBLE_AUTH }}
```

Pin to `@v1` to receive fixes without surprises. `@main` follows unreleased commits.

2. Add the secrets `GH_TOKEN` and, if using Audible, `AUDIBLE_AUTH` (the base64-encoded auth file) in repo Settings, Secrets and variables, Actions.
3. Run the workflow once, then pin the gist on your profile.

Refresh the CSV export whenever you want fresh data, commit or upload the new file, and the gist updates on the next run. The daily cron keeps timestamps honest even when nothing changed.

## Inputs

| Input | Required | Default | What it does |
|---|---|---|---|
| `gist_id` | yes | | ID from your gist URL |
| `csv_path` | no | `storygraph_export.csv` | Path to the committed export |
| `wrap_width` | no | `50` | Book line wrap width, ashtom-style, `0` keeps one line per book |
| `title_max` | no | `0` | Drop a subtitle when a line is longer than this and the short form fits, so the pinned card does not clip it. About `52` suits the card, `0` keeps full titles |
| `goal_books` | no | hidden | Yearly goal, renders `read done of N books in YYYY` |
| `audible_locale` | no | `uk` | Your Audible marketplace code |
| `dry_run` | no | `false` | Print the rendered gist to the log and leave the gist alone, handy for previewing |

Malformed CSV rows, duplicate or empty headers and invalid UTF-8 stop the run before any gist write. The target must be a single-file gist. Unchanged content is not rewritten, and changed content is read back from GitHub before success is reported.

## Secrets

| Secret | Required | What it does |
|---|---|---|
| `GH_TOKEN` | yes | Token with the `gist` scope |
| `AUDIBLE_AUTH` | no | base64-encoded `audible` auth file for listening stats |
| `AUDIBLE_ADP_TOKEN` + `AUDIBLE_DEVICE_PRIVATE_KEY` | no | Alternative two-field Audible auth, same values the [setup-audible-cli](https://github.com/mkb79/setup-audible-cli) action uses |

Audible authentication takes either route. The full auth file is the simplest, while the two-field pattern keeps only the signing credentials in secrets and lets the runner build an ephemeral auth object. If both are present, the auth file wins.

## Run it from your own machine

The Action is optional. The same script runs anywhere with Python 3.12 and the pinned dependencies, which keeps your export out of git entirely. Your export holds your reviews and your whole library, so a public repository is the wrong place for it.

```
uv run --no-project --with-requirements requirements.txt python storygraph_box.py
```

Pass the same inputs as environment variables with an `INPUT_` prefix, for example `INPUT_CSV_PATH`, `INPUT_GIST_ID`, `INPUT_GOAL_BOOKS` and `INPUT_WRAP_WIDTH`, plus `GH_TOKEN` with the gist scope. Set `INPUT_DRY_RUN=true` to print the result instead of updating the gist.

## Keeping the export fresh

StoryGraph has no API, so the CSV has to come from the export page. When you press Generate export, the page shows a line like "Your export from 23 October 2026 - Download" after a minute or two. The Download link is a signed Google Cloud Storage address, so once you are logged in you can read the link from the page and fetch it with `curl`. StoryGraph sits behind Cloudflare, which tends to challenge datacenter addresses like GitHub's runners, so do the download from your own machine or an agent that drives your own browser.

The signed address expires within minutes and contains your signature, so do not log it or commit it.

## Notes and honest limitations

- StoryGraph has no official API. This tool uses the official CSV export, which means one manual download per refresh. An official API would need an adapter and compatibility tests before it could replace the export. Show your support on the official roadmap post, [An API](https://roadmap.thestorygraph.com/features/posts/an-api), open since 2021.
- Two other roadmap posts would close the remaining gaps if they ship. [Export your stats into CSV/Excel](https://roadmap.thestorygraph.com/requests-ideas/posts/export-your-stats-into-csv-excel) asks for reading journal data, which is what a progress bar would need, and the bug [Export mangles non-ASCII characters](https://roadmap.thestorygraph.com/bugs/posts/export-mangles-non-ascii-characters) can garble accented titles in the file.
- The export carries moods, pace, ratings, reviews, tags and read dates for every book, but no reading progress, journal entries or aggregate stats. That is why there is no progress bar here, a currently-reading book shows as a title only.
- Audible stats come from Audible's internal API through the `audible` package. It works today, it is unofficial, and a one-time external login is all it takes.

## Credits

- [ashtom](https://github.com/ashtom), whose pinned gists are the reason this exists, and whose `hadge` taught the whole pattern.
- [amorriscode/book-box](https://github.com/amorriscode/book-box) and [matchai/bird-box](https://github.com/matchai/bird-box), the lineage this follows.
- [kwacky1/book-stats](https://github.com/kwacky1/book-stats), prior art in the StoryGraph gist space.
- Part of the ecosystem in [awesome-pinned-gists](https://github.com/matchai/awesome-pinned-gists).

## License

MIT