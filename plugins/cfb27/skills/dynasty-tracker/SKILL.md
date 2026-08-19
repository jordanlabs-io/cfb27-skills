---
name: dynasty-tracker
description: Capture and retrieve the user's own College Football 27 dynasty/league saves in dynasties/. Use whenever the user dictates a dynasty update — "log my dynasty", "I played my dynasty", game results/scores, recruit commitments or signings, transfer-portal moves, injuries, awards, or recruiting-board changes — and whenever they ask for a scouting report ("prep me for <rival>"), a recruiting-fit question ("who should I target", "does <recruit> fit"), or a season-end archive ("archive my season", "start the next season"). This is personal save data, kept strictly separate from the transcript-sourced wiki.
---

# Dynasty Tracker

Track the user's real CFB 27 saves — roster, recruiting board, rival tendencies, season history — so Claude can strategize from durable knowledge of his actual dynasty, fused with the strategy `wiki/`. Data lives in `dynasties/<slug>/`. The payoff is **retrieval** (scouting reports, recruiting fits), not storage.

Active dynasties: **North Carolina** — the primary save (7-person online league; subject of the film-room, scouting-report, and newsletter pipelines) — plus **Stanford** and **Oregon State**. All three share one schema.

## Isolation invariant (non-negotiable)

`dynasties/` is personal save data. It **never** flows into `wiki/` — wiki pages are strictly synthesis of transcripts and must never cite or link to dynasty notes. The link is **one-directional**: dynasty notes MAY link into `wiki/` for strategy reference; `wiki/` never links back. `dynasties/` is also exempt from the transcript/wiki scripts and has its own tooling (below).

## Wikilink rule

Inside `dynasties/`, **always path-qualify links**: `[[dynasties/stanford/roster|Roster]]`, not `[[roster]]`. Fixed filenames (`roster.md`, `h2h.md`, `records.md`, `team-needs.md`, `_index.md`) repeat across dynasty folders, so bare links are ambiguous. Links **into** `wiki/` use the vault's normal bare filename style (`[[qb-recruiting]]`).

# Capture protocol

The user dumps whatever he remembers, in any order, however messy — often late at night, partial, out of sequence. Your job is to file it, not to interview.

- **Tolerate mess.** Parse the dump, file every fact you can place, and move on.
- **At most ONE clarifying question** per update, and only if something genuinely can't be filed without it. Never run an interview.
- **Loose ends.** Facts the user mentioned but couldn't fully specify (an OVR he doesn't remember, a recruit whose stars are unknown) go into the `## Loose ends` section of `_dynasty.md` — reconciled opportunistically next session, never blocking.
- **Reading a screen capture, not a dictation?** Menu screen-shares ("data dumps") have their own lane and a screen-by-screen guide — what each CFB 27 screen contains, which glyphs matter, and where every screen lands in this schema: `film-room` → `references/data-dump.md`. Use it instead of improvising; improvising is how one dump lost 80% of its frames.
- **Identify the dynasty first.** Every update must be filed to a specific dynasty. Multiple dynasties are live, so **default to North Carolina** when the user doesn't name one — it is the active save. If context points at another dynasty, or is genuinely ambiguous, **ask — never guess.**
- **Proof outranks derivation (user directive 2026-08-18).** A box score, stats screen, standings table, schedule result — any on-screen game readout — beats a value derived from film charting or reasoned out here. Always, without asking. On a conflict take the proof, and keep the superseded value **and its source** in the note so the reconciliation stays visible rather than looking like it never happened. Two *proofs* that disagree are a different case: record both, flag them, reconcile neither. See `film-room` → Source authority for the charting-side statement of the same rule.
- After any update session, **run `verify_dynasties.py`** (below) and report failures; don't silently "fix" data.

## Fan-out rules (one dictated event → all its homes, so nothing drifts)

Apply these verbatim. Each event has a fixed set of destination files:

- **Game result** → add a row to `seasons/<year>.md` results table. **If the opponent is a league member** (a human, has a `league/teams/<slug>.md` note), **also** add a row to that member's section in `league/h2h.md`. (Two places max — H2H lives only in the season log row and `h2h.md`; never a third tally.) CPU-opponent games live in the season log only.
- **Signing** (recruit commits/signs) → set the recruit note's `status: signed` **and** add a `roster.md` row for the player. Unknown `Archetype`/`OVR`/`Dev trait` → put `TBD` in the cell and drop a note in `## Loose ends`.
- **Injury / transfer out / position change** → update the player's `Status` / `Notes` cells in `roster.md`.
- **Award / accolade / program record** → append a dated entry to `records.md` (never resets).
- **Standings / conference table** → a **new** `league/standings/<year>-w<NN>.md` snapshot. Season logs and rival-team notes **link** to it (`[[dynasties/<slug>/league/standings/2027-w09|Week 9 standings]]`); they never restate the table. Same rule as H2H: one canonical home, never a second tally.
- **Coach level, points, abilities, facilities, NIL budget** → a **new** `coach-state/<year>-w<NN>.md` snapshot. `_dynasty.md` keeps the *plan* (the build you are working toward); the snapshot holds the *measured state*. Do not record live numbers in both.

# Schemas

Follow these exactly — the Bases views and `verify_dynasties.py` depend on the field names and enums. Sparse notes are fine; only `type`/`dynasty`/`season`/`source`/`name` are load-bearing on recruits. Never invent fields or enum values.

### `_dynasty.md` (hub)
```yaml
type: dynasty
team: "Stanford"
mode: online            # online | offline
league_name: ""         # user supplies
members: 3
current_season: 2027
started: 2026
tags: [type/dynasty, dynasty/stanford]
```
Body: league-members table (person → team), all-time record line, path-qualified links to roster/recruiting/league/seasons/records, and a `## Loose ends` section.

### Recruit — `recruiting/high-school/<slug>.md`, `recruiting/portal/<slug>.md`
```yaml
type: recruit
dynasty: stanford
season: 2027            # the season DURING WHICH the cycle runs, not the signing
                        # class year — set at creation, never changes
source: high-school     # high-school | portal
name: "John Smith"
position: OT
stars: 4
state: TX
status: targeting       # targeting | committed | signed | flipped | lost
priority: high          # high | medium | low
archived: false         # set true only on archive copies, by the script

# --- board intel: all optional, all queryable. Fill what the screen shows. ---
board_status: open      # open | top5 | top3 | verbal | committed | unknown
lock: none              # none | locked | locked-out | dealbreaker | unknown
nat_rank: 14            # national / position / state rank, as integers
pos_rank: 5
state_rank: 1
nil_value: 235          # expected NIL
offer: 0                # NIL you have actually offered; 0 = none extended
interest_rank: 1        # your ordinal in his interest list, if shown
hours: 50               # recruiting hours committed this week
favorited: false        # star glyph on the board row

# --- the race: where you actually stand in his top-schools list ---
unc_standing: leader    # leader | top3 | top5 | listed | absent | unknown
                        # (derived label; race_rank is the hard number)
race_rank: 2            # YOUR row number in his Top Schools table
race_size: 9            # how many schools that table lists
race_cutoff: 5          # row where the "Projected Cutoff" divider sits;
                        # race_rank > race_cutoff means you are projected to lose him
dealbreaker: "Conference Prestige"   # the Dealbreaker panel, verbatim
dealbreaker_have: "A-"
dealbreaker_need: "C+"

# --- physical / visual card data ---
archetype: "Dual Threat"
hometown: "Wichita, KS"
height_in: 73
weight_lb: 202
p_tier: 5               # YOUR "P TIER" value in his Top Schools row — int 1-5, see below

# --- scouted reveals: ONLY from the recruit card's Scouting tab ---
scouting_pct: 0         # 0-100, the "Scouting (N%)" sub-tab label
scout_grade: unknown    # gem | normal | bust | unknown
ovr: 0                  # revealed OVR; 0 = not revealed
```

**The race lives in `recruiting/races.csv`, not in YAML.** One row per (recruit, school), so the whole board's competitive picture is one query:

```
season,recruit,rank,school,influence,trend,offer,visit,p_tier,mult,below_cutoff,locked_out,source_frame
2027,tim-natson,2,North Carolina,,,false,false,6,,false,false,f_1747
```

`recruit` is the note slug. `trend` is `up`/`down`/blank (the green/red arrows). `below_cutoff` / `locked_out` mark rows under the "Projected Cutoff" and "Locked Out" dividers. The recruit note's body links to it and quotes only its own rows; the frontmatter carries the three scalars you filter on (`race_rank`, `race_size`, `race_cutoff`).

**`scout_grade` reads the gem icon on the prospect card, not the Scouting tab.** Directly under the portrait, a recruit card stacks small icons: a favourited star, the crossed-out-handshake dealbreaker flag, and — on some players — a **green gem**. That gem is the scouting reveal.

- `gem` — green gem present.
- `normal` — `scouting_pct: 100` and no gem drawn. Verified as a real per-player difference, not a screen that hides it: at `Scouting (100%)` Greg Eddy (f_1766) shows the gem and Emanuel Anchrum (f_1795) shows only the dealbreaker flag.
- `unknown` — no card opened, or scouting below 100%. An unscouted player has nothing to show.
- `bust` — **the enum carries it; this capture never produced one.** No bust glyph has been observed on any card. Do not infer `bust` from the absence of a gem — that is what `normal` is for, and `normal` here means "fully scouted, no gem", not "confirmed not a bust."

Two decoys sit on the same screen: the top-right HUD currency chips are gem-shaped too (blue/teal 335, orange/red 10) and are currency, not scouting; the crossed-out handshake is the dealbreaker flag.

`ovr` is a different matter — no recruit card in this capture showed one, at any scouting level. Leave it `0` until a screen produces it.

**`p_tier` is pipeline strength (user-confirmed 2026-08-18).** The Top Schools table has a column headed `P TIER`, one coloured map-pin per school with a character inside; the same glyph sits beside hometowns on player and recruit cards. The user confirms the recruiting board reads out **pipeline strength** among the card's fields, so `P TIER` is that value: how strong a given school's pipeline is into that recruit's hometown, and your own row's value is the one that matters to you.

**Values are `1`-`5` and nothing else** (5 strongest), corroborated by
`dynasties/_wiki/recruiting/pipelines.md`, which documents the game's five pipeline tiers and each
school's regions. Store it as an **integer**, or `unknown` if the pin is unreadable.

This corrects an earlier reading. Values `6 8 9 B S` were recorded from the 2027 Week 9 capture and
carried here as "store it as a string, the ordering is not known" — all 22 were misreads of the
magenta `5` pin, confirmed against the frames rank-by-rank. Read the pin's **colour** first
(bronze 1, silver 2, gold 3, teal 4, magenta 5); the digit is unreliable at that size. Keep the
field named for the screen (`p_tier`), and reject anything outside 1-5 at capture time rather than
storing it.

**Why these are frontmatter and not prose.** The Bases views query frontmatter only. A recruit note whose ranks, NIL and board status live in the body renders as an almost-empty row on the live board — the data is *stored* but not *usable*. Anything you would ever sort or filter a board by belongs up here; narrative (top-schools list, visit history, why he fits) belongs in the body.

**Every enum carries `unknown` on purpose.** A screen you did not read must never force a guess — file `unknown` and drop a line in `## Loose ends`. This is the schema-level expression of the capture protocol's "unknown beats a guess."

### Rival team — `league/teams/<slug>.md`
```yaml
type: rival-team
dynasty: stanford
team: "Oregon"
controlled_by: "Mike"
```
**No `h2h_record` field** — H2H lives only in the season log + `h2h.md`. Body: scheme/tendency notes, roster intel, memorable games.

### Season log — `seasons/<year>.md`
```yaml
type: season
dynasty: stanford
year: 2027
record: ""              # e.g. "8-2" — fill as the season progresses
postseason: ""          # e.g. "Won National Championship"
```
Body: results table `Week | Opponent | H/A | W/L | Score | Notes` (CPU opponents live here only), then freeform narrative.

### Standings snapshot — `league/standings/<year>-w<NN>.md`
```yaml
type: standings
dynasty: stanford
season: 2027
week: 9
conference: "SEC"
```
Body: one table — `Team | W-L | Conf | PF | PA | Diff | MOV | Home`, plus any ranking shown.

**One file per capture, never a mutable current-standings file.** Snapshots are how you get a time series: without them a capture overwrites the last one and every week-over-week delta is lost. The same reasoning as `records.md` being append-only.

### Coach + program state — `coach-state/<year>-w<NN>.md`
```yaml
type: coach-state
dynasty: stanford
season: 2027
week: 9
level: 15
skill_points: 335
gold: 10
prestige: "C+"
job_security: "Safe"
archetype: "Motivator"
career_record: "14-7"
```
Body: purchased abilities per tree, coordinator cards, facility tiers and slots, NIL budget split.

**Also one file per capture.** This exists because state drifts silently — a level 14 → 15 bump or a gold 30 → 10 spend is invisible unless both sides are on disk.

### Plain-markdown files (no per-entity frontmatter)
- **`roster.md`** — one table: `Name | Pos | Class | Archetype | OVR | Dev trait | Status | Notes`. Persistent; players age up at archive (the script does it), never cleared.
- **`team-needs.md`** — a `##` section per position group with a priority line + notes. Reset from template at archive.
- **`records.md`** — sections: Player awards, Team/program records, Milestones. Dated, append-only.
- **`h2h.md`** — a `##` section per league member: a running tally line + table `Season | Week | W/L | Score | Notes`.

# Retrieval workflows (the payoff)

### 1. Scouting report — "prep me for Mike" / "prep me for the Oregon game"

**For a full written matchup brief or game-plan document (own game, or helping another league member), hand off to the `scouting-report` skill** — it owns the report format, the intel-protection rules, and the branded PDF. The quick fusion below is for in-chat prep only. Fuse, for the named rival:
- their `league/teams/<slug>.md` (scheme, tendencies, roster intel),
- the H2H history from `league/h2h.md`,
- your own `roster.md` — matchup gaps and depth concerns,
- **relevant strategy from `wiki/gameplay/*` and `wiki/dynasty/*`.**

When you pull a strategy claim from a wiki page, **carry its citation through** in the vault's standard format — `([[<transcript-filename>|Short Title]] **[MM:SS]**)`. Wiki pages already carry these citations on every claim; copy the citation with the claim so the scouting report stays traceable to the source video. Do **not** fabricate citations and do **not** cite dynasty notes.

### 2. Recruiting fit — "who should I target" / "does this WR fit"
Combine `recruiting/team-needs.md` (where the holes are) + the live recruiting board (`recruiting/high-school/`, `recruiting/portal/`, `archived != true`) + the relevant `wiki/dynasty/` recruiting pages (e.g. `[[qb-recruiting]]`, `[[ol-recruiting]]`). Same citation rule when quoting wiki strategy.

### 3. Season retrospective
Generated at archive time from the finalized season log + `records.md` — a narrative recap of the year. Produced as part of the season-end ritual, not ad hoc.

# Season-end ritual

When the user finishes a season and wants to roll to the next, **run the script — never archive by hand:**

```bash
python3 "<skill-base-dir>/scripts/archive_season.py" <dynasty-slug> <year>
```

(`<skill-base-dir>` = this skill's base directory, announced when the skill loads; quote it — the path may contain spaces.) The script runs three preflight checks and aborts with a report if any fail:
1. every `status: signed` recruit appears in `roster.md`;
2. every recruit has a terminal status (`signed|flipped|lost`) — non-terminal stragglers abort unless you pass `--allow-stragglers`;
3. `seasons/<year>.md` exists with a non-empty `record`.

On success it snapshots roster + recruiting into `archive/<year>/` (with `archived: true` on the copies), generates `league-snapshot.md`, clears the live recruiting boards, resets `team-needs.md`, ages roster classes (FR→SO→JR→SR; graduating SRs get `Status: review` — you confirm graduated/drafted, the script never deletes), bumps `current_season`, and creates next year's season log. Use `--dry-run` first to preview. Fix any preflight failure in the data (e.g. add the missing signed recruit to the roster), then re-run — don't work around the script.

# Verify after every update

```bash
python3 "<skill-base-dir>/scripts/verify_dynasties.py" .
```

Checks enum validity, that each `dynasty:` field matches its folder, `season`/`year` are ints, roster/h2h/season tables are well-formed, path-qualified wikilinks resolve, and archive flags are correct (live recruiting never `archived: true`; archive copies always). Exit 0 = clean, 1 = problems. **Report failures to the user; do not silently fix data.** (If `dynasties/` doesn't exist yet, it exits 0 with a note.)
