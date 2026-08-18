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

1. `ffmpeg` 1 fps → `frames/f_%04d.jpg` (full-res 1920×1080; the tier-1 downscale lives separately
   in `tier1/`). `f_0720.jpg` = second 719 → `[11:59]`.
2. dHash every frame on a **cropped** region that excludes the clock/ad overlay (`dhash.py`,
   `hashes_crop.tsv`), so an ad banner rotating doesn't make a static screen look "new".
3. Dedup greedily against a rolling window: drop a frame only if it is within ~3 bits of a frame
   already kept **within about 25 seconds**. A screen revisited five minutes later is new evidence
   (values may have changed) — do not dedup across the whole VOD.
4. Tier-1 classify the survivors → `chapters.json` (see `cm/PROMPT.md` shape).
5. Tier-2 transcribe **every survivor**, ~14 frames per agent, batched in **time order** so one
   agent sees a whole scroll and can merge it into one table.
6. Reconcile: for every category in `chapters.json`, assert transcribed == survivors. Any shortfall
   is a bug, not a judgement call.

## Reading the screens

Common to all of them: the top-right HUD (currency counters, LVL, Job Security), the header
`TEAM [W-L]`, the `L1`/`R1` tab strip with one tab active, an `L2` filter chip, and a footer button
legend. Those tell you *which* screen you are on and *what filter produced these rows* — a stats
table transcribed without its category chip is unusable.

### TEAM STATS
The season-cumulative statistics browser, and the biggest screen in any dump — 362 of 719 classified
frames in the 2027 dump. Tabs switch team-vs-player and the stat category. **The category chip is
load-bearing**: the same table shape means passing, rushing, receiving, defense, kicking or
returns depending on it. Long vertical scrolls, plus **horizontal** scrolls that move the column
window — when the NAME column scrolls off the left edge, row identity must come from unchanged row
order, and that has to be said out loud in the digest, not assumed.
→ `seasons/<year>-player-stats.csv`, `seasons/<year>-team-stats.csv`.

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

### RECRUITING — Recruiting Board
Split screen. **Left rail** = the board list: `# | NAME | ★ | POS | board_status | Int: Nth | NIL$`
plus glyphs — padlock (committed/locked), red crossed-out handshake (dealbreaker), star
(favorited), binoculars (scouting), document (offer extended). **Right panel** = the selected
prospect's card:

- Identity line: stars, `NAT: n | STA: n | POS: n` (POS is a *rank*, not the position).
- `POSITION | CLASS | HEIGHT & WEIGHT` and `ARCHETYPE | EXPECTED NIL | HOMETOWN`. A small map-pin
  glyph appears beside some hometowns and not others — record it, don't interpret it.
- Interest meter: a bar with `OPEN`, `TOP 5`, `TOP 3` markers. Say which markers the fill passes.
- Sub-tabs `Overview | Recruiting | Scouting (N%)` — **always record N.**
- **Top Schools = the recruiting race.** `# | SCHOOL | INFLUENCE | TOP 3/TOP 5 | OFFER | VISIT |
  P TIER | MULT`, with a `Projected Cutoff` divider and sometimes a `Locked Out` divider. Your own
  row number against the cutoff row is the single most useful number on the screen: rank 9 of 9
  with a cutoff at 5 means you are losing him regardless of how much interest shows.
- Right side: `Action Summary` (what you spent last week) and `Dealbreaker` with Have/Need grades.

→ `recruiting/high-school/<slug>.md` frontmatter + `recruiting/races.csv`.

**The Scouting tab is where gem/bust and OVR live, and only there.** Verified on a prospect sitting
at `Scouting (100%)`: the Recruiting tab still showed no grade and no OVR. If the dump never opens
that tab, every recruit is honestly `scout_grade: unknown` — say so and tell the user which tab to
open next time.

### RECRUITING — My School
Your program's grades (Playing Time, Academic Prestige, Coach Stability, Brand Exposure, Stadium
Atmosphere, Campus Lifestyle, Program Tradition, Playing Style) each with a national Top Schools
leaderboard showing your rank. The `Playing Style` tab is cycled per archetype with `R2` — each
archetype re-ranks the leaderboard, so one screen produces many distinct tables.
→ not yet schematized. Capture it; flag it in `## Loose ends`.

### PROGRAM OVERVIEW / FACILITY MANAGEMENT / SUPPORT STAFF
Dynasty-point allocation, the NIL budget split (roster vs recruiting, with the game's own suggested
percentages beside your actual ones), facility tiers as `n/4`, and staff cards.
→ `coach-state/<year>-w<NN>.md`.

### COACH STATS / COACH ABILITIES
Level, XP, prestige, contract goals with XP values and met/unmet state, and the ability trees
(`Recruiter`, `Motivator`, `Strategist`, `Scheme Guru`, …) with each node checked or unchecked.
→ level/points/goals to `coach-state/<year>-w<NN>.md`; the trees are **not yet schematized**.
