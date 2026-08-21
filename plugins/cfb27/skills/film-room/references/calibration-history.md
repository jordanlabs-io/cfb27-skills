# Calibration history — archaeology

Findings and superseded decisions moved out of SKILL.md. Nothing here is a live instruction; it's the evidence base behind the current pipeline's choices.

## Calibration lineage

- 2026-07-22: OSU-UMD, 185 plays, user-accepted — original broadcast-VOD calibration.
- 2026-07-28/29: coverage block added; frames.py snap bug found + fixed; camera test; extraction-framework v2; Gemini-video architecture decision (superseded, below).
- 2026-07-30: caller-screen lane proven (KSU-WVU 95 + UMD-ARI 132 plays); Claude vision made the primary charting lane; HUD rescue, menu-intel, play-clock snap lanes built.
- 2026-08-05: UNC-VAND (Lane A, 116 windows). Four pipeline defects found and fixed; possession hand-verified on every window and the detector replaced. Details below.

## Possession + HUD calibration (2026-08-05, UNC-Vanderbilt)

**dd box and parser.** The old box `(845,980,230,38)` clipped the leading ordinal digit on this scorebug ("1st & 10" → `st a10`, "4th & 1" → `4thsl`), and `DD_RE` demanded a literal `[&8]` separator while this font OCRs `&` as `s`. `DD_NORM` additionally required a trailing word boundary, so `4ths` never normalized. Combined readability was **2%**. Widening to `(820,976,280,44)` at 4× upscale plus an alias-tolerant parser (aliases observed: `1st`→Ist/lst/ist/jst, `2nd`→and/anda/andes/end/ena, `3rd`→3rake/3rds/ard/srd, `4th`→Ath/4tn/atn; `S`→5, `I`/`l`→1, `O`→0) took it to **64% in-game, 67 → 116 detected plays.** The parser strips exactly one leading separator from the tail so the `&`-alias isn't then read as a digit (`4thsl` → `4&1`, not `4&51`). The clock box was also one pixel late (x=914 against a glyph at x=913), clipping the leading `0` of `0:56` — moved to x=905, width 108.

**Possession.** The old ball-spot glyph OCR (`poss_l`/`poss_r`) measured constant HUD chrome and scored **22%**. Five candidate detectors were tried against the film. Scores vs all-116-window hand verification:

| Signal | Accuracy |
| --- | --- |
| dd-bar colour vs the two score boxes (**shipped**) | **96%** (108/112) |
| outcome-derived drive model | 53% |
| blind jersey-colour reads by haiku vision agents | 49% |
| play-call menu vocabulary, menu crops only | 86% precision but 30% coverage |
| menu vocabulary incl. presnap/preplay | 56% |
| ball-spot glyph OCR (replaced) | 22% |

Notes on the losers, because each failure mode is reusable knowledge:
- **Jersey colour is unusable in a home stadium.** The vision agents' errors ran 36 toward the home team against 10 the other way — Kenan Stadium's turf, end zones and crowd are all Carolina blue, so "dominant colour" names the host, not the offense.
- **Outcome-derived drive models drift.** Possession only changes on punt/turnover/score, and dd-segmentation is structurally blind to special teams, so one missed punt inverts the model's phase for a whole stretch.
- **Menu vocabulary is confounded by the formation banner.** `presnap.jpg`/`preplay.jpg` carry the offensive formation banner ("Shotgun - Wing Trips Wk 1RB 1TE 3WR") for whichever team has the ball, so offensive vocabulary fires on every snap. Restricting to dedicated menu crops fixes the precision but leaves only 30% coverage.
- **The first "validation" of the bar-colour lane was worthless**: it was scored at 94% agreement against the ball-spot OCR column, which was itself 22% right. Two broken detectors agreeing is not evidence. The eventual hand-read was the only real check.

The shipped version is team-agnostic (the game-specific one hardcoded "light blue = North Carolina"): the bar takes the possessing team's colour, and the two score boxes always carry the two teams' colours, so the bar is classified by nearest score box in RGB, abstaining when the two team colours are within 25 RGB units or when neither box wins by 40%.

**Strongest untapped Lane A possession tell:** the play-call screen's playbook type — a defensive playbook means the caller is on defence, and the inset shows the opponent's formation with *their* logo. Higher-signal than colour where it's visible; the blocker is coverage, not accuracy.

**Two more defects, same game.** `frames.py --plays` accepted only comma-separated numbers while SKILL.md documented `A-B` ranges — a range matched nothing and **exited 0 with no output.** And five ≤5s windows all collapsed onto one out-of-window `snap_est` (4021.5s, inside the postgame recruiting menus); their composites came from the wrong part of the film and two were charted as a real pass and a real run. Both now fixed in `frames.py` (range parsing + loud no-match, snap clamped into the window, short windows tagged `snap_unreliable`).

**`splits.py` never counted a conversion.** Its third-down test string-matched `"1ST-DOWN"`/`"first down"`/`"TD"` against `key_event`/`result`, which this pipeline never writes in that vocabulary, so every third down scored as a failure — it printed Vanderbilt 0/18 where the truth was 3/18. Conversions are now derived from the next window's down within the same possession, with unreadable successors counted `undetermined` rather than as failures.

## frames.py snap-localization saga (2026-07-28/29)

**Bug:** audit of 25 retained `ghost.jpg` across the 5 charted games: 2/25 post-snap, 0/25 could support a coverage read — the rest were play-call menus, coverage-adjust screens, personnel cards, or pre-snap stills. Cause: `find_snap` took the motion onset after the *longest still stretch*, and in CFB 27 the longest still stretch is the play-call UI, so it locked onto the camera cutting back to the field seconds before the snap. `pc_stop_time` (play clock vanishing) was already preferred when the two disagreed by >3s, but returns `None` when play-clock OCR fails — exactly the low-readability films where the fallback mattered.

**Fix (shipped 2026-07-29):** (a) the `pc_stop is None` fallback uses `find_snap(..., mode="last")` — last sustained motion onset before `t_last - 5`; (b) post-grab gate `hud_says_presnap()` OCRs a full-width bottom-12% band of a fresh uncropped frame at `snap + 0.4s` for `PRE-PLAY`/`SUBS`, advances and re-grabs on a hit (max 2 retries), marks `snap_unreliable=1`. Gate fails open. **Live verification (Arizona, 95 plays, 3.4Mbps YouTube re-encode): `mode="last"` mostly good, but the gate produced ZERO flags while at least one play had visible PRE-PLAY HUD — the gate under-detects on low-bitrate video; treat as advisory there.** Residual failure mode: a sustained post-play onset (long return, celebration pan) before `t_last - 5` overshoots the snap.

**2026-07-30 addendum:** on caller-screen film, snap times are now derived from the timeline play-clock lane (`timeline_snaps.py`) instead — the play clock hides at the snap, making `mode="last"` moot there. frames.py also got an EOF guard in `strip()` (grabs past EOF write nothing at rc 0; skip missing cells).

**Consequence for pre-fix data:** every vision-sourced column in the five games charted before the fix (`formation` where `formation_src=vision`, `motion`, `concept`, `routes_or_blocking`, `def_front`, `def_shell_pre`, `def_post_snap`) was largely read off pre-snap and menu imagery. This is also the real reason vision over-calls pass — it was reading play-call route art, not routes. Banner/OCR, transcript, and HUD-derived columns are unaffected.

## Camera test (2026-07-29)

25 plays with `playclock_at_snap ≤ 5` across the 5 charted games: **the camera is NOT the blocker.** 16/25 strips contained genuine post-snap action; 11 of those (69%) showed a readable deep shell — the standard wide behind-the-offense camera holds ~20-25 yards of depth and both safeties; 1-high vs 2-high (incl. spin-downs) is distinguishable. Best coverage info is strip tiles 1-3 (+0.4 to +1.5s); later tiles tighten onto the ball. Unrecoverable minority: tight-sideline and goal-line camera variants (no DBs in frame; chart `unknown`). The 9/25 dead strips were all snap-localization failures; Baylor was 1/5 usable (per-game timing drift on top of the per-play bug). Net usable yield ≈44% pre-fix, ceiling ~70% post-fix.

## Completeness-audit findings (2026-07-29)

dd-based segmentation is structurally blind to special teams (kickoffs, PATs, touchbacks — no dd to change). Baylor ≥5 missed scrimmage plays, Northwestern ≥3 (1st→4th jump = two straight lost); WVU/Maryland clean. Arizona (Gemini full-screen segmentation) audited zero gaps in every check. The 2026-07-30 caller-screen games audited zero >3min holes after the HUD rescue.

## fps finding (2026-07-29)

Gemini Flash 3.6 re-tested at fps=4 with a guided step-by-step prompt on the 10-play WVU calibration set: `safeties_post` still 4/10 vs pro — **the judgment failure is the model, not the sampling rate.** Perception fields held (shell_pre 9/10). Charting clips keep `fps: 2`; segmentation chunks default.

## Video-model architecture decision (2026-07-29) — SUPERSEDED 2026-07-30

Original decision: Gemini video, clipped to play windows, as the preferred lane for any coverage re-chart (a video model dissolves snap localization via native temporal grounding; ~274k tokens/game; Twelve Labs and local Qwen3-VL/MLX rejected). **Superseded by the user's 2026-07-30 decision: Claude vision (haiku frames lane, on-plan) is primary for all charting; Gemini survives only as the optional Lane-A cloud respot** (public-YouTube delivery — see `references/my-games-twitch.md`). Reasons: the Claude lane shipped two full games reliably, runs on the Claude plan at no marginal cost, and opponent film can't be posted publicly anyway. Still open from the original decision: whether a 5-game re-chart is worth the ~12.4GB VOD re-pull (Drive IDs in each game's `drive_upload.json`).

## 2026-08-21 — UNC at Rutgers (W12 2027, 123 windows): four pipeline faults

First game charted on sonnet. Ground-truth key: the 92 postgame HIGHLIGHTS rows aligned to
the 123 windows by monotonic sequence alignment (86 paired, 60 clean run/pass controls
split 30/30). Scores `hud_dd` and `play_type` only — no scheme field has external truth.

**F1 — snap localisation ~4s early on 96% of windows.** `frames.py find_snap` uses motion
onset; on online H2H film the first sustained motion is the play-call UI, not the snap, so
frames were cut around the call screen. Two contributing bugs, both now fixed in
`frames.py`: `pc_stop_time` was called with `t_last - 4`, truncating the search exactly where
the snap lives (the window is bounded by the dd change the play itself causes, so the snap
sits near `t_last`); and it returned the last readable sample before a ≥4s gap, but the clock
often FREEZES rather than vanishing, so that condition fires at the freeze's END — up to 4s
late. New `snap_times.py` derives snaps from the rescued `hud_timeline` before frame
extraction. Hand-verified: play 30 → 901 (motion 902, correct), play 23 → 708 (motion 705),
play 21 → 651 (motion 646). Median `playclock_at_snap` 18, consistent with the ~20-24 H2H band.

**F2 — ghost composites unusable on panning film.** Broadcast camera pans after the snap;
a 3.2s min/max blend stacks the stadium on itself. Not `deshake` (regenerating without it is
identical). Every ghost-derived field was unknown on 12/12 calibration plays. Smeared on all
three other films spot-checked. `--no-ghost` now emits native-res `snap1..5.jpg` instead.

**F3 — the coverage lane has a hard ceiling on wide-angle film.** Even at native 1568px,
`cb_leverage_pre` and `saf_depth_band` were unknown on 12/12; post-snap fields unknown on
~80% of snaps. Of three filled reads cross-checked against visible play art, **1 of 3 agreed**
— fill rate is not accuracy. Coverage tendencies must come from counters or play art.

**F4 — menu crops were never handed to the charting agents.** 0/123 plays had `menu_tiles`,
silently removing rule 1 from the ingest. Recovered by a separate transcription pass (441
tiles, 103 plays booked). Note the ownership trap: on the user's own screen every menu is the
USER's call sheet — this film added nothing to Duis's counter book.

**Model comparison (identical frames, identical prompt, only the model varying, 12 plays):**
sonnet vs haiku — run/pass 75% / 42%; `hud_dd` 92% / 91%; scheme fields FILLED 38% / 86%;
`def_coverage` named 1/12 vs 0/12. Inter-model agreement on scheme fields near zero
(formation 0/12, `def_shell_pre` 2/12, `def_safeties_post` 1/12) — one model is inventing.
Better frames moved haiku's HUD reading 73%→91% and its run/pass judgement 50%→**42%**.
Matches `frame_quality.py`'s measured "coin flip on an illegible frame" at 52%.

**Source authority ruling (user, 2026-08-21):** postgame play-by-play is the source of truth
for the play record; film-room charting is the fallback where no PBP exists. Applied here:
`validate_chart.py` independently flagged 4 plays as "run-labelled but outcome implies pass";
10 were reconciled against the outcome lane. Post-reconciliation the chart agrees with the PBP
on 61/62 scoreable plays. **Honest split: 82% is vision-only accuracy (independent); 98% is
the chart's agreement with its own correction source and is not a model metric.**

Unfixed and known: play 37 remains unchartable (7s window, snap falls outside it — a
segmentation fault, not a snap-timing one).
