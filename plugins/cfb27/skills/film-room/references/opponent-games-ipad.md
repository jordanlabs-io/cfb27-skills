# Lane B — opponent games (iPad party-share recording)

Opponent film: iPad screen recording of a shared screen in the PlayStation party — I'm watching from the outside. 4:3, silent, soft/compressed HUD, and (the payoff) the sharing coach's **play-call menus are visible**. Proven 2026-07-30 on KSU-WVU (95 plays) + UMD-ARI (132 plays).

Two capture variants of the same lane:

- **On-device iPad screen recording** (the original): 2732×2048, no audio track, may be moov-less.
- **QuickTime recording of the iPad over USB-C** (first seen 2026-08-19, NW-ARI + BAY-NW): **1600×1200@60**, healthy moov (no untrunc needed), and a **PCM audio track that IS present but carries only quiet game audio** (~-40 to -49 dB mean) — still triage and adjudicate as Lane B silent (skip transcription, use HUD-delta adjudication). Crop recipe scales proportionally: `crop=1600:900:0:150` — same 12.5% top band as the native recipe below.

## Intake + repair

- **Multi-file games are normal.** Copy all recordings in; record per-file durations, concat offsets, and perspective seams in `files.json`.
- **moov-less files** (recording/transfer interrupted; ffprobe can't read them): repair with **untrunc** (anthwlock fork). Build once: `make FF_VER=shared` with `CXXFLAGS="-isystem$(brew --prefix)/include" LDFLAGS="-L$(brew --prefix)/lib"` against brew ffmpeg. Reference file = any healthy same-device recording. Recovery has been complete both times tried.
- **Geometry:** iPad 2732×2048 is 4:3. Transcode before anything else:
  `crop=2732:1536:0:256,scale=1920:1080,fps=30` → hevc_videotoolbox 10M, `-an`. (QuickTime-over-USB-C variant: `crop=1600:900:0:150` before the same scale.) Two files concat in a single filter_complex pass. Occasional `hevc_videotoolbox` "-12912" errors during parallel transcodes have produced complete outputs anyway — verify duration + spot frames rather than assuming failure.
- **iOS system overlays** (Control Center, the Wi-Fi picker, etc.) get recorded over LIVE play frames — the game keeps running behind them (observed 2026-08-19, NW-ARI/BAY-NW). Treat them like menu overlays: chart the play visible behind/around the overlay, don't tag the window `non-play` just because an overlay covers part of it.
- **Perspective:** the recording shows ONE coach's screen and may flip mid-file (e.g. WVU's screen first half, KSU's second). The seam timestamp goes in `files.json`; every play downstream carries `menu_screen_owner` so menu-intel is attributed to the right coach. Capture the sharing players' gamertags for the dossiers.
- **Tail harvest:** grab the last ~60s of frames — POST GAME / quarter-line / team-stats screens are the scoring ground truth.

## Claude-sheet HUD rescue (trigger: segment.py dd readability <50%)

Tesseract collapses on soft share-screen scorebugs (27%/21% observed) even though the text is model-legible.

1. `sheet_gen.py GAMEDIR T0 T1 OUTDIR` — stacks labeled scorebug crop-sheets (24 rows/sheet, `tN` tags).
2. Haiku transcription agents, ~7-10 sheets each, output JSON per sheet. They read dd, score, possession, clock verbatim — including "KICKOFF"/"PAT&GOOD" dd states (free special-teams tags). **Possession** comes from the dd-capsule's team color (match capsule color to jersey/trim colors, e.g. purple=KSU=L, navy=WVU=R). Respawn any agent stalled >10 min; re-check apparent short outputs before re-running (they're often complete).
3. **t-value validation gate — MANDATORY before rebuild.** Haiku agents mislabel the sheet-row `t` tags (Rutgers leading-digit failure, recurred 2026-08-19 on NW-ARI/BAY-NW): rows come back with fabricated or shifted `t` values, which silently corrupts the rebuilt timeline. Sheet N covers `sorted-frames[(N-1)*24 : N*24]` — validate every `sheetNNN.json`'s `t` values against that true chunk, then repair:
   - **(a)** full 24-row sheets → positionally remap (row i = i-th frame of the chunk);
   - **(b)** partial sheets with a single constant offset → constant-offset repair;
   - **(c)** anything still unfixable → re-transcribe those sheets with **sonnet** agents, which read the labels correctly where haiku failed twice.
   Scripts: `validate_rescue.py GAMEDIR` (drops fabricated/out-of-range rows) and `remap_rescue.py GAMEDIR` (remap + offset repair) in this skill's `scripts/`.
4. `rebuild_timeline.py GAMEDIR` — patches `hud_timeline.csv` from the JSONs and re-runs play detection (coerce `t` to float; observed results: dd 27%→84% / 21%→90%, windows 37→95 / 68→132, zero audit holes).

Keep the rescue JSONs after cleanup — they're the timeline's source of record.

## Menu-intel lane (the best defensive-tendency source captured to date)

Between plays the caller's screen shows play-call menus with **per-play usage counters ("N CALLS | X.X AVG YDS") and starred favorites** — verbatim call-sheet truth that outranks behavior-derived reads (see Source authority in SKILL.md).

- `prep_batches.py GAMEDIR TEAM_L TEAM_R [SEAM]` extracts full-res menu crops from the gap before each snap and attaches up to 3 per play.
- Charting agents transcribe every legible tile (title, MAN/ZONE/BLITZ tag or formation, counters), the personnel/tab row, and stars → `screen_call` / `menu_tiles` fields (`references/charting-prompts.md`).
- Payoffs observed: exposed a signature blitz suppressed in prior head-to-head film (WS Blitz 3, 30 calls); resolved a man/zone ambiguity the tell-stack got wrong (Cover 3 Cloud Press 52 calls — pressed cloud corners read as man). In the scout report, cite counters as call-sheet fact and mark behavior-derived reads as inference.

## Silent-film adjudication + snaps

- No audio → `adjudicate_hud.py` (step 7b). Treat `TURNOVER?` flags skeptically: special-teams windows and replay-stale frames fake turnovers; confirm against composites and the postgame quarter line.
- **Replay contamination:** coaches rewatch replays on their own screen → interleaved stale scorebug frames (phantom score clusters). Always reconcile total scoring with the postgame quarter line.
- **poss_rescue menu/colour disagreement on near-identical team colours** (e.g. Northwestern purple vs Arizona navy, 2026-08-19): the colour lane's decided windows can themselves be WRONG, so a menu/colour disagreement is not automatically the menu lane's fault — and bulk-trusting either lane is how a whole stretch flips. Hand-verify each disputed window from `film/playNNN` frames, **blank the refuted colour reads** in the timeline, then rerun `poss_rescue.py`.
- **Snaps from the play-clock lane** (`timeline_snaps.py`): CFB 27 hides the play clock at the snap → last counting second = snap. Online H2H median playclock-at-snap ≈ 20-24, so assemble.py's ">10 = broken snaps" warning is a CPU-pacing false alarm here.

## Ops notes

- Subagent concurrency cap is 20 — queue the remainder as slots free.
- `frames.py` at ~40s/play is fine; if a game paces far slower, parallel-split with `--plays A-B` ranges (3× split used on UMD-ARI).
- Opponent film never goes to YouTube/Gemini (public-only ingestion) — Claude vision is the only charting lane here.
- Archive ALL original recordings (not the transcode); the 4:3 originals are the ground truth for any future re-transcode.
- **gws upload parsing:** `gws` prints a `Using keyring backend: file` line BEFORE its JSON output — strip everything up to the first `{` before parsing upload responses. Large single multipart uploads are fragile (a 5.5GB one barely survived, 2026-08-19) — upload smallest-first so a late failure costs the least re-upload time.
