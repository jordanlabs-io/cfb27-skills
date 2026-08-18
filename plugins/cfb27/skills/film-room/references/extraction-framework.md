# Maximum-Extraction Charting Framework (v2, 2026-07-29)

Goal: extract every scouting-relevant datum a video model can read from a play clip,
with each field routed to the cheapest model that reads it reliably.

**Design rule (three validations deep, do not regress):** flash-class models read
*behaviors* (what a player physically does) at 70-90% agreement with pro, but fail
*abstractions* (what scheme that behavior implies) at ~40%. So: chart behaviors, derive
abstractions deterministically in `assemble.py`. Never ask flash for a scheme name.

## Man/zone WITHOUT the family call — the tell stack

Each tell is an independently observable behavior. `assemble.py` votes them into a
`man_zone_verdict`; no single tell decides, and `unknown`s abstain.

| Tell | Field | Man signal | Zone signal | Readability |
| --- | --- | --- | --- | --- |
| Motion response (STRONGEST, pre-snap) | `motion_response` | a defender chases the motion man across the formation (`follow`) | defenders bump/slide one gap over (`slide`), or nobody moves (`static`) | HIGH - flash-safe. In CFB 27 the AI reliably travels with motion in man. |
| CB post-snap relation | `cb_relation` | turns hips, back to QB, chases receiver downfield (`chase`) | sinks with cushion, squared up, eyes in backfield (`squat`), or bails to a landmark (`land`) | HIGH first 1.5s |
| Second-level reaction | `lb_pass_action` | LB/nickel turns and RUNS with a back or TE crossing (`run-with`) | LB drops straight back to a spot and hovers (`spot`), or blitzes (`blitz`) | MED |
| Crosser handling | `crosser_handoff` | one defender trails a crossing route wall-to-wall (`trail`) | crosser is passed between defenders (`pass-off`) | MED - only when a crosser exists (`none` otherwise) |
| Blitz math | `rushers` | 5+ rushers usually = man behind it (cover-0/1) | 3-4 rushers neutral | HIGH - count bodies crossing the LOS |

Derivation (in `assemble.py`, deterministic):
- `follow` motion or `trail` crosser or majority `chase` corners → **man**
- `slide`/`static` motion + `spot` LBs + `squat/land` corners → **zone**
- mixed chase/squat by side → **match or man-free** → flag for pro adjudication
- rushers ≥5 breaks ties toward man.

The pro respot then only adjudicates: family name, safeties_post, spot-drop vs match,
and any play the tell-vote flags as conflicted.

## Full v2 field schema

### Pre-snap (flash tier)
- `off_formation`, `off_personnel` (banner OCR still wins when present)
- `motion_type`: jet / orbit / short / across / shift / none
- `motion_response`: follow / slide / static / no-motion  ← man/zone tell #1
- `def_front`: even / odd / bear / okie / unknown; `box_count`: integer 5-9
- `def_shell_pre`: 2-high / 1-high / 0-high (validated 9/10)
- `cb_depth_pre`: press / off / mixed (validated 7-9/10)
- `nickel_present`: y/n (slot corner vs 3rd LB - personnel package read)

### Post-snap behaviors (flash tier)
- `play_type`: run / pass / pa-pass / rpo / screen / no-play
- `rushers`: integer count crossing the LOS
- `cb_relation`: chase / squat / land / mixed  ← tell #2
- `lb_pass_action`: run-with / spot / blitz / run-fit  ← tell #3
- `crosser_handoff`: trail / pass-off / none  ← tell #4
- `qb_drop`: 3-step / 5-step / rollout-L / rollout-R / boot
- `target_area`: short-L/M/R, mid-L/M/R, deep-L/M/R (9-zone grid)
- `run_direction`: L-edge / L-gap / middle / R-gap / R-edge (runs only)
- `pressure`: clean / hurried / hit / sacked (pocket outcome)

### Judgment (pro tier ONLY - flash writes nothing here)
- `def_safeties_post` (4/10 on flash x2 tests - hard-blocked)
- `def_zone_type` (spot-drop vs match), `def_coverage` family, `def_rotation` direction
- `disguise`: pre-snap shell ≠ post-snap structure beyond simple spin-down

### Derived in assemble.py (no model)
- `man_zone_verdict` + `mz_confidence` (count of agreeing tells) - from the tell stack
- `def_rotation` from shell_pre vs safeties_post (existing)
- result / yards / key_event stay transcript+HUD sourced (existing authority order)

## Sampling
- Charting clips: `fps: 2` in `videoMetadata` (default 1fps can miss jet motion & CB flip).
- Segmentation chunks: default fps fine (HUD state is static for seconds).
- Cost: video tokens ~2x per play; still ~7k tok/play - negligible.

## Report standard (v2, user directive 2026-07-29)

Game reports, rival dossiers, and recaps must exploit every v2 field — thorough and
in-depth, but every claim carries its denominator and source tier. Required sections:

**Game report** (`film-room/games/<slug>.md`):
1. **Game flow** — score progression by quarter, drive outcomes, game-script context
   (blowout/close — tendency data from garbage time gets flagged, not averaged in).
2. **Opponent defensive identity** — man/zone split (firm vs lean, per the confidence
   rule), shell distribution pre-snap AND rotation rate, box counts vs our personnel,
   pressure profile (rusher counts, blitz rate by down), corner technique by side,
   motion response (do they travel or bump? = man tell AND matchup-hunting guide).
3. **Opponent offensive identity** — formation/personnel frequency, motion rate + type,
   run direction distribution (edge vs interior, L/R bias), target-area heatmap
   (9-zone), QB drop profile, play-action and screen rates, tempo pattern.
4. **Situational** — 3rd-down conversions vs distance bucket, red-zone calls,
   2-minute behavior, 4th-down aggression.
5. **Special teams** — now charted (kind-tagged windows): return usage, FG range
   attempted, fake indicators. Excluded from offense/defense tendency splits.
6. **Exploits & counters** — specific, actionable: "their nickel travels with jet
   motion (man tell, 6/7) → motion to diagnose, then attack the vacated flat."
   Every exploit cites the plays (n=...) it's built on.
7. **Data quality block** — plays charted / windows / CHECK rows / provisional fields.

**Rival dossier** (`league/teams/<member>.md`): running multi-game aggregates of the
same splits with per-game sample sizes, trend arrows across meetings, and a "book"
section: 3-5 bullet game-plan directives with citations. Update, never overwrite —
old reads get superseded-by notes, not deletion.

**Recaps/self-scout**: same rigor on our own tendencies (what we showed = what
opponents will scout: our motion tells, our target bias by down, our run direction
lean behind which line side).

Claims ledger: no claim without (a) denominator ("8 of 11 third downs"), (b) source
tier (pro/flash-behavior/derived/HUD/transcript), (c) provisional tag where the pro
respot hasn't confirmed. Tendencies on <5 snaps are "flashes", never percentages.

## Validation ledger
- 2026-07-29: flash 3.6 @1fps coverage judgment 4/10 (rejected); @4fps guided 4/10
  (rejected - failure is judgment, not sampling); shell_pre 9/10, cb 7/10 (accepted).
- 2026-07-29 full-WVU validation (v2 flash tells vs 42 pro-truth plays):
  `man_zone_verdict` **32/33 (97%) on decided plays, 9 abstains**. Zone side is
  proven. Man side is NOT: the truth set held one man play (cover-1, off corners,
  no motion, no crosser) and the tells voted zone conf-2 on it - off-man is the
  known disguise the tell stack can't see without motion/crosser evidence.
- **Interpretation rule:** `mz_confidence >= 3` = firm; 1-2 = lean (report as
  "zone-lean", never as a count in a tendency split); pro family overrides the
  tell verdict whenever both exist. Expect the tell stack to under-call man
  against man-heavy opponents until a man-side validation sample exists.
