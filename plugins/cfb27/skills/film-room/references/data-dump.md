# Lane C — data dump (menu screen-share)

A **data dump** is a VOD of the user paging through his own dynasty menus on purpose. It is not
game film: nobody is playing, there are usually no plays, and on a Twitch VOD there is often no
narration at all. Every frame is a UI screen, and **the screens are the entire payload.**

Triage signals: 16:9, own-stream URL, near-silent audio, and a tier-1 pass that comes back almost
entirely `team_stats` / `recruiting_board` / `standings` rather than `gameplay`.

## The failure this lane exists to prevent

The 2027 Week 9 dump (`2027-w9-datadump`, Twitch 2849880558, 33 min, 1999 frames) was first run
ad-hoc through the film pipeline. Result: **719 of 1999 frames were classified and only 374 were
ever transcribed.** 301 of 367 `team_stats` frames — the box scores and player stats — were never
read by anything. Nothing recorded that, so the vault looked finished. The user found the hole
himself, weeks later, by noticing stats he knew he had captured were missing.

Two rules come straight out of that:

1. **Sample nothing.** Film can be sampled because a play lasts seconds and repeats. A menu scroll
   cannot: every scroll position is different rows. Dedup by hash, never by stride.
2. **Write the coverage ledger into the capture `_index.md`** — frames total / classified /
   transcribed / dropped-as-duplicate. An uncounted gap is an invisible gap.

## Pipeline

Every step below is a script in this skill's `scripts/` directory, run with the film venv python.
Resolve them the way the vault's verification block does, so the path survives the workspace being
deleted:

```bash
SK=$(ls -d ~/.claude/plugins/cache/cfb27-skills/cfb27/*/skills | sort -V | tail -1)
```

1. `ffmpeg` 1 fps → `frames/f_%04d.jpg` (full-res 1920×1080; a downscaled copy goes to `tier1/`).
   `f_0720.jpg` is frame 720 = **second 719** → `[11:59]`.
2. `dhash.py hashes frames/ hashes_crop.tsv` — dHash on a **cropped** region excluding the animated
   background and the player card, so neither makes a static table look "new".
3. `dhash.py calib hashes_crop.tsv` — **do not skip.** Pick `--thresh` from the valley between the
   "same screen" and "screen changed" clusters. Taking the default blind is how a wrong crop
   degrades dedup silently.
4. `dhash.py dedupe hashes_crop.tsv dedupe.json --thresh 3 --window 25` — keep a frame unless it is
   within 3 bits of one already kept **within about 25 seconds**. A screen revisited five minutes
   later is new evidence (values may have changed) — never dedup across the whole VOD.
   **The `dedupe.json.keep` file it writes is the coverage contract.**
5. `dump_batches.py dedupe.json.keep cm/ --size 14` → tier-1 batches; classify with
   `dump-prompts/tier1-classify.md`; merge with `dump_chapters.py cm/ chapters.json`.
6. `dump_batches.py dedupe.json.keep t2/ --size 14` → tier-2 batches; transcribe **every one** with
   `dump-prompts/tier2-transcribe.md`.
7. `dump_reconcile.py --keep dedupe.json.keep --manifests 't2/*.txt' --frames frames/ --chapters
   chapters.json --markdown` — **the gate.** Survivors minus the union of every batch manifest must
   be empty, or it exits 1 and names the frames. `--markdown` emits the ledger table for `_index.md`.
   Re-run `dump_reconcile.py` after every wave and again before writing `_index.md`.
8. `dump-prompts/assemble-csv.md` → per-game CSVs, only after step 7 passes.

**The gate is a filename set-difference, not a per-category count.** Tier-1 classification covers a
subset of survivors (719 of 1,552 in the 2027 Week 9 dump), so any assertion keyed on
`chapters.json` categories is structurally blind to every unclassified survivor — it reports green
over exactly the hole this lane exists to catch.

**Produce the `.keep` file before transcribing, and transcribe exactly it.** The 2027 Week 9 capture
did not: its 1,552 transcribed frames were assembled operationally across two passes, and no
`(--thresh, --window)` pair reproduces that set (the closest is off by 188 frames). Its ledger
therefore records what was read without recording a decision anyone can re-derive. Later captures
should not repeat that — the `.keep` file is what makes coverage auditable instead of merely counted.

## Check a value space before trusting a reading

`dynasties/_wiki/` in the vault is canonical game knowledge scraped from CFB Labs, MaxPlaysCFB and
CollegeFootball.gg — enumerations and formulas that hold in every save. **Use it as a decoder while
transcribing, not just as strategy reading**, because a known value space turns an unreadable glyph
into a solvable one:

| Want to check | Page |
| --- | --- |
| What an icon means and which values it can hold | `screens/glyph-index.md` |
| The letter-grade ladder and impact weightings | `screens/grade-scale.md` |
| `P TIER` pin values, and each school's pipeline regions | `recruiting/pipelines.md` |
| The fourteen My School categories and their drivers | `recruiting/my-school-grades.md` |
| Coach leaderboard columns, per tab | `coach-progression/coach-stats-screen.md` |
| How many archetypes a position actually has | `player-development/ability-requirements.md` |
| Whether a trait name on a player card is real | `player-development/player-abilities.md` |
| Coach ability names, trees, tiers and point costs | `coach-progression/coach-abilities.md` |
| What gem/bust status changes | `recruiting/scouting-and-gems.md` |

This is how the `P TIER` error was caught: the pin was being transcribed as `6 8 9 B S`, and the
canonical page says pipelines have exactly five tiers. A reading outside the value space is a
misread, and it is only visible if you know the value space.

## Reading the screens

Common to all of them: the top-right HUD (currency counters, LVL, Job Security), the header
`TEAM [W-L]`, the `L1`/`R1` tab strip with one tab active, an `L2` filter chip, and a footer button
legend. Those tell you *which* screen you are on and *what filter produced these rows* — a stats
table transcribed without its category chip is unusable.

### Glyphs and identities that hold across screens

- **The person-silhouette glyph marks a human-controlled program.** It precedes the opponent logo on
  TEAM SCHEDULE and appears beside schools inside a recruit's Top Schools list. It is how you tell a
  league game from a CPU game without asking, and it settled which 2027 fixtures belonged in
  `league/h2h.md`.
- **The coloured map-pin is the pipeline glyph, and its value space is 1-5 — nothing else.**
  **Read the colour, not the digit**: bronze 1, silver 2, gold 3, teal 4, magenta 5. A magenta pin is
  always a `5`, and its stylised glyph is the most misread on any CFB27 screen — in the 2027 Week 9
  dump it came back as `6`, `8`, `9`, `B` and `S` across 22 rows and was never once right, while
  every 1-4 was correct. A reading outside 1-5 means you misread a 5. An unlit or black pin is `?`.
  Full colour table and every other in-table icon: `dynasties/_wiki/screens/glyph-index.md` — that
  page is the value-space reference, this one is the procedure. Do not restate its tables here.
- **`Total Yards = Total Offense + PR + KR`** on the box score, exactly, on every captured team-line.
  Use it as an arithmetic check on a scroll you suspect you misread — but if the check fails, suspect
  your transcription before you report a game bug.
- **A leaderboard stat is scoped to the position group being shown, not to the team.** On the My
  School Playing Style tab, Receptions reads 21 at HB, 43 at TE and 63 at WR on the same screen.
  A `0` is therefore usually real, not a render artifact: "QB - Pure Runner: 0 rushing YPG" is the
  quarterbacks' number on a team that rushes for 171 a game.

### TEAM STATS
The season-cumulative statistics browser, and the biggest screen in any dump — 362 of 719 classified
frames in the 2027 dump. Tabs switch team-vs-player and the stat category. **The category chip is
load-bearing**: the same table shape means passing, rushing, receiving, defense, kicking or
returns depending on it. Long vertical scrolls, plus **horizontal** scrolls that move the column
window — when the NAME column scrolls off the left edge, row identity must come from unchanged row
order, and that has to be said out loud in the digest, not assumed.
→ `seasons/<year>-player-stats.csv` (**long** format: `week,opponent,team,category,player,stat,value`
— each category has a different column set), `seasons/<year>-team-stats.csv` (**wide**: the team stat
set is identical every game).

### BOX SCORE
Per-game final. Quarter-by-quarter grid on top, then a two-column team-vs-team stat list. Scrolls
several screens deep; the bottom rows (penalties, T.O.P.) are the ones that get lost. In-game ad
overlays sit exactly where T.O.P. renders — mark obscured values `?`, never reconstruct them.
→ `seasons/<year>-team-stats.csv`, one row per team per game. **This is proof** (see Source
authority): it outranks anything charted from the film of the same game.

### TEAM SCHEDULE
Full slate with results and each opponent's record. Prints the **winner first** — "L 33-19" is a
19-33 loss. Also carries team OVR/OFF/DEF and combined opponent record. Scroll to the end: a
schedule read that stops early is how the Rutgers Week 12 fixture got denied in the first pass.
→ `seasons/<year>.md` results table.

### SCORES/SCHEDULES, CONFERENCE STANDINGS, LEAGUE HISTORY
League-wide results, the conference table, past champions and program-history rows.
→ `league/standings/<year>-w<NN>.md` (one snapshot per capture, never a mutable current file),
`league/h2h.md` for league-member games only.

**LEAGUE HISTORY is cumulative, not a weekly snapshot** — it goes to `league/history/`:
`champions.csv` (national + conference, one row per title), `season-<year>.csv` (final standings,
all teams). Its **Season History** tab for a *finished* year is the only screen that states a season's
final record, so it is what closes a season log whose last row was a mid-season standing. The
person-silhouette glyph on a team row marks a human-controlled program. Bowl results render as
logos, not text — transcribe the name only when the logo carries readable text, else `?`.

### RECRUITING — Recruiting Board
Split screen. **Left rail** = the board list: `# | NAME | ★ | POS | board_status | Int: Nth | NIL$`
plus glyphs — padlock (committed/locked), red crossed-out handshake (dealbreaker), star
(favorited), binoculars (scouting), document (offer extended). **Right panel** = the selected
prospect's card:

- Identity line: stars, `NAT: n | STA: n | POS: n` (POS is a *rank*, not the position).
- **`CLASS & NIL` on the card is the NIL you have OFFERED, not what he is asking.** The RECRUITS NIL
  board carries both as separate columns — `OFFER` (extended, 0 = none) and `NIL` (expected) — and the
  card shows the `OFFER` figure. Confirmed six times without a contradiction. Filing the card number as
  the expected NIL put four recruit notes' `nil_value` backwards. `offer` ← board `OFFER`;
  `nil_value` ← board `NIL`.
- `POSITION | CLASS | HEIGHT & WEIGHT` and `ARCHETYPE | EXPECTED NIL | HOMETOWN`. A coloured map-pin
  glyph sits beside some hometowns and not others, **with a character inside it** — the same glyph
  the `P TIER` column uses. Transcribe the character; zoom in rather than reporting "a pin".
- Interest meter: a bar with `OPEN`, `TOP 5`, `TOP 3` markers. Say which markers the fill passes.
- Sub-tabs `Overview | Recruiting | Scouting (N%)` — **always record N.**
- **Top Schools = the recruiting race.** `# | SCHOOL | INFLUENCE | TOP 3/TOP 5 | OFFER | VISIT |
  P TIER | MULT`, with a `Projected Cutoff` divider and sometimes a `Locked Out` divider. Your own
  row number against the cutoff row is the single most useful number on the screen: rank 9 of 9
  with a cutoff at 5 means you are losing him regardless of how much interest shows.
  `P TIER` is the pipeline column — a coloured pin per school holding **1-5 only**; read the colour
  (see the glyph table above), and treat any reading outside 1-5 as a misread magenta 5. Tier 5 is
  strongest. Cross-check a school's plausible tier against
  `dynasties/_wiki/recruiting/pipelines.md`, which carries the per-school region tiers.
- Right side: `Action Summary` (what you spent last week) and `Dealbreaker` with Have/Need grades.

→ `recruiting/high-school/<slug>.md` frontmatter + `recruiting/races.csv`.

**The gem is on the card, under the portrait.** A small icon stack sits below the player photo:
favourited star, crossed-out-handshake dealbreaker flag, and on some players a **green gem** — the
scouting reveal. Zoom in and report the stack explicitly; the first pass wrote "below-photo icons"
without saying which, and the gem was lost. Absence of the gem at `Scouting (100%)` is itself data
(the player is not a gem). No **bust** glyph has ever appeared in a capture — do not report one from
an absence. Beware two decoys: the HUD currency chips are also gem-shaped, and the crossed-out
handshake is the dealbreaker flag.

### RECRUITING — My School
Your program's grades (Playing Time, Academic Prestige, Coach Stability, Brand Exposure, Stadium
Atmosphere, Campus Lifestyle, Program Tradition, Playing Style) each with a national Top Schools
leaderboard showing your rank. The `Playing Style` tab is cycled per archetype with `R2` — each
archetype re-ranks the leaderboard, so one screen produces many distinct tables (42 archetypes
across 15 position groups in the 2027 dump).

Each grade names the factor it depends on, and each archetype names its "How to Improve" factor with
an impact weighting, your value, and your national rank + letter grade.
→ `recruiting/school-grades.csv` and `recruiting/playing-style.csv`.
**An archetype can carry more than one requirement** — QB Pocket Passer shows Offensive Pass Yards on
one frame and Points Per Game on another, both real — so cycle the tab slowly and treat any single
capture as a floor, not a complete list.

### PROGRAM OVERVIEW / FACILITY MANAGEMENT / SUPPORT STAFF
Dynasty-point allocation, the NIL budget split (roster vs recruiting, with the game's own suggested
percentages beside your actual ones), facility tiers as `n/4`, and staff cards.
→ `coach-state/<year>-w<NN>.md`.

### COACH STATS / COACH ABILITIES
Level, XP, prestige, contract goals with XP values and met/unmet state, and the ability trees
(`Recruiter`, `Motivator`, `Strategist`, `Scheme Guru`, …) with each node checked or unchecked.

**Two currency counters sit side by side in the HUD and mean different things.** The blue diamond is
**dynasty points** (the Staff / Facilities / NIL budget, labelled "DYNASTY POINTS BUDGET · n / N"); the
gold headset-diamond is **coach points**, and only coach points buy abilities. A capture that reads
them as one currency reasons wrongly about every spend — that is exactly how a 30 → 10 drop got
filed as "unrecorded" instead of "a 20-point ability purchase." Read the icon, not the position.

**The archetype wheel has 10 nodes; the ability catalog lists 13 trees.** They agree: 7 base
archetypes with 8-branch T1–T4 trees, 3 elite upgrades reached *through* a base node (Elite
Recruiter, Master Motivator, Scheme Guru), and 3 flat archetypes with no branch grid (CEO, Rainmaker,
Visionary). Branch grids are always the same 2×4 order — QB, RB/FB, WR/TE, OL / DL, LB, DB, K/P — so a
slot's position identifies it even when its icon does not.

**Record the `n/4` badge per branch, and say which coach's tab was active.** The wheel has a "Toggle
Other Coaches" setting, so a tree opened from a coordinator tab may not be that coordinator's; if the
frame does not establish the owner, say so rather than assigning it.

→ level / points / goals / facilities to `coach-state/<year>-w<NN>.md`; the branch grids to
`coach-state/<year>-w<NN>-abilities.csv` (`coach,role,tree,branch,tier,ability,cost,owned,source_frame`),
joined against `dynasties/_wiki/coach-progression/coach-abilities.md` for names and costs; the league
leaderboard to `league/coach-stats/<year>-w<NN>.md` + `.csv`. Structure and its known conflicts:
`dynasties/_wiki/coach-progression/ability-trees.md`.
