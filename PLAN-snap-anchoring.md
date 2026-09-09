# PLAN: film-room snap anchoring, PBP ground truth, stoppage criteria

Status: DRAFT for Opus pre-flight → Sonnet execution. Author: Fable advisor session 2026-09-09. Handoff from the Rutgers scouting session (measured on `~/CFB27-film/2028-rutgers-vs-northwestern`).

## Context

Two independent measurements say the per-play frame set is cut from the wrong moment:

- Rutgers session: `seg/snaps.csv` snap is 0.5–1.0s EARLY on plays 40 and 100 (847.0 vs ~848.0; 2130.0 vs ~2130.8). Cause: `snap_times.py` and `frames.py:pc_stop_time` define snap = START of the terminal frozen play-clock second, but a value like "13" is legitimately on screen for up to a full second before it freezes, so the anchor is quantized early. Stacked offsets then make `presnap.jpg` ≈ −2.2s and end the post-snap window ≈ +2.3s, before coverage declares (+2.5–4s).
- Coverage labeling pass (2026-09-09, 60 UNC plays): 6/60 `presnap.jpg` frames were already post-snap (anchor LATE, consistent with `timeline_snaps.py` taking `run[-1]`, up to 4s late), 10/60 frames carried menu panels, and the vision agent declined coverage on 37/60 mainly because the post-snap frames stop before the deep structure settles.

So there are two estimators with opposite biases (`snap_times`/`pc_stop_time` early, `timeline_snaps` late), no sub-second refinement, and a post-snap window that ends too soon. Only one lane of ground truth exists for the play list (postgame play-by-play on UNC-recorded games) and it is prose-joined, not scripted.

## Goals (definition of done)

1. Snap anchor within ±0.3s of the true snap on ≥90% of plays on the calibration film, measured against a hand-verified set (plays 40, 100 + 18 more sampled across quarters).
2. One snap estimator path with explicit precedence and a `snap_src` column written to `seg/snaps.csv` and carried into `plays_charted.csv`.
3. Pre-snap frames at −2.0s (pre-shift look) and −0.4s (last look), post-snap at +0.5, +1.5, +2.5, +3.5, +4.5.
4. Lane A stage: postgame PBP tail → `seg/pbp.csv` → reconciliation report against `seg/plays.csv` (window count, dd, quarter, sequence), scripted and re-runnable.
5. Written stoppage/boundary criteria in SKILL.md, each measured on the calibration film.
6. All existing verifiers pass; `validate_chart.py` passes on the calibration game.

## Work items

### W1. Sub-second snap refinement (`frames.py`, `snap_times.py`)
- Keep the play-clock freeze as the coarse bracket: `[t_freeze, t_freeze + 1.2]`.
- Inside the bracket, sample the field crop at 10 fps and take the first sustained motion onset (reuse `motion_onsets` machinery with a finer step; threshold from the same percentile logic). Record `snap_src=playclock+motion`.
- If the pre-flight confirms a fixed-position HUD snap prompt (HIKE/SNAP), add a template matcher (`cv2.matchTemplate` on a cropped band, template captured once from the calibration film, stored under `references/hud-templates/`) and prefer it: `snap_src=hud-prompt`. If not confirmed, skip; do not build on an unverified glyph.
- `snap_times.py` writes the refined value; `frames.py` `_snap_override` keeps precedence but now gets the refined number. `pc_stop_time` gets the same refinement so the in-process path agrees.
- `timeline_snaps.py`: stop using it as a snap source. Keep it for `sec_since_prev_snap`/`tempo` only, computed from the refined snaps. SKILL.md step 8 wording changes accordingly.

### W2. Frame offsets (`frames.py`)
- `PRESNAP_OFFSETS = [-2.0, -0.4]` → `presnap_shift.jpg`, `presnap.jpg`.
- `STRIP_OFFSETS = SNAP_SINGLES = [0.5, 1.5, 2.5, 3.5, 4.5]` (strip becomes 5 cells + `presnap` as cell 1 so the 3×2 grid stays).
- `PREPLAY_OFFSETS` unchanged (play-art window is separate).
- Bump `frames.py` schema/version note so old game dirs are recognizable (`meta.txt` gains `frames_version=2`).

### W3. Re-grab gate (`frames.py:hud_says_presnap`)
- Replace fail-open OCR with: (a) HUD prompt template if W1 confirmed it, else (b) motion check: if the field crop shows no sustained motion in `[snap, snap+1.0]`, the anchor is early → advance to the next onset. Never silently fail open; write `anchor_gate=<result>` to `meta.txt`.

### W4. Postgame PBP ground truth (new `pbp_ingest.py`, new `pbp_reconcile.py`)
- Input: the tail of a Lane A recording (last N minutes) or a screenshot set. `pbp_ingest.py` samples 1 fps, dedupes screens (reuse `menu_ingest.py` dhash), OCRs the PBP table rows (tesseract on the table band; vision-agent fallback batch file if OCR confidence is low), and writes `seg/pbp.csv` with `qtr, clock(if shown), dd, spot, text, play_type, result, yards, scoring`.
- Pre-flight must confirm whether the PBP screen shows game clock per row. If yes, join key = (qtr, clock, dd) with monotonic sequence; if no, join key = (qtr, dd) monotonic sequence only, and clock proximity comes from the HUD timeline.
- `pbp_reconcile.py`: aligns `seg/pbp.csv` to `seg/plays.csv` with the monotonic rule already in SKILL.md (never nearest-clock alone), and prints: windows with no PBP row (candidate false windows or stoppage windows), PBP rows with no window (missed plays), dd mismatches, and per-quarter counts. Exit non-zero on <90% alignment. This becomes the Lane A calibration check for W1/W5.
- SKILL.md gains a Lane A stage "3b. PBP tail ingest + reconcile" and the 3a prose join now points at the script.

### W5. Stoppage / boundary criteria (`segment.py`, SKILL.md)
- Define explicitly, in this order, what closes a play window: (1) dd change; (2) play-clock reset upward >3 after ≥3 readings; (3) PRE-PLAY/SUBS tag; (4) score change; (5) quarter change. What does NOT close a window: motion stoppage of any length, unreadable HUD gaps ≤ `GAP_TOLERANCE`, replay overlay, menu return, timeout/injury/review screens (these extend the current window's dead time, they don't create a play).
- Remove the implicit 1.5s bracket assumption: the snap search runs over the whole window, using the last freeze before the next boundary, not a fixed bracket after the first freeze.
- Measure on the calibration film with `pbp_reconcile.py` before/after: window count vs PBP row count, dd agreement. Write the measured numbers into `references/calibration-history.md`.

### W6. Ship
- Bump plugin.json (minor). Commit, push, `claude plugin update cfb27@cfb27-skills`.
- Re-cut frames for the calibration game only (`frames.py --plays` on the 20-play verification set) and for the 60-play labeling set (three 2028 UNC games) so the labeling sheet can be regenerated with correct frames.

## Verification
1. Hand-verified snap set: extract 0.1s contact sheets for 20 plays on `2028-rutgers-vs-northwestern`, mark true snap, compare to `seg/snaps.csv` before/after. Report median and P90 error.
2. `pbp_reconcile.py` on one UNC Lane A game with a PBP tail: alignment ≥90%, exit 0.
3. Re-run the 60-play labeling frames and count `presnap.jpg` that are post-snap (was 6/60; target 0).
4. `validate_chart.py` on the calibration game; four CLAUDE.md verifiers exit 0.

## Open questions for pre-flight
- Does CFB27 render a fixed-position HIKE/SNAP HUD prompt? (Rutgers session says yes; the codebase has no reader for it.)
- Does the postgame PBP screen show per-row game clock? (SKILL.md 3a says no; Rutgers session says "timestamped".)
- Which existing films were cut by `timeline_snaps.py` vs `snap_times.py`? Reports name 5 films for timeline_snaps; the rest are ambiguous. Needed to decide whether to re-cut the labeling set.

## Pre-flight amendments (Opus, 2026-09-09) — these override the work items above

Evidence: play 40 true snap 848.0–848.1 (snaps.csv 847 → −1.0s); play 100 true snap ≈2130.15 (snaps.csv 2130 → −0.15s, within tolerance). Play clock "13" was on screen 0.8s before the snap. HIKE/SNAP chip is world-anchored at the LOS and absent on the endzone camera; the fixed-position PRE-PLAY/SUBS chip (≈x 0.03–0.19w, y 0.76–0.81h) disappears at the snap on both cameras. Pre-snap hot-route arrows produce frame-diff spikes of 19–26 vs baseline 3, so first-crossing motion fires ~1.8s early. Postgame PBP tail is a HIGHLIGHTS list (28 rows for ~130 plays), rows carry `time` MM:SS + prose but no quarter field. 21 of 29 film dirs have `snap_t` overwritten by `timeline_snaps.py` (1–9s late), including 2028-unc-vs-illinois (median +4s) and 2028-unc-vs-baylor (+5s); 2028-unc-vs-maryland is intact.

A1. **Interpreter.** System `python3` lacks numpy/cv2. First task: find the interpreter the skill actually runs under (SKILL.md / `_run` / a venv), record it in SKILL.md, and add a preflight check. Do NOT add an OpenCV dependency; the chip detector below is PIL + stdlib.
A2. **Primary snap estimator = PRE-PLAY chip clear.** Within bracket `[t_freeze − 0.5, t_freeze + 1.5]` (t_freeze from the 1 fps play-clock lane), sample full frames at 10 fps, crop the chip box (reuse `preplay_box` geometry, but the fixed chip box above, scaled by frame size), compute per-frame stddev/mean-diff of the crop; snap = first frame where the chip region goes uniform (stddev collapses / diff vs the pre-snap reference exceeds a threshold) and stays so for ≥0.5s. `snap_src=preplay-chip`. Handle white and red play-clock chips (irrelevant to this box but note for any play-clock crop).
A3. **Fallback = sustained non-returning motion** on the field crop at 10 fps inside the same bracket: onset where diff stays above baseline×2 for ≥1.0s with no sample returning to baseline. `snap_src=motion-sustained`. Do not reuse `motion_onsets` (it filters t ≤ t_last−5 and is first-crossing).
A4. **Play-clock freeze is a bracket, not an estimate.** If neither A2 nor A3 resolves, keep `t_freeze` with `snap_src=playclock-bracket` and `unreliable=True`.
A5. **Frames.** Replace the hardcoded `snap − 1.2` at frames.py ~421/~449 with `PRESNAP_OFFSETS = [-2.0, -0.4]` (`presnap_shift.jpg`, `presnap.jpg`; `fullframe.jpg` at −0.4). Rewrite `strip()` to a 3×2 of `[presnap(−0.4), +0.5, +1.5, +2.5, +3.5, +4.5]`, all cells grabbed at the same width; `SNAP_SINGLES = [0.5,1.5,2.5,3.5,4.5]`. Make the `frames.py:441` gate reference a named constant. `meta.txt` gains `frames_version=2` and `snap_src`.
A6. **Schema.** `snap_src` is a new column: add to `snaps.csv`, `chart_schema.py` field list, `assemble.py` passthrough, and check `validate_chart.py:152` gap logic still holds with fractional `snap_t`.
A7. **timeline_snaps.py** no longer writes `snap_t`; it computes tempo columns from the refined snaps. Add a one-line stderr note when run on a dir whose snaps.csv has no `snap_src` (old cut).
A8. **PBP (W4) redefined.** Input is a fresh Lane A tail capture (frames on disk), not menu-intel jsonl. `pbp_ingest.py` → `seg/pbp.csv` with `time, dd, spot, carrier, text, play_type, result, yards, quarter(inferred from enclosing quarter_score block or clock monotonicity)`. Join key `(clock, dd)` + monotonic sequence. Gate = ≥90% of PBP rows find a window; windows without a PBP row are expected (highlights subset) and are NOT flagged as false windows. Re-ingest the rutgers tail (`type: null` records) as the first test.
A9. **W5 becomes documentation + named deltas.** Document segment.py's current close rules (≥4s window, GAP_TOLERANCE 12, two consecutive pc≥25 after a pc<15). The only behavioral delta: the snap search uses the LAST freeze before the next boundary over the whole window (not a bracket after the first freeze). Any other change to segmentation is out of scope; do not retune window counts across 29 films.
A10. **Calibration claim.** Replace "0.5–1.0s early" with the measured distribution from the 20-play hand set; expect bimodal (large when the clock ticks just before the snap, near-zero otherwise). Write the numbers into calibration-history.md.
A11. **Re-cut scope.** Re-cut frames for 2028-rutgers-vs-northwestern (calibration), and the three labeling games (maryland, illinois, baylor) with the new estimator. Do not rechart. Leave tempo columns on the other 18 timeline_snaps films as-is; log them as a known debt in calibration-history.md.
A12. **Goal restated.** ±0.3s on ≥90% of hand-verified plays is reachable only with A2/A3 as primary; report it honestly if it is not met, with the per-play table.
