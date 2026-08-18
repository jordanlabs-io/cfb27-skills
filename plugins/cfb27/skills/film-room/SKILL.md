---
name: film-room
description: Ingest CFB 27 game film, chart every play like a professional scout, and produce a play-by-play CSV + scout report filed in the dynasty's film-room folder, plus rival dossier updates. Handles BOTH input types — Twitch VOD links of the user's own games AND iPad screen recordings of opponents' games (silent share-screen captures from the PlayStation party, including damaged/multi-file recordings). Use whenever the user drops a Twitch link, drops one or more .mp4/.mov screen recordings, says "ingest this game", "film room", "chart this game", "scout this film", mentions recording an opponent's game, or wants opponent tendencies from any game footage. Ends by archiving originals to Google Drive (md5-verified) and freeing local storage.
---

# Film Room — game film ingestion pipeline

Spec: `docs/superpowers/specs/2026-07-22-film-room-design.md`. Calibrated 2026-07-22 (OSU-UMD, 185 plays); caller-screen lane proven 2026-07-30 (KSU-WVU 95 + UMD-ARI 132 plays); HUD/possession/splits fixes 2026-08-05 (UNC-VAND, 116 windows, possession hand-verified). History and superseded decisions: `references/calibration-history.md`.

## Input triage — decide the lane FIRST

Two lanes, split by whose game it is. Everything downstream branches on this.

| Concern | **Lane A: my games (Twitch)** | **Lane B: opponent games (iPad party-share)** |
| --- | --- | --- |
| Source | Twitch VOD link (own stream) | Screen recording(s) dropped from iPad — shared screen in the PS party |
| Geometry | 16:9, use as-is | iPad 4:3 (2732×2048) — crop+scale to 1920×1080 first |
| Container | healthy | may be moov-less (interrupted transfer) → untrunc repair |
| Audio | commentary/mic → transcribe | silent → skip transcription entirely |
| Results/yards | transcript adjudication (step 7) | HUD-delta adjudication (step 7b) |
| HUD OCR | tesseract usually fine | soft scorebugs — expect collapse; Claude-sheet rescue at <50% dd |
| Formations | banner OCR ground truth | banner present but tesseract-garbled → vision agents read it |
| Menus | not visible | play-call menus + usage counters + favorites visible → **menu-intel lane** |
| Perspective | my screen | ONE coach's screen; may flip mid-file (seam → `files.json`) |
| Charting | Claude vision (primary); optional Gemini cloud respot via public YouTube | Claude vision only (opponent film never goes public) |
| Lane depth | `references/my-games-twitch.md` | `references/opponent-games-ipad.md` |

Triage signals at intake: URL vs dropped file; `ffprobe` aspect ratio; audio stream present/silent; moov atom errors. When in doubt, a 4:3 silent file is Lane B.

## Source authority (calibration-locked, do not regress)

0. **Knowledge firewall (user directive 2026-07-30): for *interpreting* film** — naming coverages, reading leverage/shell principles, what an audible means — the real-football sources (Christian Sam, Kurt Benkert → `references/football-iq.md` + `wiki/football-iq/`) outrank game-creator content. Game creators (Clario, Call Me Jaden, et al.) remain the authority for *game mechanics, menus, metas, and exploits*. Never present game-glitch behavior as football principle or vice versa.
1. **Menu usage counters (Lane B): verbatim call-sheet truth** — a tile reading "COVER 3 CLOUD PRESS | 52 CALLS" outranks every behavior-derived coverage read. Resolves man/zone ambiguity that tell-stacks get wrong (pressed cloud corners fake out the tells).
2. Formation/personnel: banner OCR (exact) > vision > announcer. *(Hook: when the user's external formation/play-ID tool arrives, it slots here between banner and vision.)*
3. **Run/pass: VISION IS THE AUTHORITY — audio never overrides it (user directive 2026-07-31).** The announcer read is still computed and stored in `play_type_transcript` so conflicts stay visible, but it must not rewrite `play_type`; `assemble.py` resolves `vis_type or tr_type`, and `merge_adjudication.py`'s play_type override must not be run. Vision's known pass-bias is disclosed as a caveat, not "corrected" by commentary.
3b. Result + yards + key_event: transcript adjudication (Lane A) / HUD deltas (Lane B, `adjudicate_hud.py`, deterministic). Vision never charts results, so these lanes don't collide with rule 3.
4. Coverage shells, routes, motion: vision (ghost trails / composites), behavior tells per `references/extraction-framework.md`.
5. Never average conflicting sources — flag them.
6. **Possession: the dd-bar colour lane (`segment.py`) is the authority. NEVER use jersey colour, and never trust an outcome-derived drive model.** When the colour lane degrades (night/fog film washes the semi-transparent scorebug — abstention climbs through the film, 2%→95% on BAY-NCST 2026-08-13), run `poss_rescue.py` AFTER charting: it fills ONLY colour-blank windows from (a) the **menu lane** — offensive vs defensive play-call screen on caller film says which side the recording owner is on; since 2026-08-14 it classifies the combined `v2_screen_call` + `v2_menu_tiles` text (tiles recovered 42 plays on RUT-VAND where screen_call was all "unknown"), with `v2_menu_side` as tiebreak ONLY when both patterns fire — never when neither fires (that bucket measured ~70%: agents' offense/defense labels on non-play-call overlays are guesses) — then (b) a ≤3-window continuity fill flanked by the same team with no score change (96.9% on masked-recovery sim vs the hand-verified UNC-VAND chart; longer gaps stay blank because a whole drive can hide inside them — naive unlimited fill measured only 75%), then (c) the **chain lane**: a blank inside a provably-continuous down chain (down +1 each play, distance strictly shrinks — GOAL→GOAL the only repeat — no score change, ≤90s gaps, dd readable throughout, anchored by a colour/menu-decided window, never fill) inherits the chain's team at unbounded length; any fresh 1st down BREAKS the chain (conversion vs punt/turnover are indistinguishable from dd alone). Masked-recovery validation 2026-08-14: menu 91-94%, chain 100%, zero overwrites. It never overwrites a measured read, aborts if menu/colour disagreement >10%, and stamps per-play `poss_src` (colour/menu/fill/chain). (calibration-locked 2026-08-05, UNC-VAND, all 116 windows hand-verified). Measured: bar colour **96%**, blind jersey-colour reads by vision agents **49%**, outcome-derived drive model **53%**. The vision failure is directional and predictable — 36 errors toward the home team against 10 the other way, because a home stadium's turf, end zones and crowd wear the home colours, so "dominant colour in frame" just names the host. The drive model drifts because possession can only flip on a punt/turnover/score and dd-segmentation is structurally blind to special teams, so one missed punt leaves it phase-inverted for a whole stretch. **Two detectors agreeing is not validation** — the bar-colour lane was once "confirmed" at 94% agreement against the equally-broken ball-spot OCR column. Validate possession against hand-read film or not at all.

## Environment

- Tools venv: `~/CFB27-film/.venv` (yt-dlp, faster-whisper, pytesseract, pillow). tesseract + ffmpeg via system. mlx-whisper is BROKEN on M5 — use faster-whisper CPU int8.
- Game workspace: `~/CFB27-film/<game-slug>/` (OUTSIDE the vault). Slug: `<season>-<team>-vs-<opp>`.
- All scripts in this skill's `scripts/` directory (base path announced when the skill loads), run with the venv python. Vault path has a space — quote it.
- Gemini respot (Lane A only): needs `GEMINI_API_KEY` in `~/CFB27-film/.env` (CLI free tier is dead).

## Pipeline (per game)

1. **Intake.**
   - Lane A: `yt-dlp -J <url>`; on token-null (auth-gated VOD) use the GQL `seekPreviewsURL` route — see `references/my-games-twitch.md`.
   - Lane B: copy recordings into the workspace; repair moov-less files with untrunc; record per-file offsets + perspective seams in `files.json`; concat-transcode 4:3 → `video.mp4` 1920×1080 CFR30. Recipes in `references/opponent-games-ipad.md`. Archive ORIGINALS; the transcode is a deletable regenerable.
   - Harvest the recording tail (~last 60s of frames) every ingest — postgame/quarter-line/team-stats screens are the scoring ground truth (guards against replay contamination).
2. **Transcribe** (Lane A, background): 16k mono wav → faster-whisper `large-v3-turbo`, cpu/int8, vad_filter → `transcript.json`. ~0 segments = silent film → treat as Lane B downstream (skip step 7, use 7b).
3. **Segment:** `segment.py video.mp4 seg/` (`--procs N`, OCR is parallel) → `seg/hud_timeline.csv`, `seg/plays.csv`. Clock column is context-only, never trust for logic. **`poss` comes from the COLOUR of the dd bar** vs the two score boxes (team-agnostic; 96% vs hand verification, and it abstains when the two teams' colours are within 25 RGB units). Since 2026-08-14 two additions (validated: 0/116 regression flips on UNC-VAND; RUT-VAND window-decided 37→101 with the 4 audited disagreements all resolving in the new lane's favour): an **adaptive colour model** (k-means on capsule chromaticity learns the film's two team colours; activates only when its cluster→team mapping agrees ≥90% with the fixed-threshold method; fills frame-level gaps only — a fixed-threshold decision always wins) plus **per-window majority voting** (`poss_conf`/`poss_n` columns; ST frames excluded). `hud_timeline.csv` now tags `st_state` (KICKOFF/PAT/PAT_GOOD/PAT_NOGOOD) and `seg/poss_anchors.csv` records each kickoff as a possession boundary directed by the preceding score change (scoring team kicks) — anchors are for the rescue lane/hand-checks, not yet auto-consumed. Check the "possession decided on X%" line — if that is low, per-team splits are not trustworthy and possession must be hand-read. **If dd readability <50% (typical on Lane B soft film): run the Claude-sheet HUD rescue** — `sheet_gen.py` → haiku transcription agents → `rebuild_timeline.py` (proven 27%→84%, 21%→90%). Details + agent prompt in `references/opponent-games-ipad.md`.
4. **Formations:** `scan_formations.py video.mp4 seg/plays.csv seg/formations.csv` — validate against the Gun/Pistol/I-Form/... prefix whitelist. Lane B: expect garbage from tesseract; vision agents carry formations instead.
5. **Keyframes:** `frames.py video.mp4 seg/plays.csv film/` (background, ~40s/play; parallel-split with `--plays A-B` ranges when slow) — **preplay 2×2 grid (snap−8→−1.2s, the audible/adjustment read)**, presnap, ghost pair, 3x2 strip, result frame, meta.txt. `--plays` takes numbers, ranges, or a mix, and **exits non-zero if any selected play is absent** (it used to silently produce nothing). Snap estimates are clamped into the play window, and windows ≤5s are tagged `snap_unreliable=1 short_window=` — **chart those as `non-play` unless the composites clearly show live football**; their snap cannot be localized and the frames can come from anywhere in the film. Snap-localization caveats: `references/calibration-history.md`.
6. **Vision charting (Claude primary):** haiku subagents, batched ≤12 plays, prompt + superset-JSON schema from `references/charting-prompts.md` — includes the **pre-play read** (`formation_initial`/`presnap_adjust`/`def_adjust`: lineup vs snap formation = audibles). `prep_batches.py` builds batches + full-res **menu crops** (Lane B); agents fill `screen_call`/`menu_tiles` from play-call menus. `fanout.py` → legacy blocks + chart_v2 jsonl → `merge_results.py` + `merge_v2_local.py`. Tag provenance `v2_src=claude-haiku-4.5-frames/<date>`. Lane A upgrade: Gemini cloud respot on the public YouTube copy — `references/my-games-twitch.md`.
7. **Transcript adjudication** (Lane A): haiku text-only, ~40 plays/batch, transcript window `[snap_N, snap_N+18s]` — announcers narrate into the next window.
7b. **HUD-delta adjudication** (Lane B / silent): `adjudicate_hud.py seg/plays.csv hud_results.csv` — result/yards/key_event from the NEXT play's HUD state. Deterministic; conversions are lower bounds (`>=dist`); unclassifiable rows get `CHECK`. Merge after step 8. Since 2026-08-14: a scoring window whose `poss` is blank gets `TD-UNATTRIBUTED` (never DEF-TD — the old blank-poss→DEF-TD default shipped 6 false defensive TDs on RUT-VAND), and score readings are monotonicity/stability-guarded (single-row spikes rejected unless confirmed by the next reading; no base-carrying; confirming reading must land ≤120s after the window or the row downgrades to `CHECK`). A `CHECK` can also mean the score jump belongs to an untracked adjacent event (missing PAT/return row) — dd-segmentation is ST-blind, so the delta is real but window ownership isn't resolvable from `seg/plays.csv`; check footage. Any `TURNOVER?` flag: confirm against composites + the postgame quarter line before believing it (special-teams artifacts and replay-stale frames both fake turnovers).
8. **Assemble:** Lane B first runs `timeline_snaps.py GAMEDIR` — the DEFAULT Lane B snap source, not a contingency (play clock hides at the snap → last counting second = snap). Then `assemble.py <gamedir> <batchdir> plays_charted.csv` — merges everything, computes tempo + `man_zone_verdict` tell-vote. **assemble's ">10 playclock = broken snaps" warning false-alarms on online H2H film** (median playclock-at-snap ≈20-24 there; it was calibrated on CPU pacing) — check the timeline lane before believing it.
8.4. **Possession rescue (when segment.py reported a low "possession decided on X%" line):** `poss_rescue.py GAMEDIR OWNER_SIDE [--maxgap 3] [--dry-run]` — runs after the chart merge (it reads `v2_screen_call` + `v2_menu_tiles` from `plays_charted.csv`) and before splits. See source-authority rule 6 for what it may and may not do. Re-copy the CSV to the vault after it writes.
8.4b. **Re-attribute HUD scoring after the rescue:** `adjudicate_hud.py --reattribute GAMEDIR` — re-resolves TD/DEF-TD/TD-UNATTRIBUTED against post-rescue possession, rewriting ONLY `result`/`key_event` (never `play_type` or `v2_*`). Run it whenever poss_rescue changed anything. Rows at `CHECK` stay `CHECK` by design — the underlying delta was never trustworthy and possession can't fix that; treat surviving CHECK/mismatch like `RE-VERIFY ATTRIBUTION` (go to the footage).
8.5. **Completeness audit:** `audit_clips.py <slug>` after every segmentation — down-sequence gaps, out-of-window score changes, >3min holes. dd-segmentation is structurally blind to special teams; ST windows get `kind` tags and are excluded from tendency splits. Verify total scoring against the postgame quarter line (replay rewatches interleave stale scorebug frames).
9. **Scout report:** run `menu_book.py GAMEDIR TEAM_L TEAM_R [SEAM OWNER_A OWNER_B]` → the game's call-sheet book (per-owner playbook table with usage counters, sorted by calls). Compute tendency splits locally (`splits.py` digest + run/pass by down, formation frequency, tempo, audible rate + transitions, 3rd-down/red-zone, menu-counter findings). **3rd/4th-down conversions are derived from the NEXT window's down** (same possession + fresh 1st down = converted; possession change = failed; unreadable successor = `undetermined`, excluded from the denominator, so report the undetermined count alongside the rate). Each dossier gets/updates a **"Call-sheet book"** section: cumulative counters per play with per-film deltas — **counters are the user's ALL-TIME call totals (user ruling 2026-08-13: at minimum multi-season/dynasty-scope, definitely more than one season)**, so each film is a lifetime-sheet snapshot and the delta between two films = calls made in the interval, including games we never saw. A counter that DECREASES between films is a red flag: vision misread or wrong film ordering — recheck the menu crops. Also run `call_ledger.py dynasties/<dynasty>/film-room/call-sheets ~/CFB27-film/<game>...` (pass every workspace that has a `menu_book.csv`) to rebuild the per-player counter ledgers — one CSV per coach, one row per film×play, the machine-readable counter history behind the dossier books. Write `dynasties/<dynasty>/film-room/games/<slug>.md` (NO `type:` frontmatter — the verifier whitelists types when present) + copy CSV to `film-room/plays/<slug>.csv`. Update rival dossier in `league/teams/<member>.md` (running sample counts; Lane B: capture gamertags, note matchup-dependence — one game's reads are gameplan, not identity).
9.5. **Chart validation — run BEFORE writing any report** (`validate_chart.py GAMEDIR`, added 2026-07-31 after three defects shipped undetected):
   - **Outcome contradictions.** A row charted `run` whose adjudicated `result`/`key_event` says `complete`/`incomplete`/`interception`/`sack` is impossible — those all require a dropback. Feed every hit to a contradiction re-check (`build_contradictions.py`) and let VISION decide again; never auto-flip (vision stays authoritative, the contradiction is only a reason to look harder). Iterate until zero.
   - **Game-boundary check.** A scorebug that goes BACKWARD and stays there, plus a quarter resetting to 1, means **the film rolled into a second game**. A one-play score dip that reverts is only OCR noise; a sustained reset is a new game. This actually happened: 16 windows of *Oregon State @ Oregon* were charted inside the OSU–Maryland VOD (seam = the 20-min gap between windows 169/170) and sat in that scout report undetected. Tag foreign windows `non-play` with an `[OTHER GAME: ...]` note so splits exclude them, and persist the tag into `chart_v2_flash.jsonl` so a re-merge keeps it. **`audit_clips.py`'s ">3min hole" flag is the early warning — always look at what is on the far side of the hole.**
   - **Off-schema `play_type`.** Agents invent values like `special-teams`; the schema allows only run/pass/non-play. `apply_recheck.py` normalises these — check the count it reports.
10. **Verify + log:** `verify_dynasties.py` must pass; /log the session.
11. **Archive + cleanup:** upload ORIGINALS to Drive folder "CFB27 Film Room" (id `1RHufk2iZPnoPACIue0LYGWW4MPzcnYoO`):
    `gws drive files create --upload "$f" --json '{"name":"<name>","parents":["1RHufk2iZPnoPACIue0LYGWW4MPzcnYoO"]}' --params '{"fields":"id,name,size,md5Checksum"}'`
    (the old `--parent` flag no longer exists). **Verify md5Checksum against local `md5 -q` BEFORE deleting anything**; record IDs in `drive_upload.json`. Then delete bulky regenerables: originals' local copies, `video.mp4`, `audio.wav`, `seg/hud_frames/`, rescue sheets. KEEP: `plays_charted.csv`, `transcript.json`, `seg/*.csv`, rescue JSONs, `film/` composites (small, needed for re-charting).

## Scripts

| Script | Signature | Lane / step |
| --- | --- | --- |
| `segment.py` | `video.mp4 seg/` | both / 3 |
| `sheet_gen.py` | `GAMEDIR T0 T1 OUTDIR` | B / 3 rescue |
| `rebuild_timeline.py` | `GAMEDIR` | B / 3 rescue |
| `timeline_snaps.py` | `GAMEDIR` | B / 8 snaps |
| `scan_formations.py` | `video plays.csv formations.csv` | A / 4 |
| `frames.py` | `video plays.csv film/ [--plays A-B]` | both / 5 |
| `prep_batches.py` | `GAMEDIR TEAM_L TEAM_R [SEAM]` | both / 6 (menu crops: B) |
| `fanout.py` | `GAMEDIR` | both / 6 |
| `merge_results.py` / `merge_v2_local.py` | `GAMEDIR` | both / 6 |
| `adjudicate_hud.py` | `seg/plays.csv hud_results.csv` | B / 7b |
| `assemble.py` | `gamedir batchdir out.csv` | both / 8 |
| `poss_rescue.py` | `GAMEDIR OWNER_SIDE [--maxgap 3]` | B / 8.4 |
| `audit_clips.py` | `<slug> [...]` | both / 8.5 |
| `splits.py` | `GAMEDIR TEAM_L TEAM_R` | both / 9 |
| `validate_chart.py` | `GAMEDIR [...]` | both / 9.5 |
| `build_recheck.py` | `GAMEDIR OWN_POSS` | both / 9.5 repair |
| `build_contradictions.py` | `GAMEDIR` | both / 9.5 repair |
| `apply_recheck.py` | `GAMEDIR` | both / 9.5 repair |
| `menu_book.py` | `GAMEDIR TEAM_L TEAM_R [SEAM A B]` | B / 9 call-sheet book |

## References

- `references/my-games-twitch.md` — Lane A depth: Twitch intake, transcription, transcript adjudication, YouTube→Gemini cloud respot.
- `references/opponent-games-ipad.md` — Lane B depth: untrunc, geometry, HUD rescue, menu-intel, perspective seams, play-clock snaps, replay contamination, ops.
- `references/charting-prompts.md` — coach-style vision agent prompt template + superset-JSON schema + coverage block + pre-play/audible read. Read before spawning charting agents.
- `references/football-iq.md` — real-football field guide (coverage-ID tells, Quarters vs Palms, seam-flat rules, audible interpretation), distilled from Sam/Benkert transcripts. The interpretation authority per the knowledge firewall above.
- `references/extraction-framework.md` — v2 behavior-tell decomposition + deterministic man/zone derivation.
- `references/calibration-history.md` — archaeology: frames.py snap saga, camera test, fps finding, superseded Gemini-primary decision.

## Boundaries

- Game W/L results flow ONLY through normal dynasty capture (season log + h2h) — film room is never a third tally.
- `dynasties/` never feeds `wiki/`; wiki pages never cite film-room data.
- Local deletion happens ONLY after checksum-verified Drive upload.
