# storygraph-box

Update a pinned gist with your latest StoryGraph reads, listens and Audible listening time, in plain text.

📚 A pinned-gist tool for the post-Goodreads era. book-box died with the Goodreads API in December 2020. This one runs on the official StoryGraph CSV export, no scraping, no Cloudflare fights, plus optional Audible listening stats from Audible's internal API via [mkb79/Audible](https://github.com/mkb79/Audible).

Sample output, the actual pinned gist of the author.

```
latest reads
Recently read:
Dicţionar englez-român român-englez: pentru toţi by Georgeta Nichifor
Psihologia poporului român: profilul psihologic al românilor
într-o monografie cognitiv-experimentală by Daniel David
Sarmizegetusa, cuib de vulturi by David Sava
The Divine Comedy by Dante Alighieri

Recently listened:
Jurnal de razboi 1916-1918 - Maria, Regina Romaniei by Regina Maria

2026: 0/5 books
listened in 2026, 35h 28m on Audible
```

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
    steps:
      - uses: actions/checkout@v4
      - uses: YOUR_USERNAME/storygraph-box@main
        with:
          gist_id: YOUR_GIST_ID
          goal_books: '5'
        env:
          GH_TOKEN: ${{ secrets.GH_TOKEN }}
          AUDIBLE_AUTH: ${{ secrets.AUDIBLE_AUTH }}
```

2. Add the secrets `GH_TOKEN` and, if using Audible, `AUDIBLE_AUTH` (the base64-encoded auth file) in repo Settings, Secrets and variables, Actions.
3. Run the workflow once, then pin the gist on your profile.

Refresh the CSV export whenever you want fresh data, commit or upload the new file, and the gist updates on the next run. The daily cron keeps timestamps honest even when nothing changed.

## Inputs

| Input | Required | Default | What it does |
|---|---|---|---|
| `gist_id` | yes | | ID from your gist URL |
| `csv_path` | no | `storygraph_export.csv` | Path to the committed export |
| `wrap_width` | no | `50` | Book line wrap width, ashtom-style |
| `goal_books` | no | hidden | Yearly goal, renders `YYYY: done/N books` |
| `audible_locale` | no | `uk` | Your Audible marketplace code |

## Secrets

| Secret | Required | What it does |
|---|---|---|
| `GH_TOKEN` | yes | Token with the `gist` scope |
| `AUDIBLE_AUTH` | no | base64-encoded `audible` auth file for listening stats |

## Notes and honest limitations

- StoryGraph has no official API. This tool uses the official CSV export, which means one manual download per refresh. If StoryGraph ever ships an API, this becomes a ten-line change.
- The CSV export drops moods, pace and reading-journal stats. Blame the export, not the tool.
- Audible stats come from Audible's internal API through the `audible` package. It works today, it is unofficial, and a one-time external login is all it takes.

## Credits

- [ashtom](https://github.com/ashtom), whose pinned gists are the reason this exists, and whose `hadge` taught the whole pattern.
- [amorriscode/book-box](https://github.com/amorriscode/book-box) and [matchai/bird-box](https://github.com/matchai/bird-box), the lineage this follows.
- [kwacky1/book-stats](https://github.com/kwacky1/book-stats), prior art in the StoryGraph gist space.
- Part of the ecosystem in [awesome-pinned-gists](https://github.com/matchai/awesome-pinned-gists).

## License

MIT