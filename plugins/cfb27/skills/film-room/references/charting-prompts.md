# Charting prompts — how vision agents watch film

Claude **sonnet** vision agents are the primary charting lane (both input lanes; haiku confabulates scheme fields — SKILL.md step 6). This file is the prompt kit: read order, game-context template, superset-JSON schema, and the calibration-locked rules. Behavior-tell definitions and the deterministic man/zone derivation live in `references/extraction-framework.md`.

## Coach's read order (structure every agent's look this way)

Chart like a coach breaking down film — a fixed scan sequence, not a free-form description:

1. **Pre-snap (presnap.jpg):** personnel on the field → formation + strength → backfield set → alignment oddities (nub TE, bunch, reduced splits) → motion man and type → ball hash (`ball_hash`). Defense: front (count down linemen), box count, shell (safety count + depth), CB depth/leverage, nickel present. **v3 tell fields, all from this frame:** `cb_leverage_pre` (outside CB's shade vs the WR: inside / outside / head-up; per-side difference = `mixed`), `saf_depth_band` (deepest safety: <10 / 10-14 / 15+; two safeties in clearly different bands = `split`), and — trips sets only — `saf_nickel_trips_side` (safety AND nickel on the trips side = `both`; safety opposite the trips = `safety-opposite`; non-trips = `n/a`). These are alignment observations, not coverage conclusions — chart what you see, the derivation names families downstream.
1a. **Full-frame HUD (fullframe.jpg):** read the scorebug independently — `hud_dd` (down & distance as printed), `hud_poss` (which side's score box carries the possession bar: L or R), `hud_score`. Transcribe exactly what the HUD shows; if unreadable, `unknown`. Never reconcile with anything — disagreements with the machine HUD row are exactly what this field exists to surface.
1a2. **Play-art preview (playart.jpg, when provided):** this is an UNCROPPED pair from the pre-snap call-screen window. ONLY if a play-art overlay is actually visible: `off_playart` (short phrase from route stems / blocking arrows), `def_playart_zones` (verbatim zone colors/shapes, e.g. "2 deep dark-blue, 4 yellow hooks"), `def_playart_coverage` (family per the playart-key zone-color legend — allowed here and only here, because the art IS the call being displayed, not an inference). No overlay visible → omit all three keys entirely.
1b. **Pre-play adjustments (presnap_seq.jpg — 3×2 grid, each cell STAMPED with its offset, snap−12 → snap−0.5s; older film sends the unlabeled 2×2 preplay.jpg instead, snap−8/−5/−3/−1.2s):** find the first cell showing a full offensive set = `formation_initial`, and its shell = `def_shell_initial`. Compare against the snap alignment (`formation`). Different formation = `presnap_adjust: audible`; same personnel re-aligned = `shift`; only a motion man moved = `motion-only`; identical = `none`. Because the cells are timestamped, also chart the SEQUENCE: `adjust_seq` = ordered list of what changed and when, using the cell labels (e.g. `["-7.4s: TE trades across", "-2.8s: safety walks down, 1-high"]`); empty list when nothing moved. **Compare against the first NON-MENU cell** — a menu in the earliest cell never makes the comparison impossible; use the earliest cell that shows a set. **QB animation (`qb_presnap_anim`, this grid only):** arm-extended "come through" wave = `wave`; QB squat = `squat`; double toe-tap = `double-tap`; QB and a receiver touching helmets = `helmet-touch`; nothing seen = `none`. These are multi-second animations — a positive read is valuable, `none` is the normal case and is NOT a pass tell by itself. Early cells showing the play-call menu are normal (the call screen) — read them as menu intel, and mark `formation_initial: menu` if no set is visible in any early cell. Watch the defense across the same cells for its answer: `def_adjust` = `shell-shift` (safety structure changed), `front-shift` (line/LB alignment slid), `late-show` (pressure look appearing after the offense set), or `none`. Real-football interpretation of what an audible/check means lives in `references/football-iq.md` — consult it when writing scout-report narratives, not per-play.
1c. **Play-art re-checks (playart_check*.jpg, Lane B, when present):** the coach re-opened play art between lineup and snap — the art shows the ORIGINAL call. `playart_delta` = one line on how the final pre-snap look differs from that art (e.g. "art shows Trips Right; at snap RB flexed, now empty"); `none` when identical, `unknown` without a clear read. Play-art rules from step 5 still hold: art = options/assignments, never proof of the call made.
2. **Snap keys (ghost.jpg + strip tiles 1-3, +0.4 to +1.5s — the best coverage info; later tiles tighten onto the ball):** did the shell rotate (2-high → 1-high spin-down)? CB technique at the snap (press jam / off / bail)? Rusher count? LB first step (run-with / spot-drop / blitz / run-fit)? Motion response (follow = man tell, slide/static = zone tell)?
2b. **Front behavior (ghost trails on the DL):** trails crossing/exchanging = `dl_stunt_seen: twist`; the whole line sliding one way = `slant`; a rusher looping wide around a penetrator = `loop`; straight rushes = `none`. Record the BEHAVIOR only — never name a stunt (TEX/EXIT/...); the analyst names it later from menu tiles + the catalog.
3. **Play flow (full strip + ghost trails):** run/pass, concept, QB drop depth/direction, route distribution or blocking scheme, run direction, crosser handoff (trail vs pass-off). **Mesh behavior:** run fake then throw look = `pa_fake: yes`; mesh held while the QB stares at one defender = `rpo_look: yes` (either can be yes on a run that pulled). Screens: `screen_dir` = which side the screen released. **Busts:** a receiver running genuinely uncovered, or a defender clearly abandoning his zone = `def_bust: yes` — chart it even when you can't explain it; failure attribution happens downstream.
4. **Outcome cues (result.jpg):** pressure state only (clean/hurried/hit/sacked). **Never results/yards** — those come from transcript or HUD adjudication.
5. **Menus (Lane B menu crops):** transcribe, don't interpret — every legible tile verbatim.

## Calibration-locked rules (copy into every batch prompt)

- **Non-play requires that NO frame shows live football — check ghost.jpg and strip.jpg LAST-resort before voiding a window.** (Calibration 2026-07-31: this rule was over-firing and voided ~14 real snaps on one game alone.) A window is `non-play` ONLY when *every* provided image is a full-screen non-football screen. Work in this order:
  1. Scan **strip.jpg and ghost.jpg** for live football — 22 players in formation, a snap, ball movement, route/blocking action.
  2. If ANY frame shows live football, the window **IS a real play**. Chart it normally, even if other frames are menu screens. Note the obstruction in `note`.
  3. Only if NO frame shows live football → `play_type: "non-play"`, describe the screen in `note`, fill other fields `n/a`/`unknown`.
- **A menu OVERLAY on a live field is NOT a non-play.** CFB 27 draws the coach's own screens — `CUSTOM ADJUSTMENTS`, `AUDIBLES`, `SELECT DEFENDER`, coverage-adjustment panels — as a *panel on top of the live snap*, and the play runs behind it. Likewise the persistent bottom-bar HUD prompts (`PRE-PLAY`, `SUBS`, `DEFENSE AUTO-FLIPPED`) are always-on chrome, not a menu screen. If you can see the field and players through/around the panel, chart the play. Only a **full-screen** takeover (stats table, replay diagram, standings, postgame) with no field visible is a non-play.
- **Early preplay-grid cells showing the play-call screen are EXPECTED and never by themselves make a window non-play** — the grid starts 8s before the snap, when the call screen is legitimately up. Judge the window on the snap-and-after frames, not on the earliest cell.
- **Live-action fragments:** if presnap.jpg already shows the ball out / players mid-play AND no frame anywhere shows a pre-snap alignment or live snap, the window missed the snap — mark `non-play` with note "window missed snap"; never chart a run/pass from a play fragment.
- **Menu TITLES are UI labels, never the play call.** (Calibration 2026-07-31: this mislabelled multiple goal-line rushing TDs as passes.) A panel reading `PASS PROTECTION` is the protection-adjustment screen — it appears on RUN plays too, and the user opens it pre-snap regardless of the call. Same for `AUDIBLES`, `CUSTOM ADJUSTMENTS`, `SELECT RECEIVER`. **Never let on-screen menu text decide `play_type`.** Decide run vs pass ONLY from what the players do after the snap in ghost/strip: handoff mesh + carrier behind blockers = run; QB drop + receivers releasing = pass. Pre-snap red/orange arrows are blocking-assignment art and appear on runs.
- **Short-yardage and goal-line default to nothing.** `1&GOAL`, `3&INCHES`, `4&1` are exactly where run/pass is most often mis-called. Require the same positive evidence as anywhere else — a visible handoff mesh or interior surge means run, a QB drop and releasing routes means pass. If the ghost is a pile at the line with no clear drop, say `run` only on a visible mesh, otherwise `unknown` with `confidence: low`. Never default a goal-line snap to `pass`.
- **Play-call tiles are the options OFFERED, not the call MADE.** (Calibration 2026-08-05.) The call screen shows three choices; which one the coach picked is not visible. So `menu_tiles` may record them verbatim, but **never set `def_coverage`, `concept`, or `routes_or_blocking` from a menu tile** — those come from post-snap structure only. A window whose tiles read `COVER 3 BUZZ / TAMPA 2 / COVER 2 MAN` tells you nothing about the coverage that was actually run.
- **Chart ONLY from the images provided for that play** — never borrow imagery or menu content from an adjacent play or from memory. `menu_tiles` may come from dedicated menu crops OR from menus genuinely visible inside the play images (strips often catch the call screen); if no provided image shows menus, `menu_visible: false`, `menu_tiles: []`.
- **Emit key names verbatim from the schema** (`def_coverage`, not `coverage`; `def_shell_pre`, not `shell`). `fanout.py` matches keys exactly — a renamed key silently drops the column.
- **"unknown" beats a guess** — a confident wrong read is worse than a blank.
- **v3 tell fields are behaviors, never conclusions.** Chart the shade, the depth band, the animation, the crossing trails. Never emit a stunt name, a match-check name (Bingo/Box/Lock/...), or a coverage family from alignment alone — the ONE exception is `def_playart_coverage`, and only off a genuinely visible play-art overlay (the art is the call itself). `qb_presnap_anim` comes ONLY from the preplay grid; `none` is not a pass tell without motion context. `hud_*` fields are transcription of the fullframe scorebug, never reconciled with anything.
- **Schema authority: `references/chart-schema.md`** (machine twin `scripts/chart_schema.py`). On any conflict between this prompt and that file, that file wins.
- **run vs pass needs positive evidence** (ghost trails releasing downfield, QB drop, handoff mesh). Ghost is the primary play-flow source; without a clear ghost read, prefer the strip — and if neither is conclusive, keep `play_type` but drop `confidence` to `low` and say why.
- **No result guessing:** no yards, no complete/incomplete, no scoring claims.
- Post-snap judgment fields (`def_safeties_post`, `def_zone_type`, `def_coverage`) ONLY when ghost/strip clearly shows the deep structure at the top of the drop — else unknown. `def_safeties_post` is read at the top of the drop, NOT pre-snap.
- `formation_truth` from banner OCR is never contradicted.
- Menu/replay/timeout-only windows → `play_type: "non-play"`, note what the screen shows.
- Agents write JSON to their assigned `batches/json_outNN.json` and reply with ONE summary line.

## Game-context template (fill per game, prepend to every batch)

```
- CFB 27 <online H2H|vs CPU> game. <Lane A: my Twitch stream | Lane B: iPad recording of
  a COACH'S OWN SCREEN — not broadcast>. <Perspective/seam: first Ns = TEAM_X's screen
  (gamertag); after seam = TEAM_Y's screen. Each play's menu_screen_owner says whose
  menus are visible.>
- <TEAM_L> = scorebug LEFT, <jersey/trim colors>. <TEAM_R> = RIGHT, <colors>.
  Possession L = <TEAM_L> offense, R = <TEAM_R> offense.
- Final: <score + quarter line, from the postgame tail>. <Silent film: results come from
  the HUD lane — vision agents must NOT guess results.>
- On `--no-ghost` film there is NO ghost.jpg; the agent instead gets snap1..5.jpg —
  native-res full frames at snap +0.4/+0.9/+1.5/+2.1/+2.7s, to be stepped through as a
  flipbook and used everywhere this file says "ghost trails". Say so in the batch prompt,
  or the agent reports the ghost as missing evidence.
- Per play the agent receives: play_images (presnap_seq.jpg = 3x2 timestamp-labeled
  pre-snap grid snap−12→−0.5s — or on older film preplay.jpg, an unlabeled 2x2
  snap−8→−1.2s; presnap.jpg; ghost.jpg = min|max long-exposure pair, player paths as
  streaks; strip.jpg = 3x2 snap→+3.3s; result.jpg; fullframe.jpg = UNCROPPED
  snap−1.2s with scorebug — the hud_* source; playart.jpg = uncropped snap−8/−5
  pair — playart_* ONLY if an art overlay is visible), up to 3 menu_images (full-res
  lower-half crops from the gap BEFORE the snap; with --tiles each is two 960px
  native-res tiles _L/_R), and possibly playart_check images (the coach re-opened
  play art between lineup and snap — see read-order step 1c).
- <Paste the "Condensed table for batch prompts" from references/presnap-tells.md
  here (≤10 lines) — tells inform reads, never override observed behavior.>
```

## Superset-JSON schema (one object per play; emit EVERY key)

Use `"unknown"`/`"n/a"`/`"none"` rather than omitting — except `def_coverage`, omitted unless positively seen. `fanout.py` splits this into legacy blocks + chart_v2 rows; renaming a key silently drops the column.

```json
{"n": 12, "read": {
  "formation": "Gun Trips - variant or unknown", "personnel": "1RB 1TE 3WR or unknown",
  "motion": "yes|no|unknown", "play_type": "run|pass|non-play",
  "concept": "inside zone / four verts / screen / ... or none",
  "routes_or_blocking": "short phrase from ghost trails",
  "def_front": "4-2-5|3-3-5|4-3|unknown", "def_shell_pre": "2-high|1-high|0-high|unknown",
  "def_post_snap": "free-text man/zone impression", "def_safeties_post": "2|1|0|unknown",
  "def_cb_technique": "press|off|bail|mixed|unknown", "def_zone_type": "spot-drop|match|man|unknown",
  "def_coverage": "cover-0/1/2/2-man/3/3-match/4/6 ONLY if positively seen, else omit",
  "confidence": "high|medium|low", "note": "one line",
  "motion_type": "jet|orbit|short|across|shift|none",
  "motion_response": "follow|slide|static|no-motion",
  "box_count": "5-9|unknown", "cb_depth_pre": "press|off|mixed|unknown",
  "nickel_present": "true|false|unknown",
  "rushers": "int|n/a|unknown", "cb_relation": "chase|squat|land|mixed|unknown",
  "lb_pass_action": "run-with|spot|blitz|run-fit|unknown",
  "crosser_handoff": "trail|pass-off|none|unknown",
  "qb_drop": "3-step|5-step|rollout-L|rollout-R|boot|n/a|unknown",
  "target_area": "short-L/M/R|mid-L/M/R|deep-L/M/R|n/a|unknown",
  "run_direction": "L-edge|L-gap|middle|R-gap|R-edge|n/a|unknown",
  "pressure": "clean|hurried|hit|sacked|n/a|unknown",
  "cb_leverage_pre": "inside|outside|head-up|mixed|unknown",
  "saf_depth_band": "<10|10-14|15+|split|unknown",
  "saf_nickel_trips_side": "both|safety-opposite|n/a|unknown",
  "ball_hash": "left|middle|right|unknown",
  "qb_presnap_anim": "wave|squat|double-tap|helmet-touch|none|unknown",
  "pa_fake": "yes|no|n/a|unknown", "rpo_look": "yes|no|n/a|unknown",
  "dl_stunt_seen": "twist|slant|loop|none|unknown",
  "def_bust": "yes|no|unknown", "screen_dir": "L|R|middle|n/a|unknown",
  "hud_dd": "verbatim scorebug down&distance from fullframe.jpg, or unknown",
  "hud_poss": "L|R|unknown", "hud_score": "verbatim NN-NN or unknown",
  "off_playart": "OMIT unless playart overlay visible: concept from route stems",
  "def_playart_zones": "OMIT unless visible: verbatim zone colors/shapes",
  "def_playart_coverage": "OMIT unless visible: family per playart-key legend",
  "formation_initial": "first full set in presnap_seq/preplay grid, or menu|unknown",
  "def_shell_initial": "shell in that same first-set cell: 2-high|1-high|0-high|unknown",
  "presnap_adjust": "audible|shift|motion-only|none|unknown",
  "adjust_note": "one line: what changed, e.g. Gun Trips -> Gun Bunch, RB flexed",
  "adjust_seq": ["-7.4s: TE trades across", "-2.8s: safety walks down, 1-high"],
  "def_adjust": "shell-shift|front-shift|late-show|none|unknown",
  "playart_delta": "Lane B, only when playart_check images present: how the final look differs from the re-opened play art, or none|unknown",
  "postsnap_confirms": "yes|partial|no|unknown — does ghost/strip post-snap movement confirm the FINAL pre-snap read (e.g. shown 2-high that spins to 1-high post-snap = no)",
  "menu_visible": true, "menu_side": "offense|defense|both|none",
  "screen_call": "play name selected/likely-called if determinable, else unknown",
  "menu_tiles": ["4-3 OVER COVER 2 MAN | MAN | 0 CALLS | 0.0 AVG", "..."]
}}
```

### Coverage block — how to read the four fields

| Key | Values | How to read it |
| --- | --- | --- |
| `def_safeties_post` | `2`/`1`/`0`/`unknown` | Deep safeties **at the top of the drop, not pre-snap**. The single most important field — separates quarters/Cover 2 from Cover 3/Cover 1. Read off the ghost frame. |
| `def_cb_technique` | `press`/`off`/`bail`/`mixed`/`unknown` | `press` = jammed at LOS. `off` = 5+ yards and stays. `bail` = aligned press, turns and runs at the snap (Cover 3/quarters tell). `mixed` = differs by side. |
| `def_zone_type` | `spot-drop`/`match`/`man`/`unknown` | `spot-drop` = settle on landmarks. `match` = pick up and carry routes entering the area. `man` = travel with a receiver across the field. Can't tell match from spot-drop → `unknown`, don't default. |
| `def_coverage` | `cover-0/1/2/2-man/3/3-match/4/6` | Only when the family is positively seen — especially `cover-6` (needs field/boundary split; the derivation can't infer it). Otherwise omit; `assemble.py` derives from the three fields above. `def_rotation` is never charted — assemble computes it from `def_shell_pre` vs `def_safeties_post` (2-high shell + `1` post = spin-down). |

### Menu-intel instructions (Lane B)

Read every legible play tile on menu images: title (e.g. "COVER 3 SKY"), type tag (MAN/ZONE/BLITZ, or formation for offense), and the usage counters ("N CALLS | X.X AVG YDS"). Defense menus = coverage calls; offense menus = formation + concept names. Record the personnel/tab row (e.g. "PERSONNEL 4-3: Under/Tite Leo/Over...") and any starred/favorited plays. Transcription only — tendency math happens downstream where counters outrank behavior reads.

## Batching + provenance

- ≤12 plays per agent, batched by offense; each batch = manifest (`batchNN.txt`) + image paths; agent writes `json_outNN.json`.
- **Attach THREE keys to every batch:** `references/visual-passes/diagrams/diagram-key.jpg` (clean schematics: shell-first protocol, trips C3-vs-C1, motion test, Sky-vs-Match hips, C3 zones, Palms trigger) + `references/visual-passes/playart/playart-key.jpg` (the game's OWN play art with the zone-color legend — decode any menu/coach-cam zones by color: dark blue=deep quarters/halves/thirds, yellow=hooks, purple=curl flat, lavender=seam flat, teal=cloud flat, orange=QB spy, lone dot=man; bottom-left badge = MAN/ZONE/MATCH/BLITZ) + `references/visual-passes/frames/coverage-key.jpg` (the same looks in real CFB 27 footage). The proof chain is schematic → play art → game exemplar → the play images; a coverage call should be nameable at all layers. Keys are REFERENCE imagery for naming what you see — never chart content from them, and never let them override what the play imagery actually shows. Full sets for deeper comparison when a call is close: `visual-passes/diagrams/` (14 schematics, regenerate via `scripts/diagrams.py`), `visual-passes/frames/` (61 exemplars — consult `frames/INDEX.md` for what each shows and which visual-pass note explains it), `visual-passes/web-diagrams/` (34 coaching-site diagrams incl. fronts, run concepts, and pass concepts — see its MANIFEST.md for per-image content and naming quirks), and `visual-passes/playart/` (171 CFB 27 in-game defensive play-art images from cfblabs.com — one per named play; MANIFEST.md has the zone-color legend and inventory).
- **Prompt-cache prefix (cost rule):** build every charting agent's prompt with a
  byte-identical invariant prefix, in this fixed order: (1) the rubric text from this
  file, (2) the THREE key images, (3) the game-context template — and only THEN the
  per-play manifest + play images. Automatic prompt caching only hits on an unchanged
  prefix, so the ~10 batches per game each re-pay the rubric + 3 key images unless the
  ordering and bytes are identical across batches. Never interleave per-batch content
  (batch number, play list) before the keys; put anything batch-specific after them.
- Model: **sonnet** (calibration 2026-08-21 — haiku scored 42% on run/pass vs sonnet's 75% on
  identical frames, and filled 86% of scheme fields while agreeing with sonnet on almost none
  of them; see SKILL.md step 6). Respawn agents stalled >10 min. Transcription-only passes
  (menu tiles, HUD rescue sheets, Lane C) stay on haiku — it is judgement that fails, not reading.
- Provenance tag on merged columns: `v2_src=claude-sonnet-5-frames/<date>` (frames-tier provisional; older charts carry `claude-haiku-4.5-frames/<date>` and their scheme fields are lower-trust — see SKILL.md step 6). Gemini respot columns (`g_*`) get their own tag — never silently mix sources in one column.
