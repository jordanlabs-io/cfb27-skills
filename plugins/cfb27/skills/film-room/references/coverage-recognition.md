# Coverage Recognition: Visual Decision Tree for Charting Agents

Read `charting-prompts.md` first — this file is a companion reference for the specific judgment call of naming `def_coverage` (and its supporting fields `def_shell_pre`, `def_cb_technique`, `def_coverage`, `def_zone_type`, `def_safeties_post`) from the frame set. It never overrides the schema or the calibration-locked rules there; it exists because "which family am I looking at" is the single highest-stakes, most base-rate-biased call in the pipeline. **`def_rotation` is not a charted field** — `assemble.py` derives it from `def_shell_pre` vs. `def_safeties_post`; do not invent a value for it here.

Citation convention: `([[<transcript-filename>|Short Title]] **[MM:SS]**)` for transcript-backed claims, `(general knowledge)` for football fundamentals with no transcript citation (mostly the frame-mechanics of *this specific vision pipeline*, which the source creators never discuss since they aren't watching contact-sheet stills).

## 1. Decision tree, keyed to frame offsets

**Step 1 — Presnap shell, -1.2s (`presnap.jpg` / `fullframe.jpg`).** Count deep safeties. This is the first read by design — three independent creators converge on "count the deep safeties first" as the starting diagnostic ([[03-super-bowl-champ-breaks-down-identifying-cover-3-vs-man-cove|Identifying Cover 3 vs. Man]] **[00:00]**; [[09-how-to-read-madden-defense-like-an-nfl-qb|How To Read Madden Defense]] **[00:55]**–**[01:50]**; [[20-every-defensive-coverage-explained-in-15-minutes|Every Defensive Coverage Explained]] **[00:42]**). Two deep = `def_shell_pre: 2-high` (cover-2/2-man/4/6 family). One deep = `def_shell_pre: 1-high` (cover-1/3/3-match family). No deep safety, corners pressed, extra rushers = `def_shell_pre: 0-high` (cover-0).

**Step 2 — Post-snap safety count, +0.9 to +1.5s (`snap2`/`snap3`, ghost trails).** Confirm or contradict the presnap shell at the top of the drop — `def_safeties_post` is read here, never presnap. A shell that holds is "sitting"; a shell that changes count is a rotation (see §3). This single comparison is the schema's stated primary separator of quarters/2 from 3/1.

**Step 3 — CB technique, snap through +0.9s.** Press-and-turn-to-run (`bail`) at the snap is a man/match tell; off-and-settle-eyes-in is a zone/spot-drop tell. Sam's condensed checklist ties depth and technique together explicitly: "if the safeties are both deep and corners are off, it's probably cover [three]. If they're pressed, safeties are deep, corners are pressed up, cover two, man" ([[02-master-defense-with-these-college-football-26-coverage-tips|Master Defense]] **[16:27]**–**[17:30]**).

**Step 4 — Hook/curl/flat defender presence, +0.9 to +2.1s.** A defender staying square and settling into an underneath zone bubble (not traveling with any one receiver) is the flat/hook-defender tell that rules out man; a defender who latches onto a specific receiver and travels with him through the frame set rules out spot-drop zone.

### 4a. Cover-1 vs. cover-3 branch

Both often show `def_shell_pre: 1-high` AND `def_safeties_post: 1` — the shell alone does not separate them. The tell is CB technique plus hook-defender behavior, not safety count:

- **Cover-1 tell:** CBs press and turn-and-run with a receiver (`def_cb_technique: press`, travels downfield tracking one man); no defender settles into an underneath hook/curl bubble — everyone underneath is also traveling with a man.
- **Cover-3 tell:** at least one underneath defender (hook or curl) stays square, gets depth, and settles — eyes on the QB, not glued to a receiver (general knowledge — this is the operational definition of `def_zone_type: spot-drop` vs. `man` in the schema table). CBs are more often `off` and bail to a deep third than press-turn.
- **Rule 1 fallback when available:** against 3x1 (trips), safety and nickel aligned on the *same* side is cover-1 by rule — no zone coverage places them together ([[02-master-defense-with-these-college-football-26-coverage-tips|Master Defense]] **[01:18]**, **[17:30]**; [[03-super-bowl-champ-breaks-down-identifying-cover-3-vs-man-cove|Identifying Cover 3 vs. Man]] **[05:55]**, **[06:48]**). Chart this as the `saf_nickel_trips_side: both` tell field, not as a coverage conclusion.
- If neither tell is legible in the frame set (CB technique ambiguous, no hook defender visible, trips test not applicable), do not force a call — see §4 "do not commit."

### 4b. Cover-2 vs. cover-4 vs. cover-6 branch

All three commonly show `def_shell_pre: 2-high`. Separate by safety depth/leverage and CB technique, plus field/boundary asymmetry for cover-6:

- **Cover-2 tell:** CBs press with safeties deep over the top; corners squat on outside receivers rather than carrying them deep, because they have safety help — Benkert's cover-2-man depth benchmark applies here ([[11-how-to-play-madden-like-an-nfl-qb|How To Play Madden]] **[12:39]**, cited via [[identifying-man-vs-zone]]). `def_zone_type: man` when CBs are pressed and traveling; a true cover-2 zone shows CBs squatting the flat, not traveling.
- **Cover-4 (quarters) tell:** safeties sit noticeably lower and flatter-footed than cover-2/3 safeties, around 10–12 yards, because of run-fit responsibility ("the safeties are about 10 to 12... they're going to be inching back very slowly," [[02-master-defense-with-these-college-football-26-coverage-tips|Master Defense]] **[13:57]**–**[15:15]**). CBs are more often off, reading #2's release rather than pressed and locked. If CBs and safeties are both around 5 yards deep with press technique, that is Sam's quarters benchmark for a tighter variant, not cover-2 (**[16:27]**–**[17:30]**).
- **Cover-6 tell — the one call the derivation cannot make on its own:** the frame set must show a genuine field/boundary (or strength/weak) asymmetry — quarters technique (safety sitting ~10-12, CB off, reading #2) on one half of the field, and cover-2 technique (CB press/squat, safety deep over top) on the other half, simultaneously. Schema note: `def_coverage: cover-6` is one of the few families the automated derivation cannot infer from `def_shell_pre`/`def_safeties_post`/`def_cb_technique` alone — it needs a positive visual read of the split, so only chart it when both halves are legible in the same frame set. If only one side of the field is visible or legible, do not guess cover-6 from a single-side read.

## 2. Per-family table

| Family | Safeties | Corners | Hook/flat defenders | Tell that confirms | Tell that rules out |
|---|---|---|---|---|---|
| **cover-0** | 0 deep pre- and post-snap | Press, no help over top | N/A — extra rushers, no coverage shell | Extra rushers, no safety ever gets deep, corners locked man tight ([[20-every-defensive-coverage-explained-in-15-minutes\|Every Defensive Coverage Explained]] **[00:42]**) | Any defender getting to a deep third or deep half |
| **cover-1** | 1 deep, holds post-snap | Press, turn-and-run with a receiver | None settle into a zone bubble — everyone underneath travels with a man ([[20-every-defensive-coverage-explained-in-15-minutes\|Every Defensive Coverage Explained]] **[01:29]**) | Safety+nickel same side vs. trips ([[02-master-defense-with-these-college-football-26-coverage-tips\|Master Defense]] **[01:18]**) | A hook/curl defender staying square and settling on a landmark |
| **cover-2** | 2 deep halves, holds | Press, squat the flat (help over top) | Flat defenders present, corners not carrying vertical alone | Corners press + safeties deep over top ([[11-how-to-play-madden-like-an-nfl-qb\|How To Play Madden]] **[12:39]**) | Safeties sitting low (~10-12yd) rather than deep-half depth |
| **cover-2-man** | 2 deep halves, holds | Press, travel with a receiver (man, not squat) | N/A — LBs/nickel also man, not zone-settling | Same shell as cover-2 zone but CBs travel downfield with a receiver instead of squatting the flat | A hook/curl/flat defender settling on a spot rather than a man |
| **cover-3** | 1 deep, holds | Off, bail to a deep third | At least one defender settles square in a hook/curl bubble, re-routes but doesn't chase ([[cover-3-family-and-variations]]) | Safeties deep + corners off ([[02-master-defense-with-these-college-football-26-coverage-tips\|Master Defense]] **[16:27]**) | A hook defender that travels with one man the whole route (that's match, see below) |
| **cover-3-match** | 1 deep, holds | Off, bail to deep third | Defenders latch onto a numbered receiver post-snap and travel with him rather than settling (**[05:27]**, [[cover-3-family-and-variations]]) | A receiver "runs scot-free" through what should be a settled zone — matched defender missed his numbered assignment (**[09:04]**) | Underneath defenders visibly re-routing and hovering rather than traveling |
| **cover-4 (quarters)** | 2 deep, holds, sit ~10-12yd | Often off, reading #2's release | Quarter-flat defender relates to #2, big-eyes #3 (**[03:13]**–**[04:12]**, [[cover-4-match-rules]]) | Safeties flat-footed and lower than cover-2 depth ([[02-master-defense-with-these-college-football-26-coverage-tips\|Master Defense]] **[13:57]**) | Safeties at true deep-half depth (cover-2) or corners pressed and locked (cover-2-man) |
| **cover-6** | 2 deep pre-snap; post-snap splits — one half quarters depth, one half cover-2 depth | Asymmetric by half: off/reading on the quarters side, press/squat on the cover-2 side | Present on both halves but with different jobs per half (**[02:03]**, [[cover-6-and-cover-9-split-field]]) | Visible field/boundary depth-and-technique asymmetry in the SAME frame set (both halves legible) | Only one half of the field visible/legible — cannot confirm the split |

## 3. Disguise and rotation

A 2-high shell that spins down to 1-high between the presnap frame and the +0.9-1.5s snap frames is a **rotation**, and it is the single most common way this game disguises a call — do not treat a presnap read as final. Fourth and Film independently corroborates the cover-3-buzz version of this: two safeties show a cover-2 look presnap, then one drops down to an underneath zone after the snap while the corners bail to deep thirds, disguising the eventual cover-3 shell from what looked like cover-2 ([[20-every-defensive-coverage-explained-in-15-minutes|Every Defensive Coverage Explained]] **[11:04]**–**[11:48]**). Sam separately documents the same mechanism in CFB26 terms — the buzz defender comes down from depth into the hook while the weak backer becomes the new curl-flat defender ([[01-breaking-down-every-cover-3-variation-in-college-football-26|Cover 3 Variations]] **[12:45]**–**[13:43]**).

A shell that shows no change in safety count or depth between presnap and the snap-window frames — same look at -1.2s and at +1.5s — is **sitting**, not disguising. Chart `postsnap_confirms: yes` in that case per the schema; a shell that changes count is `postsnap_confirms: no`.

Sam's caution on over-disguising cuts both ways for a charting agent: real coaches limit how much they rotate because it can put their own players out of position ("I always tell don't do shells because I don't want my guys out of position trying to disguise a look," [[02-master-defense-with-these-college-football-26-coverage-tips|Master Defense]] **[15:15]**) — so a rotation, when it does appear in the frames, is a deliberate and visually legible event, not subtle noise to be inferred from ambiguous stills. If the rotation itself isn't clearly visible across the snap-window frames, don't chart one.

No field/boundary (short-side/wide-side) asymmetry claims specific to CFB26/27's engine appear in the transcripts sourced for this reference beyond the cover-6 split-field structure already covered in §1.4b and §2 — the source material frames field/boundary distinction only within cover-6's quarters-vs-cover-2 half split, not as a general engine-specific tendency. Do not extend beyond that without a transcript citation.

## 4. Do-not-commit rules

`def_coverage` (and its supporting fields) go to `unknown` — never to a guess, and never to `cover-3` as a fallback — whenever any of the following holds for a given play window:

- The ball is snapped away from the safeties (they are cropped out of frame, or the play direction pushes the read out of the captured area) before the shell can be confirmed at the top of the drop.
- The camera cuts mid-play (a replay, angle change, or menu takeover interrupts the snap-through-drop window) before `def_safeties_post` is legible.
- A play-art/HUD overlay covers the coverage read itself (see §5) rather than merely coexisting with a visible field.
- CB technique is genuinely mixed or unreadable and no hook/flat defender is visible settling or traveling — i.e., none of the §1 tells resolve.
- Only one half of the field is legible when a cover-6 split-field call is suspected (§1.4b).

State plainly, per the schema's own calibration-locked rule: **"unknown" beats a guess.** Cover-3 (and cover-3-match) is the majority class among this offense's opponents' tendencies in this vault's charted sample, which is exactly why it is the highest-risk default — a model that is uncertain and reaches for the majority class will systematically overcount cover-3 and understate the rest of the family tree. Base rate is never a tiebreaker over an uncertain vision read. When the tells in §1 don't resolve, output `unknown`, not the class you'd bet on blind.

## 5. CFB27 play-art overlay contamination

CFB27 draws coach's-own-screens (play-call menus, coverage-adjustment panels, custom-adjustment screens) as panels that can appear ON TOP of a live pre-snap field — this is expected chrome, not a non-play (see `charting-prompts.md`'s calibration-locked rules on menu overlays). Separately, the dedicated `playart.jpg` pair sometimes shows an actual route/zone diagram: the play art itself, not gameplay pixels. When a play-art or route-diagram overlay is visible in ANY of the provided frames and that overlay is what informs a coverage-family read (rather than an incidental panel the agent charted around), the resulting read is coming from a schematic drawing of the intended call, not from what the defense actually did on the snap.

The schema already partitions this correctly at the field level: `def_playart_coverage` exists specifically for a coverage name read off a genuinely visible play-art overlay, and it is explicitly the ONE place alignment-only naming of a family is allowed, because the art IS the call being displayed (`charting-prompts.md` step 1a2). **Never let `def_playart_coverage`, `def_playart_zones`, or `off_playart` substitute for or overwrite `def_coverage`** — the latter must still come from what the players actually do post-snap, per the schema's own separation of these fields. If an agent notices that its post-snap coverage read was effectively reconstructed from a visible overlay rather than from player movement (for example, because the players themselves are obscured by the panel across the whole snap window), that is a case for `def_coverage: unknown` with a `note` flagging the overlay as the reason — not for silently filling `def_coverage` with the overlay's own content under a different name. Downstream analysis that wants to distinguish an overlay-derived read from a vision-derived one should look for a populated `def_playart_coverage` alongside an `unknown`/thin `def_coverage` on the same play, rather than expecting a `src` tag that does not exist in the current schema.

## NFL priors (Big Data Bowl 2026, 2023 season, n=14,066 pass plays) — (external data, not transcript-sourced)

### Shell (9yd depth threshold) -> coverage family, row-normalized

| Shell | cover-0 | cover-1 | cover-2 | cover-2-man | cover-3 | cover-4 | cover-6 | n |
|---|---|---|---|---|---|---|---|---|
| 0-high | 42.2% | 27.0% | 4.1% | 0.0% | 13.1% | 12.7% | 0.9% | 953 |
| 1-high | 2.3% | 35.4% | 9.6% | 0.5% | 42.1% | 7.3% | 2.8% | 5759 |
| 2-high | 0.8% | 12.8% | 16.8% | 3.1% | 24.3% | 25.0% | 17.2% | 6485 |
| 3-high | 1.6% | 5.6% | 18.1% | 0.9% | 41.0% | 20.9% | 11.9% | 869 |

### Overall coverage family distribution

| Family | k/n (pct) |
|---|---|
| cover-0 | 601/14066 (4.3%) |
| cover-1 | 3175/14066 (22.6%) |
| cover-2 | 1837/14066 (13.1%) |
| cover-2-man | 237/14066 (1.7%) |
| cover-3 | 4482/14066 (31.9%) |
| cover-4 | 2346/14066 (16.7%) |
| cover-6 | 1388/14066 (9.9%) |

### Safety rotation rate by pre-snap shell (corrected: FS/SS or CB-at-safety-depth only, not all defenders)

Rotation measured only on players who are FS/SS, or a CB aligned at safety depth pre-snap (frame-1 depth ≥ 9yd) — this excludes zone-dropping LBs/CBs that a naive all-defenders shell count would pick up. deep_pre = that subset with depth ≥9yd at frame 1; deep_post = with depth ≥12yd at ~+2.0s. roll-down = deep count decreased, bail = increased, sat = unchanged.

Overall safety rotation rate: 4061/14066 (28.9%)

| Shell at snap | rotated k/n (pct) | roll-down | bail | sat |
|---|---|---|---|---|
| 0-high | 124/953 (13.0%) | 0.0% | 13.0% | 87.0% |
| 1-high | 999/5759 (17.3%) | 8.3% | 9.1% | 82.7% |
| 2-high | 2514/6485 (38.8%) | 38.1% | 0.6% | 61.2% |
| 3-high | 424/869 (48.8%) | 48.0% | 0.8% | 51.2% |

### Disguise baselines

- **Disguised cover-3** (2-high-at-snap, labeled cover-3, and rolled down): 1156/6485 (17.8%)
- **Cover-1 from 2-high** (started 2-high, played cover-1): 828/6485 (12.8%)

### Coverage family by down and distance

| down | cover-0 | cover-1 | cover-2 | cover-2-man | cover-3 | cover-4 | cover-6 | n |
|---|---|---|---|---|---|---|---|---|
| 1 | 3.1% | 16.4% | 13.2% | 0.9% | 37.6% | 18.5% | 10.4% | 5141 |
| 2 | 3.6% | 19.4% | 13.0% | 1.1% | 31.3% | 19.7% | 11.8% | 4687 |
| 3 | 5.7% | 33.1% | 13.2% | 3.3% | 25.9% | 11.5% | 7.4% | 3873 |
| 4 | 13.7% | 38.4% | 11.0% | 3.3% | 21.1% | 8.5% | 4.1% | 365 |

| distance | cover-0 | cover-1 | cover-2 | cover-2-man | cover-3 | cover-4 | cover-6 | n |
|---|---|---|---|---|---|---|---|---|
| short (≤3) | 14.4% | 34.2% | 10.2% | 1.7% | 25.7% | 8.5% | 5.3% | 1477 |
| medium (4-6) | 6.5% | 33.2% | 11.1% | 2.1% | 27.1% | 12.7% | 7.4% | 2265 |
| long (7-10) | 2.4% | 20.2% | 13.0% | 1.5% | 34.3% | 18.2% | 10.4% | 8465 |
| very long (11+) | 2.2% | 11.2% | 18.1% | 1.9% | 31.6% | 21.1% | 13.9% | 1859 |

### How to use

These are NFL base rates (2023 season, Big Data Bowl 2026 tracking data) — not CFB27 truth. Use them only to (a) set the agent's prior when frames are ambiguous, i.e. which family is *statistically* more likely given shell/down/distance before the vision tells resolve it; (b) sanity-check a coach's disguise rate in query_plays.py's `disguise` output against the NFL 2-high roll-down rate (38.8%) — a coach whose rate is wildly out of this range is worth a second look, not proof of anything; (c) never to fill a field the frame does not support — `unknown` still wins per §4's do-not-commit rules regardless of what these priors say is likely. On the 3-high row specifically, do not apply the NFL's low-frequency prior at face value — `4-2-5 3-High` is a CFB27 base formation, not a rare/prevent shell, per the "CFB27 call → coverage cross-reference" section below.

Three caveats, explicitly:
1. **Frame 1 is near-snap, not frozen pre-snap** — some presnap shifting/motion is already underway by frame 1 in the tracking data; it is the earliest available reference, not a truly static presnap instant.
2. **The 9yd/12yd depth thresholds are analyst choices**, not a rule of the NFL rulebook or CFB27's engine — sensitivity analysis in priors.md shows the shell distribution shifts meaningfully across 8/9/10/12yd thresholds.
3. **NFL ≠ CFB27 AI defense.** These are human NFL defensive coordinators and players in 2023; CFB27's defensive AI has no obligation to match NFL tendencies, disguise rates, or shell distributions. Treat every number above as an outside reference point, never as ground truth for this game.

## CFB27 call → coverage cross-reference (Airtable "CFB 27 Schemes", civil.gg-derived; external, not transcript-sourced)

Source: Airtable base "CFB 27 Schemes" (`appu56SmvCabWRjm0`), table `Plays` (`tblcKblLELnS8Ay0y`), 34 records with a non-empty Play Call as of 2026-09-08. This is the user's own scheme-building reference, sourced from Civil's (civil.gg) CFB27 defensive playbook — it names the actual in-game call, formation, and macro settings, not a transcript claim, and is kept separate from the transcript-sourced tables above per this vault's citation rules. Rows below collapse exact duplicate (Formation, In-game call, Role Detail) triples from the 34 source records; "(varies)" marks a call that ships more than one macro/Role Detail combination in the base.

| Formation | In-game call | Coverage played after macros (Role Detail) | Pre-snap look / disguise cue | Scheme |
|---|---|---|---|---|
| 6-1 | Sam Will Blitz | (varies — no Role Detail set) | 61 BASE macro (Pinch DL, Route Commit Inside, Contain); Curl Flat OLB assignment varies by package (both/one/none); Pistol/Under Center variant runs "Cover 2 shell, user weakside safety over MLB" | Cover 2 / Cover 3 / Mixed (context-dependent — Gun vs. Pistol/Under Center changes the base shell) |
| 6-1 | Sam Will Blitz | Coverage Shading: Inside · Route Commit: Inside · QB Contain: Both · Technique: Pinch | 61 BASE macro + man top safety to isolated WR, cloud-flat outside CB to isolated side (bunch/trips changeups) | Mixed (man-heavy bracket coverage) |
| 6-1 | Sam Will Blitz 3 | QB Contain: Both · Technique: Pinch · Zone Strategy: Aggressive · CB1/CB2: Outside Third · FS/SS: Inside Quarter | 5 Wide D macro — Inside Quarter both safeties, Outside Third both corners | Cover 3/4 |
| 6-1 | Cover 4 Quarters | — | Cover 4 Quarters shell, CB depth 3/width wide, safety width spread; Spread DL then Texas 4 Man/El Paso 4 Man | Cover 4 |
| Nickel 3-3 Cub | Tampa 2 | — | Redzone package; spy the blitzing OLB | Cover 2 |
| Nickel 3-3 Cub | Mike Blitz 0 | Route Commit: Inside · QB Contain: Both · Technique: Pinch · FS: Deep Half · SS: Deep Half · SLB1: Hook Curl | Max-man, 2-high shell; Deep Half both safeties (macro) | Cover 2 Man |
| Nickel 3-3 Cub | Mike Blitz 0 | Route Commit: Outside · Technique: Pinch | Man version with deep-safety help; man the HB, inside-third that safety | Cover 1 Man |
| Nickel 3-3 Cub | Mike Blitz 0 | — | RPO answer; Hard Flat the OLB on the RPO side | Man |
| Nickel 3-3 Cub | Cover 4 Quarters | — | Lockdown-run package; Texas 4 Man stunt | Cover 4 |
| Nickel 3-3 Cub | 3 Sam Will Blitz | (varies — no Role Detail set) | Prevent package (Inside Quarter both safeties) OR shotgun-run keying package | Cover 4 / (unset) |
| Nickel 3-3 Cub | 3 Sam Will Blitz | Technique: Pinch · SLCB1: Vertical Hook · FS: Inside Quarter · SS: Inside Quarter · LEDG/REDG: Hard Flat · SLB1: Blitz | "Counter" user blitz; Inside Quarter both safeties (macro) | Mixed |
| Nickel 3-3 Cub | 3 Sam Will Blitz | Technique: Pinch · Zone Drop defaults · FS: Inside Quarter · SS: Inside Quarter | 5-Wide vs. empty; Inside Quarter weak-side safety | Mixed |
| Nickel Wide | Cover 4 Quarters | — | Heavy-run answer; Texas 4 Man stunt, user weakside safety | Cover 4 |
| 4-2-5 3-High | 3 Double Cloud | QB Contain: Both · Technique: Pinch · Stunts: Left Pirate 3 Man · CB1/CB2: Curl Flat | Base zone call; both corners set to Curl Flat outside | Cover 3 |
| 4-2-5 3-High | 3 Double Sky | QB Contain: Both · Technique: Pinch · Stunts: Left Pirate 3 Man | Pinch DL, Pirate/Texas/El Paso 4 Man stunt options, optional Hook Curl 1 Quarter Flat | Cover 3/4 |
| 4-2-5 3-High | LB Blitz 0 | QB Contain: Both · Technique: Left/Right · LEDG/REDG: Curl Flat · SLB1/2: Hook Curl | Shift DL left/right, curl-flat the opposite DE, shade coverage inside, route-commit inside | Cover 0 Man |
| 4-2-5 3-High | Hot Blitz 3 | QB Contain: Both · Technique: Left/Right · LEDG/REDG: Curl Flat · SLB1/2: Hook Curl | Shift DL left/right, curl-flat opposite DE, user opposite LB, optional curl-flat CB + outside-third safety same side | (unset — pressure package) |
| 4-2-5 3-High | Tampa 2 | QB Contain: Both · Technique: Pinch · Stunts: Left Pirate 3 Man | Pinch DL, stunt options, optional shade underneath, optional drop hook-curl zones to 5 | Cover 2 |
| 4-2-5 3-High | Cover 4 Quarters | QB Contain: Both · Technique: Pinch · Stunts: Left Pirate 3 Man | Pinch DL, Pirate stunt, contain | Cover 4 |
| 4-2-5 3-High | Any Base Coverage | Technique: Spread · Stunts: Texas 4 Man | Run-defense overlay layered on whichever base coverage is set | (unset — layered call) |
| Nickel 2-4 Single Mug | Cover 3 Cloud | (varies — no Role Detail set) | RPO-read seminar OR shotgun run-support loop | Cover 3 |
| Nickel 2-4 Single Mug | Cover 3 Cloud | Technique: Spread · Stunts: Texas 4 Man | Spread DL, Texas 4 Man, **Cov 2 shell on**, User on HB side | Cover 3 |
| Nickel 2-4 Single Mug | Cover 3 Cloud | Technique: Spread · SLB1: Blitz | Spread DL, Contain, Blitz SubLB1, optional zone-out backside DE | Cover 3 |
| Nickel 2-4 Single Mug | Cover 3 Cloud | Technique: Spread · Stunts: Left Tex 2 Man | Spread DL, Left/Right Tex 2 Man stunt, User to HB side — contains rollouts | Cover 3 |
| 3-3-5 Mint | Cover 3 Cloud | — | Contain + Drag Blitzing OLB Outside (new blitz concept) | Cover 3 |
| Nickel 2-4 Single Mug | Cover 4 Quarters | — | Spread DL, Texas 4 Man/Slant DL Outside vs. outside runs, User a High Safety | Cover 4 |
| Nickel 2-4 Single Mug | Cover 2 Man | Technique: Spread · Stunts: Texas 4 Man/Left Tex 2 Man · Coverage Shading: Inside · Route Commit: Inside · CB Depth: Press | Spread DL, **Press** + Shade + Commit Inside | Cover 2 Man |

### What this means for recognition

- **`4-2-5 3-High` is a BASE alignment in CFB27, not a rare/prevent look.** From this one formation the base plays cover-3 (3 Double Cloud, 3 Double Sky), cover-4 (Cover 4 Quarters), cover-2 (Tampa 2), and cover-0 (LB Blitz 0). NFL priors on 3-high shells (rare, prevent-flavored) do not transfer — a 3-deep pre-snap read here must be treated as an everyday base call, not an outlier.
- **The call name lies about the eventual coverage.** "Cover 3 Cloud" (Nickel 2-4 Single Mug) is run out of a "Cov 2 shell on" macro — a 2-high pre-snap look that rotates to cover-3 post-snap is a scheme-level habit, not an exception. "Mike Blitz 0" plays Cover 2 Man or Cover 1 Man depending only on which Role Detail macro is attached (Deep Half both safeties → Cover 2 Man; Route Commit Outside + inside-third safety → Cover 1 Man). "Sam Will Blitz" plays Cover 3, Cover 2, or Mixed man-bracket coverage depending on package (Gun vs. Pistol/Under Center, or bunch/trips adjustments) — the same play call is not one coverage.
- **Cloud-flat corners are the cover-3-cloud vs. cover-3-sky tell.** 3 Double Cloud sets both corners to Curl Flat (cloud-flat) outside; 3 Double Sky instead runs a Pirate/Texas/El Paso stunt package with no CB cloud-flat assignment. When the frame set shows a corner squatting the flat rather than bailing to a deep third, that is the cloud variant, not sky.
- **Macros that change safety depth are the visible pre-snap/post-snap cues in this game.** Deep Half both safeties (Mike Blitz 0 → Cover 2 Man) sets true deep-half depth; Inside Quarter both safeties (3 Sam Will Blitz, Sam Will Blitz 3, prevent packages) sets the flatter ~10-12yd quarters depth described in §1.4b above; Outside Third both corners (Sam Will Blitz 3, 5 Wide D macro) is the corner-side counterpart that shows up alongside Inside Quarter safeties in split-field/5-wide answers. A charting agent should read which of these three macros is active as the primary explanation for a safety-depth change between the presnap and post-snap frames, rather than guessing at a coverage family from depth alone.

