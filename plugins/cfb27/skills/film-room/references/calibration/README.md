# Snap-estimator calibration set

`truth_v3.csv` — the current hand-verified snap truth for
`2028-rutgers-vs-northwestern` (20 plays). Labeled from coarse-anchored 5fps
montages on the SNAP→HIKE prompt transition, the PRE-PLAY/SUBS ("R") chip
disappearing, and the ball-carrier ring appearing; label = midpoint of the last
presnap and first post-snap frame (±0.1s). Supersedes `truth_v2.csv`, which is
kept only so the A13→A14 correction stays auditable — **do not score against
truth_v2**, it is late by up to 2.3s on four plays.

`score_snap_estimator.py` rescores the shipped `snap_refine.refine_snap`
against `truth_v3`. Current numbers (A15): median 0.150s, P90 0.450s,
16/20 within ±0.3s.

`truth_v3_scores.json` — per-play t_tick, offset, digit-box read rate.
