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
| CB static leverage (v3, WEAK) | `cb_leverage_pre` | inside shade pre-snap (+1 man) | outside/head-up abstain | MED — **UNVALIDATED**; coverage shells fake it on human ranked opponents. Hand-verify 10 reads per film before trusting (see validation ledger). |

Derivation (in `assemble.py`, deterministic):
- `follow` motion or `trail` crosser or majority `chase` corners → **man**
- `slide`/`static` motion + `spot` LBs + `squat/land` corners → **zone**
- mixed chase/squat by side → **match or man-free** → flag for pro adjudication
- rushers ≥5 breaks ties toward man.

The pro respot then only adjudicates: family name, safeties_post, spot-drop vs match,
and any play the tell-vote flags as conflicted.

## Field schema — canonical source moved (v3, 2026-08-18)

**The schema now lives in `references/chart-schema.md`** (machine twin
`scripts/chart_schema.py`) — this section's old v2 listing carried enums the
pipeline never shipped (`play_type: pa-pass/rpo/screen`, `def_front:
even/odd/bear/okie`, a `disguise` field that never landed in any CSV) and is
retired. `play_type` stays `run|pass|non-play`; the pa/rpo/screen distinction is
now behavior fields (`pa_fake`/`rpo_look`/`screen_dir`) plus the derived
`play_style`. Tier routing survives unchanged: flash charts behaviors, pro
adjudicates judgment fields, assemble/merge derive abstractions
(`man_zone_verdict`, `def_rotation`, `coverage_candidates`, `field_side`,
`play_style`, `hud_conflict`).

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
7. **Series log & adjustments** (v3, from `series_book.py` + `series_book.csv`) —
   formation→play-family rep counts with 100%-pairing flags ("can't do it
   twice"), per-series defensive sequencing (sky-then-match style shifts),
   first-drive probe script vs rest-of-game, decoy-shift analysis (formation
   charted pre-snap vs post-shift — see defense-catalog.md), and the
   **failure-attribution narrative**: each momentum-swinging loss classified as
   scheme loss / missed tackle / engine bug (cite `def_bust` rows and the
   known-bug list in defense-catalog.md — a bug is NEVER a tendency). Close
   with a **patch-era line**: which patch window the film sits in and which
   tells/mechanics that dates (wiki patch notes).
8. **Data quality block** — plays charted / windows / CHECK rows / provisional
   fields / hud_conflict count / duplicate-window candidates from
   validate_chart. Coverage claims name their source tier via
   `def_coverage_src` (playart > agent > derived); `coverage_candidates` rows
   are leans and never enter tendency denominators.

**Rival dossier** (`league/teams/<member>.md`): running multi-game aggregates of the
same splits with per-game sample sizes, trend arrows across meetings, and a "book"
section: 3-5 bullet game-plan directives with citations. Update, never overwrite —
old reads get superseded-by notes, not deletion. v3 adds an **"Adjustment
habits"** subsection: does this coach adjust series-to-series (sequencing
evidence from series_book) or call static (exploitable with any check system)?
Each film entry carries a `patch_era:` note so tendencies can be discounted
when a patch invalidates the mechanics they rode on.

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
- **v3 standing tasks (2026-08-18, all open until measured):**
  (a) man-side validation — still needs a man-heavy film with hand truth;
  (b) `cb_leverage_pre` — hand-verify 10 reads on the first v3-charted film
  before the +1 man weight is trusted; (c) `qb_presnap_anim` fire rate — if
  ≈0 across a full game, raise the preplay-grid densification option
  (extra −2.5s cell in frames.py) with the user; (d) `def_playart_coverage` —
  spot-check 5 play-art reads against the playart-key on the first film that
  produces any; (e) re-measure `presnap_adjust` and `def_rotation` fill rates
  vs the 2026-08-18 audit baseline (presnap_adjust 6-18% non-none,
  def_rotation ~0%) after the first v3 chart.
