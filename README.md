# cfb27-skills

A Claude Code plugin marketplace for **College Football 27** dynasty players.
One plugin, `cfb27`, carrying the full toolkit built for the Weef league vault:

| Skill | What it does |
| --- | --- |
| `film-room` | Ingest game film (Twitch VODs or iPad party-share recordings), chart every play like a pro scout, produce play CSVs + scout reports + rival call-sheet ledgers. |
| `dynasty-tracker` | Capture your dynasty saves (results, recruiting, rosters, H2H) into a verifiable vault schema; season-end archive ritual. |
| `dynasty-bootstrap` | Stand up a new dynasty folder from the schema. |
| `scouting-report` | Build "the book" on a league opponent — full matchup game plan + school-branded 2-page PDF brief, for your own game or to hand an ally. |
| `youtube-transcript-import` | Import creator video transcripts as timestamped, citeable ground truth; synthesize the strategy wiki. |
| `dynasty-newsletter` | Produce a branded newsletter issue recapping a dynasty game (Tarstool Sports is the bundled flagship profile). |
| `film-action-shot` | Photoreal, football-correct cinematic renders of charted plays via Higgsfield. |

## Install

```
/plugin marketplace add jordanlabs-io/cfb27-skills
/plugin install cfb27@cfb27-skills
```

## Requirements

These skills operate on a **CFB 27 knowledge vault** with this shape (see the
skills for details):

```
transcripts/   # verbatim, timestamped creator-video transcripts (ground truth)
wiki/          # cited synthesis of transcripts (strategy knowledge base)
dynasties/<slug>/   # your save data: roster, seasons, league/, film-room/
operations/activity-log/
```

Run `dynasty-bootstrap` to create a dynasty; `youtube-transcript-import` explains
the transcripts/wiki invariants. Some skills additionally use: a Python venv for
film tooling (`~/CFB27-film/.venv`), a Playwright-cached Chromium for PDF
rendering, the Apify actor `streamers/youtube-scraper` for transcript pulls, and
Higgsfield MCP for image generation.

## Notes

- If your project also carries these skills in `.claude/skills/` (the original
  vault layout), remove the project copies after installing the plugin to avoid
  duplicate skill listings.
- Menu-counter intel harvested from opponents' screens is sensitive by design —
  the `scouting-report` skill's intel-protection rule governs what may appear in
  documents handed to other league members.
