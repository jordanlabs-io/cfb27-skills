---
name: dynasty-bootstrap
description: Bootstrap a new CFB 27 dynasty in this vault by importing the team's full roster from cfblabs.com. Use whenever the user starts a new dynasty, says "import the roster for <team>", "set up my <team> dynasty", "scrape the <team> roster", or wants player ratings from CFB Labs pulled into dynasties/. Creates the complete dynasties/<slug>/ folder (roster.csv with all ~55 ratings, roster.md, team-needs, hub, season file, .base files) per dynasty-tracker conventions. NOT for updating an existing dynasty's roster mid-save (in-game changes diverge from the site) — that's manual dynasty-tracker capture.
---

# Dynasty Bootstrap — CFB Labs roster import

Import a team's release-week roster from cfblabs.com and scaffold a new dynasty folder in one step. This is the "day zero" ritual for every new dynasty; after it runs, normal dynasty-tracker capture takes over.

## How the data works (why no browser is needed)

cfblabs.com is server-rendered Next.js. The team page (`/teams/<slug>`) embeds the **complete** roster as JSON (`"allPlayers":[...]` — every player with all ~55 ratings, abilities, class, hometown). Each player detail page embeds the same object in `__NEXT_DATA__` and adds only a refined position label (e.g. `QB (Right)`). So a plain HTTP fetch gets everything; the bundled script still fetches each player page to capture that refined position. **The site publishes no archetype or dev trait** — those land as `TBD` and get a Loose-ends entry to fill from in-game screens.

## Workflow

1. **Get the team slug.** It's the cfblabs URL slug (`oregon-state`, `mississippi-state`) — `lower-kebab-case` of the school name. The authoritative list is the sitemap: `curl -sL https://www.cfblabs.com/sitemap-0.xml | grep -oE '/teams/[a-z0-9-]+' | sort -u` (136 teams). Beware: **some teams exist on the site but have empty rosters** (Mississippi State and Washington State as of 2026-07 — `totalCount: 0` in the site's own data). The script detects this and exits with an explanation; the fallback is manual roster capture from in-game screens.

2. **Run the script** from the vault root (path has a space — quote it):

   ```bash
   python3 "<skill-base-dir>/scripts/bootstrap_dynasty.py" <slug> --season <year>
   ```

   It scrapes (~85 pages, ~30s at the default 0.3s delay) and writes the whole `dynasties/<slug>/` folder: `roster.csv`, `roster.md`, `records.md`, `_dynasty.md`, `recruiting/team-needs.md`, `league/h2h.md`, `seasons/<year>.md`, `League.base`, `Recruiting.base`. It refuses to overwrite an existing dynasty without `--force`. Read its output: it reports player count, missing OVRs, and any per-player fetch failures — treat any warning as a problem to resolve, not a footnote.

3. **Fill in what the script can't know.** The generated `_dynasty.md` defaults to `mode: offline`, `members: 1`, empty `league_name`, marked as such in `## Loose ends`. Ask the user (or use what they already said) whether this is an online league and who's in it; update the frontmatter, the League members table, and remove the corresponding Loose-ends line. If it stays a solo offline save, just remove that Loose-ends line after confirming.

4. **Add the dynasty to `dynasties/_index.md`** — one bullet matching the existing entries' style (team, mode, import date, live season).

5. **Verify** (must pass before reporting success):

   ```bash
   python3 "<dynasty-tracker-skill-dir>/scripts/verify_dynasties.py" .   # dynasty-tracker skill, sibling of this one
   ```

   Also spot-check 2–3 players in `roster.csv` against the live site (OVR + one skill rating each) — this catches payload-shape drift that the script would silently mis-parse.

6. **Log it** to `operations/activity-log/YYYY-MM-DD.md` per /log conventions.

## If the scrape breaks

The script depends on two payload landmarks: `"allPlayers":` on the team page and the `__NEXT_DATA__` script tag on player pages. If either is missing, the site layout changed. Don't patch blindly: `curl` the team page, find where the roster JSON now lives (search for a known player's name), and update the extraction in `scripts/bootstrap_dynasty.py` — the rest of the file-generation logic is independent of the fetch. If the data is no longer server-embedded at all, fall back to the `/aside-browser` skill to read the rendered page.

## Boundaries

- `dynasties/` data never flows into `wiki/` and wiki pages never cite it — same invariant as always.
- Season rollover is `archive_season.py` (dynasty-tracker), never this skill and never by hand.
- Roster updates after the save is live come from the user's in-game reports, not re-scraping — the site reflects release-week rosters only.
