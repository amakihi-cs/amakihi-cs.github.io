# amakihi-cs.github.io

Website of the ʻAmakihi community survey (Wenaokeao: ESPaDOnS + SPIRou at CFHT),
served at <https://amakihi-cs.github.io>.

**This repository is public, and so is its whole history.** Never commit anything internal:
proposals, data, e-mails, member lists, the team password, or any wiki content in clear text.

| Path | What it is |
|---|---|
| `index.html`, `img/` | public presentation page (single HTML file, inline CSS, no JavaScript) |
| `publications.html` | publication page, generated from `tools/publications.json` |
| `team/index.html` | team pages: the private wiki compiled and encrypted with StatiCrypt (password protected) |
| `team/source.sha256` | hash of the clear team page, so that an unchanged wiki is not re-encrypted |
| `tools/` | the two page generators, their template, data and StatiCrypt salt |
| `.nojekyll` | serve the files as they are, without Jekyll |

GitHub Pages publishes `main` from the repository root.

## Team pages

The wiki lives in the private repository `eartigau/amakihi`
(<https://github.com/eartigau/amakihi/wiki>, collaborators only). A workflow there runs on every
wiki edit, every night and on demand: it checks out this repository and the wiki, runs
`tools/build_team_page.py`, and commits `team/` here when the wiki has changed. The team pages are
therefore up to date a minute or two after someone saves in the wiki.

To build them by hand (wiki cloned next to this repository, in `../amakihi.wiki`):

```
AMAKIHI_TEAM_PASSWORD=... python3 tools/build_team_page.py --preview /tmp/team.html
```

- The clear page only goes to `--preview`, which is refused inside this repository.
- `--force` re-encrypts even if the wiki has not changed (needed after a password change; old
  versions in the history stay readable with the old password).
- `--mailmap FILE` merges the names under which one person committed; that file holds e-mail
  addresses, so it is kept in the private repository.
- Keep `tools/staticrypt.json` (the salt): "Remember me" depends on it.
- Requires Python with `markdown`, and Node (`npx` fetches `staticrypt@3.5.4`).

## Publication page

`publications.html` has two parts: **ʻAmakihi** (survey papers, empty until observations start)
and **Background effort** (ESPaDOnS and SPIRou work since 2021, grouped by work package). To add
a paper, append `{"doi": "..."}` (or `{"arxiv": "..."}`) to the right list in
`tools/publications.json`, then run `python3 tools/build_publications.py --refresh`, which fills
in authors, title and journal from CrossRef, and commit both files. A paper with a `bibcode` gets
a direct ADS link; otherwise the ADS link is a search on its DOI.

## Photo credits

Both ʻamakihi photos are by Étienne Artigau (Macaulay Library
[ML22535891](https://macaulaylibrary.org/asset/22535891) and
[ML102747991](https://macaulaylibrary.org/asset/102747991)).
