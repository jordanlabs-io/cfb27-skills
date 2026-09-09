# Calibration history — archaeology

Findings and superseded decisions moved out of SKILL.md. Nothing here is a live instruction; it's the evidence base behind the current pipeline's choices.

## Calibration lineage

- 2026-09-09: playclock-tick sub-second detector attempted (rutgers-vs-northwestern 20-play truth set) — did NOT beat the shipped chip-clear estimator; not wired as default. Details below.
- 2026-07-22: OSU-UMD, 185 plays, user-accepted — original broadcast-VOD calibration.
- 2026-07-28/29: coverage block added; frames.py snap bug found + fixed; camera test; extraction-framework v2; Gemini-video architecture decision (superseded, below).
- 2026-07-30: caller-screen lane proven (KSU-WVU 95 + UMD-ARI 132 plays); Claude vision made the primary charting lane; HUD rescue, menu-intel, play-clock snap lanes built.
- 2026-08-05: UNC-VAND (Lane A, 116 windows). Four pipeline defects found and fixed; possession hand-verified on every window and the detector replaced. Details below.

## playclock-tick snap detector attempt (2026-09-09, rutgers-vs-northwestern)

Hypothesis: the play clock stops the instant of the snap, so the LAST
downward tick of the digit before it goes frozen brackets the snap to
within 1.0s at sub-second resolution — no OCR needed to find the tick
itself, just a grayscale mean-abs-diff spike on the 52x34px playclock
digit crop (`segment.BOXES["playclock"]`) at 10fps, then A3-style motion
search inside the resulting bracket.

Measured on the same 20-play hand-verified truth set as the shipped
chip-clear/motion/bracket precedence (`scratchpad/snap/truth.csv` in that
session):

| play | true_snap | old (0.16.0) est | old src | old err | tick est | tick src | tick err |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 5 | 91.05 | 89.45 | motion-sustained | 1.60 | 89.95 | playclock-tick | 1.10 |
| 12 | 262.70 | 262.85 | motion-sustained | 0.15 | 263.55 | playclock-tick | 0.85 |
| 15 | 318.45 | 319.25 | motion-sustained | 0.80 | 319.55 | playclock-tick | 1.10 |
| 25 | 513.95 | 512.00 | playclock-bracket | 1.95 | 513.65 | playclock-tick | 0.30 |
| 33 | 702.35 | 702.00 | playclock-bracket | 0.35 | 703.85 | playclock-tick | 1.50 |
| 40 | 848.45 | 848.35 | motion-sustained | 0.10 | 847.80 | playclock-tick+motion | 0.65 |
| 48 | 1016.40 | 1016.00 | playclock-bracket | 0.40 | 1016.10 | playclock-tick+motion | 0.30 |
| 55 | 1252.35 | 1252.00 | playclock-bracket | 0.35 | 1252.45 | playclock-tick | 0.10 |
| 63 | 1393.15 | 1393.05 | motion-sustained | 0.10 | 1392.85 | playclock-tick | 0.30 |
| 71 | 1561.95 | 1561.75 | motion-sustained | 0.20 | 1562.75 | playclock-tick | 0.80 |
| 73 | 1621.45 | 1620.00 | playclock-bracket | 1.45 | 1620.75 | playclock-tick | 0.70 |
| 78 | 1697.95 | 1697.55 | motion-sustained | 0.40 | 1698.85 | playclock-tick | 0.90 |
| 85 | 1814.85 | 1815.05 | motion-sustained | 0.20 | 1814.00 | playclock-tick+motion | 0.85 |
| 92 | 1922.05 | 1922.00 | playclock-bracket | 0.05 | 1921.90 | playclock-tick+motion | 0.15 |
| 100 | 2130.75 | 2130.00 | playclock-bracket | 0.75 | 2131.35 | playclock-tick | 0.60 |
| 105 | 2281.55 | 2281.00 | playclock-bracket | 0.55 | 2281.45 | playclock-tick | 0.10 |
| 115 | 2465.05 | 2465.00 | playclock-bracket | 0.05 | 2466.25 | playclock-tick | 1.20 |
| 120 | 2585.85 | 2585.55 | motion-sustained | 0.30 | 2585.60 | playclock-tick+motion | 0.25 |
| 125 | 2683.45 | 2685.15 | motion-sustained | 1.70 | 2684.55 | playclock-tick | 1.10 |
| 133 | 2895.85 | 2895.15 | motion-sustained | 0.70 | 2896.25 | playclock-tick | 0.40 |

Summary: old (shipped) median 0.375s, P90 1.70s, 8/20 (40%) within ±0.3s.
New (playclock-tick) median 0.675s, P90 1.20s, 5/20 (25%) within ±0.3s.
**The tick detector is worse on the primary metric (median, within-±0.3s
count) and only better on P90 tail** — it did not clear the ±0.3s/≥90%
goal and does not beat the shipped estimator, so it was NOT wired as the
default. Also measured `t_tick` alone vs `true_snap` (before any motion
refinement): median |t_tick − true| 0.60s across the 20 plays — the raw
tick signal is not tight enough on its own to justify the added ffmpeg
cost.

Root cause: the playclock digit box is only 52×34px, and a single-digit
transition's anti-aliased render smears across 2-3 consecutive 10fps
frames. Multiple such smears (font kerning shift, adjacent glyph reflow)
can register as separate diff spikes without any real digit change, so a
pure grayscale mean-abs-diff spike detector picks the wrong "last tick"
on several plays (worst case play 33: tick found 1.5s late). Confirming
each candidate tick against an actual OCR'd digit value (as the original
task spec intended — "only OCR the values at 1fps to know which change is
a tick vs the freeze") would likely fix this, but wasn't built in this
pass. Code kept as `snap_refine.playclock_tick_time()` /
`snap_refine.refine_snap_tick()` (not called by the default
`refine_snap()` precedence) for anyone who wants to add the digit-confirm
step.

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

## 2026-09-08 — coverage ground truth audit

`def_coverage_src=playart` is not an independent test of vision accuracy. `prep_batches.py:131`
includes `playart.jpg` in the images handed to the charting agent, so raw agent `def_coverage`
on those rows (29/29 present of 72 total truth rows) matches the play-art overlay 29/29 — a
transcription check, not a recognition check. Separately, per-row notes on 15/72 truth rows
report the play-art overlay bleeding into `presnap.jpg`/`snap1.jpg`/`snap2.jpg`/`strip.jpg` —
the overlay contaminates the very "clean" frames it's meant to be graded against.

Truth-family counts, pooled across the four 2028 games charted so far: cover-3 44, cover-4 12,
cover-2 9, cover-0 2, cover-1 1, off-schema 4 (n=72). Majority-class baseline (always guess
cover-3) is 44/72 = **61%**.

**Consequence:** any real coverage-recognition eval needs hand-adjudicated truth, or truth from
a frame set with the play-art overlay stripped — `def_coverage_src=playart` truth is
contaminated by both the image feed and the overlay-bleed above. `query_plays.py
audit-coverage` compares play-art family against `man_zone_verdict` as a proxy signal; its
output must not be read as a vision accuracy number.

## 2026-09-09 — snap anchoring (PLAN-snap-anchoring.md, A1-A12)

**A1 interpreter.** `~/CFB27-film/.venv/bin/python3` has numpy 2.4.6, PIL, pytesseract; system
`python3` does not. Confirmed and recorded in SKILL.md. `scripts/preflight_env.py` added.

**Hand-verified truth set.** 20 plays on `2028-rutgers-vs-northwestern` (5,12,15,25,33,40,48,
55,63,71,73,78,85,92,100,105,115,120,125,133 — spans all 4 quarters, includes plays 40 and
100 from the plan's original evidence). True snap timed to 0.1s by extracting frames over
`[snaps.csv snap - 1.5, +2.5]` at 10fps and reading the PRE-PLAY/SUBS chip stddev collapse
(14/20 plays) or, where the chip signal was unreadable on that camera angle, full-frame visual
motion/prompt-transition (6/20: plays 12, 15, 48, 55, 100 needed an extended re-extraction —
play 100's true snap sat outside the original ±1.5/+2.5s bracket entirely, requiring a fresh
4s window from the coarse anchor -1.5 to +2.5 relative to a corrected reference point).
Old estimator (playclock-freeze START, no sub-second refinement) error vs this truth set:
mostly +0.35 to +2.05s early, one -0.55s late; median ~0.8s, P90 ~1.95s.

**A2-A4 estimator (snap_refine.py).** Precedence preplay-chip (chip crop stddev<10 sustained
>=0.3-0.5s) -> motion-sustained (full-frame mean-abs-diff, scorebug excluded) -> playclock-
bracket (coarse anchor, flagged unreliable). Bracket widened from the plan's spec
[t_freeze-0.5, t_freeze+1.5] to [t_freeze-0.5, t_freeze+2.5] — several true snaps in the hand
set sat past +1.5s (the playclock can freeze up to ~2s before the chip visually clears).

**Measured on the calibration film, full pipeline (snap_times.py --video -> frames.py
--snaps), 20-play truth set:**

| metric | old (playclock-bracket only) | new (chip/motion refined) |
| --- | --- | --- |
| median abs error | ~0.80s | 0.375s |
| P90 abs error | ~1.95s | 1.60s |
| within ±0.3s | ~0/20 (0%) | 8/20 (40%) |

**Goal NOT met.** PLAN-snap-anchoring.md's definition-of-done target was ±0.3s on >=90% of
hand-verified plays. Measured result is 40% within ±0.3s, median 0.375s. This is a real
improvement over the old estimator (roughly halves median error) but does not reach the
stated goal. Root cause, per-play: the PRE-PLAY/SUBS chip is the only clean, cheap,
PIL+stdlib-only signal available (per A1, no OpenCV/template-matching), and even where it
fires cleanly its own visual clearing lags the true snap by up to ~1s on this camera's HUD
(the chip is driven by a game-engine UI transition, not the ball leaving the QB's hands) —
see the `truth.csv`-vs-`snaps.csv` per-play table in the PLAN-snap-anchoring session scratch
(scratchpad/snap/truth.csv) for the full breakdown. A precise (<0.3s) estimator on this HUD
would need either a template-matched HIKE/SNAP world-anchored prompt (present in some but not
all camera angles per pre-flight evidence, unconfirmed as reliably present in general) or a
much higher-fps motion analysis than is affordable at scale across a full-game charting run.

**A8 PBP reconcile.** Tested against `2026-unc-vs-vanderbilt` (menu-intel JSONL
`2026-08-20-w11-unc-vand-postgame-tail.jsonl`, since the calibration film's recording tail
captured only the final box-score menu, not the drilled-into HIGHLIGHTS list). Result: 16/25
comparable PBP rows (64%) found a matching window in that game's `seg/plays.csv` — gate
(>=90%) FAILED. Traced to genuine absence: several PBP dd values (`4&3`, `3&Goal`, `2&6`, ...)
do not exist anywhere in that game's 117-window segmentation, a completeness gap in that
specific (older) game dir's `seg/plays.csv`, not a pbp_reconcile join bug. Also found: the
postgame HIGHLIGHTS reel does not scroll in strict chronological order across quarters, so
quarter inference in `pbp_ingest.py` is approximate and the spec's forward-only monotonic
cursor produced worse results than an any-occurrence dd match (used instead, documented in
pbp_reconcile.py). Re-test needed on a game with complete segmentation before trusting the
90% gate elsewhere.

**A11 re-cut scope, honestly limited.** Re-cut the calibration film's 20 hand-verified plays
and all of `2028-unc-vs-illinois` (131 plays) with the new frames.py. `2028-unc-vs-maryland`
and `2028-unc-vs-baylor` could NOT be re-cut: their `video.mp4` was already archived to Drive
and deleted locally by `archive_sweep.py` (regenerable-by-design per SKILL.md's KEEP list),
and re-downloading two ~4-5GB originals was out of scope for this session. Of the 60-play
labeling manifest (maryland 30, illinois 24, baylor 6), only the 24 illinois plays could be
re-cut and checked; the 36 maryland/baylor plays remain on the OLD (pre-A2-A6) frames until
their video is re-fetched. See the post-recut presnap post-snap count below.

**A12 honest goal statement.** *(SNAP HALF SUPERSEDED BY A14/A15 — the 40% figure was
measured against the `truth_v2` reference A14 showed to be wrong by up to 2.3s. The PBP
alignment half stands.)* The ±0.3s/>=90% snap-accuracy goal and the >=90% PBP-alignment
goal were BOTH investigated in full, with real code, a real hand-verified truth set, and real
measurement on real film — and both fell short (40% and 64% respectively). The estimator and
reconcile scripts shipped are real improvements over what existed before (roughly halved
median snap error; PBP ground truth went from a manual prose join to a scripted, re-runnable
one) but should not be represented as meeting the plan's original targets. Anyone re-running
this calibration on a different film should expect similar honest numbers, not ±0.3s/90%,
until a stronger snap signal (e.g. a confirmed world-anchored HIKE prompt with template
matching, explicitly deferred by A1's "PIL + stdlib only" constraint) is added.

**A13 truth set v2 + OCR-confirmed play-clock-tick experiment (2026-09-09).** *(SUPERSEDED BY
A14 — every number in this entry is scored against `truth_v2`, which is wrong. The play clock
does stop at the snap; A13's failure was the reference and the detector, not the physics.)* `truth.csv`
disagreed with an earlier loose eyeball read by 0.4-0.6s on 2 of the 20 plays (40, 100); all
20 were re-verified at 10fps under one explicit definition — true snap = first frame the ball
has left the center's hands, or (ball not resolvable) first frame the O-line visibly moves —
producing `truth_v2.csv` (scratchpad/snap2/truth_v2.csv this session). Only plays 40 (848.45
-> 848.6, +0.15s) and 100 (2130.75 -> 2130.85, +0.10s) moved, both re-verified by eye
frame-by-frame; neither exceeds the 0.2s re-verification-flag threshold, so `truth.csv`'s
existing chip-clear/visual-motion justifications were confirmed consistent with the v2
definition and carried forward unchanged for the other 18 plays.

Built and measured an OCR-confirmed play-clock-tick detector (`--psm 7`, char-whitelist
digits, tried three binarizations per frame — the shipped `segment.ocr_field` "inv" prep,
a manual white-chip threshold, and a manual red-chip threshold — smoothed with a >=3-frame
persistence filter, `t_tick` = start of the last confirmed value decrement, bracket =
[t_tick, t_tick+1.05]) against `truth_v2`, per PLAN's "clock stops the instant of the snap"
theory:

| metric | OCR-tick | shipped (chip/motion, rescored vs truth_v2) |
| --- | --- | --- |
| OCR read rate (10fps digit-box samples) | 754/900 = 83.8% | n/a |
| bracket valid (truth_v2 in [t_tick, t_tick+1.05]) | 8/20 (40%) | n/a |
| median abs error | 0.400s (14/20 produced an answer) | 0.375s (20/20) |
| P90 abs error | 1.15s | 1.60s |
| within ±0.3s | 7/20 (35%, only 14 plays produced a bracket at all) | 8/20 (40%) |

**Gate (bracket valid >=18/20) FAILED at 8/20 — NOT wired in.** Root cause: the 52x34px
play-clock digit box is too small and too often camera-cut/occluded/off-angle for OCR to hold
a clean, gap-free read through the actual tick-to-freeze transition. Play 100 (the second
re-verification play, wide/zoomed camera) is the clearest case: the digit box goes almost
entirely unreadable (`None`) for the ~2s window spanning the real snap (2130.0-2132.9), the
exact same camera-angle failure mode that made the PRE-PLAY chip unreadable for this play
under A2/A3 — OCR does not add signal where the underlying pixels are absent, and the smaller
digit box is if anything more fragile to a camera cut than the wider chip box. Where the OCR
read rate is high, the tick detector performs comparably to the shipped estimator (bracket
valid plays average ~0.2s error) — the theory is sound, but the digit-box read-rate ceiling
on this HUD keeps it well under the 18/20 bar. Not wired into `snap_refine.refine_snap`'s
precedence; `snap_refine.playclock_tick_time` (the older diff-spike, non-OCR variant) remains
the only tick-family code in the shipped module, both flagged experimental/unused. Full
per-play table and prototype scripts: scratchpad/snap2/ (`truth_v2.csv`, `ocr_tick.py`,
`run_eval.py`, `results.json`) from this session — not copied into the repo since neither the
truth-set re-verification frames nor the failed experiment's scratch scripts are needed by
the shipped skill.

**A14 the A13 "paradox" was a broken reference — truth_v3 (2026-09-09).** A13 reported an
83.8% OCR read rate yet only 8/20 brackets containing the snap. Diagnosing that by dumping
the 10fps play-clock value series per play and VIEWING the play-clock crop plus the field
frames revealed the reference itself was wrong. **`truth_v2.csv` is late by 1.4-2.2s on
several plays and its coarse marks miss the snap entirely on two.** Worked evidence:

- **Play 115.** The HUD montage over 2461.8-2466.0 shows the play clock decrement 27 -> 26 at
  t=2462.25 and then hold 26 for 3.4s while the GAME clock keeps ticking normally
  (3:38 -> 3:37 -> 3:36 -> 3:35). The field frames show the SNAP prompt at 2462.2, the
  SNAP -> HIKE transition at 2462.8, and the O-line firing off at 2462.9. The real snap is
  ~2462.75; `truth_v2` said 2465.05 — 2.3s later, i.e. mid-run. The play clock froze at the
  snap exactly as the user's rule predicts.
- **Play 73.** Static presnap through 1619.85; at 1619.95 the green ball-carrier ring appears
  and the PRE-PLAY/SUBS chip vanishes. Real snap ~1619.90; `truth_v2` said 1621.45.

All 20 plays were therefore relabeled from coarse-anchored 5fps montages (window
[coarse-3.5, coarse+2.5], widened for play 25 whose coarse mark is 2.4s early), using the
sharp, camera-angle-independent cues this diagnosis validated — the SNAP -> HIKE prompt
transition, the PRE-PLAY/SUBS ("R") chip disappearing, and the ball-carrier ring appearing —
with the label taken as the midpoint of the last presnap frame and the first post-snap frame
(+/-0.1s). Result: **`truth_v3.csv`**, which supersedes `truth_v2.csv` (kept on disk, not
overwritten). Per-play cue and bookend-visibility flags are recorded in that file.

**Two separate failure surfaces.** A13 conflated them. Split:

*(i) Reference errors — `truth_v2` vs `truth_v3` (cause (e)):*

| play | truth_v2 | truth_v3 | error | note |
| --- | --- | --- | --- | --- |
| 5 | 91.05 | 89.60 | +1.45s late | labeled mid-run |
| 25 | 513.95 | 514.35 | -0.40s early | coarse mark 2.4s early; window missed the snap |
| 73 | 1621.45 | 1619.90 | +1.55s late | labeled mid-run |
| 100 | 2130.85 | 2130.60 | +0.25s late | (within tolerance) |
| 115 | 2465.05 | 2462.75 | +2.30s late | coarse mark 2.25s late; labeled mid-run |
| 125 | 2683.45 | 2685.20 | -1.75s early | labeled during the presnap route overlay |
| 133 | 2895.85 | 2895.60 | +0.25s late | (within tolerance) |

Four plays (5, 73, 115, 125) are wrong by more than 1.4s; the other 16 moved by <=0.4s.

*(ii) A13 detector failures (why the tick was wrong or absent), 12 plays:*

| mechanism | count | plays |
| --- | --- | --- |
| digit box unreadable near the snap — terminal tick(s) never seen | 3 | 25, 48, 100 |
| leading-digit OCR drop (12 read as "2") broke the decrement chain | 4 | 5, 63, 125, 133 |
| `last_tick_time` terminal-run rejection refused to answer at all | 4 | 12, 25, 48, 63 |
| (a) clock kept ticking after ball movement | **0** | — |
| (d) clock froze before the snap (cadence / hard count) | **0** | — |

Causes (a) and (d) are ruled out on all 20 plays: wherever the digit box is readable through
the transition, the clock's last decrement precedes the snap and the value then holds.

**What the play clock actually does.** The user's rule holds. On every play where the digit
box is readable through the transition, the play clock's last decrement precedes the snap and
the value then holds frozen until the next play's 40-reset. Measured
**offset = truth_v3 - t_tick, over the 17 of 20 plays whose play-clock digit-box read rate
exceeds 53/70 (75%): mean 0.624s, sd 0.256s, min 0.20s, max 1.10s.** Do not lift that mean
onto plays below that read-rate bar. The max of 1.10s nominally exceeds one clock second;
that is the +/-0.1s labeling slack plus the R-chip's own render lag, not the clock running
past the snap. The three excluded plays (25, 48, 100) all have digit-box read rates of 45/70, 37/70 and
34/70 and are missing one or more terminal ticks; their apparent offsets (3.25s, 1.7s, 1.8s)
are missed ticks, not a second mechanism.

A periodicity-aware tick detector (`tick2.py` this session) fixes A13's failure modes: fit the
longest chain of confirmed runs consistent with "-1 per ~1.0s", tolerate a dropped leading
digit and bridge unreadable gaps with the 1.0s period, and take the last link's transition
time as `t_tick`. It produces a tick on 20/20 plays (A13's produced 14/20).

**Rescored against truth_v3:**

| estimator | median | P90 | within +/-0.3s |
| --- | --- | --- | --- |
| shipped 0.16.0 (chip-clear / motion / bracket) | 0.200s | 0.850s | 14/20 |
| raw `t_tick + 0.60` | 0.200s | 1.100s | 12/20 |
| **hybrid: keep the 0.16.0 answer when it falls in [t_tick, t_tick+1.3], else `t_tick+0.60`; skip the constraint when the digit-box read rate is below 75%** | **0.150s** | **0.450s** | **16/20** |

The hybrid's 16/20 sits on a flat plateau (stable for bracket width 1.3-1.4s, offset
0.60-0.65s, and read-rate guard 0.60-0.95), not a knife-edge fit; only bracket width 1.2s
drops it to 15/20. Its whole gain comes from using the tick as a REJECTION CONSTRAINT on the
chip/motion answer, not as an estimator: it rescues plays 15 (0.85 -> 0.10) and 115
(2.25 -> 0.15), where chip-clear latched onto a later camera state.

**A14 supersedes A12's honest-goal statement for the snap metric measured against a sound
reference: the shipped 0.16.0 estimator was never 40% within +/-0.3s — it is 70% (14/20). The
A13 table's numbers are void; they were computed against `truth_v2`.**

**A15 tick-as-constraint WIRED IN (0.16.2, 2026-09-09).** `refine_snap()` now runs the A2/A3
precedence as before, then sanity-checks the answer against `playclock_last_tick()`:

```
if a tick was found AND the digit-box read rate >= TICK_MIN_READ (0.75):
    keep the chip/motion answer only if t_tick <= snap <= t_tick + TICK_BRACKET (1.3s)
    otherwise return t_tick + TICK_OFFSET (0.60s), snap_src "playclock-tick"
```

`playclock_last_tick()` OCRs `segment.BOXES["playclock"]` at 10fps over
[t_freeze-4.0, t_freeze+3.0], builds >=3-sample value runs, **splits the run list at any
upward jump of >3 (the next play's 40-reset) and keeps only the segment covering t_freeze** —
without that split the chain walks into the next play's countdown, which is exactly how play
115 (whose coarse mark lands 2.25s AFTER its own snap) first regressed to a 4.65s error during
integration. It then takes the longest chain of runs consistent with "-1 per ~1.0s",
tolerating a dropped leading digit on single-digit reads and bridging unreadable gaps with the
period, and returns the last link's transition time.

Shipped parameter values are the MIDDLE of the measured plateau (bracket 1.3-1.4s, offset
0.60-0.65s, read guard 0.60-0.95 all score 16/20), not an edge: 1.5s also scores 16/20 but
implies a missed tick and is not physically motivated; 1.2s drops to 15/20.

**Final measured performance of the shipped `refine_snap` vs `truth_v3` (20 plays):**

| play | truth_v3 | shipped | err | src |
| --- | --- | --- | --- | --- |
| 5 | 89.60 | 89.45 | 0.15 | motion-sustained |
| 12 | 262.80 | 262.85 | 0.05 | motion-sustained |
| 15 | 318.40 | 318.30 | 0.10 | **playclock-tick** |
| 25 | 514.35 | 512.00 | 2.35 | playclock-bracket |
| 33 | 702.20 | 702.00 | 0.20 | playclock-bracket |
| 40 | 848.20 | 848.35 | 0.15 | motion-sustained |
| 48 | 1016.20 | 1016.00 | 0.20 | playclock-bracket |
| 55 | 1252.00 | 1252.00 | 0.00 | playclock-bracket |
| 63 | 1393.00 | 1393.05 | 0.05 | motion-sustained |
| 71 | 1562.20 | 1561.75 | 0.45 | motion-sustained |
| 73 | 1619.90 | 1620.00 | 0.10 | playclock-bracket |
| 78 | 1697.60 | 1697.55 | 0.05 | motion-sustained |
| 85 | 1814.80 | 1815.05 | 0.25 | motion-sustained |
| 92 | 1922.00 | 1922.00 | 0.00 | playclock-bracket |
| 100 | 2130.60 | 2130.00 | 0.60 | playclock-bracket |
| 105 | 2281.20 | 2281.00 | 0.20 | playclock-bracket |
| 115 | 2462.75 | 2462.90 | 0.15 | **playclock-tick** |
| 120 | 2585.80 | 2585.55 | 0.25 | motion-sustained |
| 125 | 2685.20 | 2685.15 | 0.05 | motion-sustained |
| 133 | 2895.60 | 2895.15 | 0.45 | motion-sustained |

**median 0.150s, P90 0.450s, 16/20 (80%) within +/-0.3s** — clears the >=16/20 wiring gate.
Was 14/20 / 0.200s / 0.850s before A15. The two remaining >0.5s misses are plays 25 (play
clock in its red sub-5s state, OCR unusable, and the coarse mark 2.4s early) and 100
(digit-box read rate 34/70, terminal ticks never seen) — both correctly fall through the
read-rate guard to the unchanged A2/A3/A4 behaviour rather than being given a bad tick answer.

Calibration artifacts now live IN the repo at `references/calibration/` (`truth_v3.csv`,
`truth_v2.csv` kept for auditability, `score_snap_estimator.py`, `truth_v3_scores.json`) —
A13's entry pointed at a session scratchpad that no longer exists; this one does not.

`2028-rutgers-vs-northwestern` was re-cut end to end (`snap_times.py` + `frames.py`).
`2028-unc-vs-illinois` could NOT be re-cut: its directory is empty, the video having been
archived to Drive and deleted locally by `archive_sweep.py` (same situation A12 recorded for
maryland/baylor). Its frames remain on pre-A15 snap times until the original is re-fetched.

**A15b out-of-window guard widened for the tick lane.** The first full re-cut with A15 moved
25 of 133 plays (all via `playclock-tick`) but BLANKED 5 that previously had a snap (4, 59,
62, 82, 91: 9 -> 14 windows with no play-clock snap). Cause: `snap_times.py`'s out-of-window
guard allowed only `t_last + 1`, and on those plays the segment lane closes the window at the
play-clock RESET, which fires before the actual snap — so the (correct) tick answer landed
past `t_last`. Two of the five are in the calibration set and confirm the tick lane was right
and the WINDOW wrong: play 62 -> 1393.0 vs truth_v3 1393.00, play 91 -> 1922.1 vs truth_v3
1922.00. Their previous values were `t_last` itself (an A4 edge pin, ~2s early, already
flagged unreliable).

The tail tolerance is now 2.0s for `snap_src == "playclock-tick"` and unchanged (1.0s)
otherwise; the head tolerance is unchanged, since a snap BEFORE its window is still a genuine
escape into a neighbouring play. 2.0s is the principled bound (one 1.0s clock period +
`TICK_OFFSET` + slack), and it is deliberately NOT widened further: that recovers plays 4 and
62 but leaves 59 (+2.1s), 82 (+2.5s) and 91 (+3.1s) blanked, because their segment windows are
wrong by more than a clock period. Play 91 is the clearest case — its tick answer 1922.1
matches truth_v3 to 0.1s while sitting 3.1s past its own window `[1912, 1919]`. Swallowing a
3.1s excursion would defeat the guard's purpose (catching a reset search that escaped into a
neighbouring play), so **the residual is logged as a segment-lane windowing defect, not fixed
here.** Those three plays fall through to frames.py's motion estimate, which is no worse than
the ~2s-early unreliable edge pin they had before.

**Net effect of the full re-cut on `2028-rutgers-vs-northwestern`:** 25 of 133 plays moved,
all onto the new `playclock-tick` source; play-clock-lane coverage 119 -> 121 of 133; windows
with no play-clock snap 9 -> 12; final `snap_src` breakdown motion-sustained 60,
playclock-bracket 39, playclock-tick 22.
