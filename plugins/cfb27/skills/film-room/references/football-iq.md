# Football IQ — real-football field guide for film sessions

Distilled from Christian Sam (former NFL LB, Patriots/SB LIII) and Kurt Benkert (former NFL QB) — the vault's real-football education layer. **Authority rule (user directive 2026-07-30):** for interpreting film — naming coverages, reading leverage, explaining audibles — this guide and its `wiki/football-iq/` sources outrank game-creator content. Game creators stay authoritative for mechanics/menus/metas. Full teaching + citations: `wiki/football-iq/_index.md`. Provenance: claims marked *(Madden)* are from Madden-context teaching — the football transfers, the mechanics may not.

## The read protocol (order matters)

1. **Shell first — "safeties can cheat but they can't lie."** One-high vs two-high decides the whole tree. Two-high ≈ zone families (2/4/6); man from two-high is rare.
2. **Confirm post-snap at the top of the drop** — rotation (2→1 spin-down = C1/C3 rotation; safeties hold = 2/4/6), then CB technique, then underneath behavior.
3. **Then name the family.** Never from one frame; the pre-snap picture is allowed to lie (Mabel, invert C2), the post-snap structure isn't.

## Man vs zone diagnostics (highest-value tells)

- **Trips self-reveals — no motion needed:** nickel AND safety on the trips side = Cover 3 (landmark rule); safety opposite the nickel, over the backside #1/TE = Cover 1. Verified visually in CFB27 film.
- **Doubles/2x2 is pre-snap ambiguous → motion is the test:** motion man's defender travels = man; defender passes him off, safety stays high, nickel re-sets to new strength = zone. (This is why the pipeline's `motion_response` field exists.)
- **Hips and eyes:** zone defenders squat on landmarks, eyes on QB (Sky); match defenders open hips and run stride-for-stride when their man threatens vertical — the single clearest Sky-vs-Match visual tell.
- **Trail technique** (pressed corner riding the hip, letting the receiver stack him) = Cover 2 man. *(Madden)*
- **Match principle:** "a body with a body at all times" — someone running free means a blown assignment, not a scheme read. And: **"it's not where they line up, it's where they wind up"** — count receivers by where routes take them, not alignment.

## Coverage family cheat sheet

| Family | Pre-snap | Post-snap confirmation | Soft spots |
| --- | --- | --- | --- |
| Cover 0 | no deep safety; "stick figures" in no-man's-land pre-snap | everyone locked, all-out pressure | hots, quick game; motion deepens blitz launch points *(Madden)* |
| Cover 1 | 1-high; man leverage; in trips: safety opposite the nickel | corners chase; safety free or robber; blitz looks = inside leverage, hole/plug looks = outside | crossers, picks, wheel on matched RB |
| Cover 2 | 2-high deep + wide (outside hashes), corners near LOS | corners squat flats, safeties halves | deep middle (turkey hole), hole shots outside |
| Cover 3 base/Sky | 1-high; corners bail/off | 3 deep, 4 under spot-drop, eyes on QB | seams, flats, quick outs |
| Cover 3 Match | same as Sky pre-snap | under-defenders carry verticals (hips turn) | dependent on exchanges; beat with route conversions |
| C3 Mabel | looks like Cover 1 to the boundary (SS down over #3) | still zone — the "buzzer" LB sits MOF instead of matching a man | ID by the free-roaming buzzer |
| C3 Buzz | 2-high-ish show | weak LB buzzes flat, safety rotates down as hook | seam behind the buzzing LB |
| C3 Cloud | hybrid look | Cover 2 to the cloud side (corner flat), C3 rules other side | side-dependent; find the C2 side flat-corner |
| Cover 4 Quarters | 2-high at 10-12yd flat-footed reading #2; corners ~5yd off | 4 deep quarters; Mike = "3-rec hook"; safeties have RUN GAPS | **not a prevent** — best 1-on-1 go-ball look outside; play-action stresses run-fitting safeties |
| Cover 4 Palms (2-Read) | **identical to Quarters — NO pre-snap tell exists** (frame-verified in CFB 27); never call Palms pre-snap | corner reads #2: flat release by #2 → corner squats down, backside safety takes the vertical, THAT SIDE converts to Cover 2; no trigger → plays out Quarters. 3x1 = "special": backside safety cues #3, takes over crossers | asymmetric — attack the side that stayed Quarters; an over-squatting Palms corner gets beaten deep on the double-move/vertical behind him (frame-verified) |
| Cover 6 | split-field: quarters to field, C2 to boundary (or inverse) | different rules per side | needs the field/boundary split read — never infer, only call when seen |

## CFB 27-specific coverage machinery (visually verified)

- **Coach Adjustments → Cover 4 tab** carries per-formation Quarters checks: Stack / Bunch / Trips, each settable to Default / **Box** / **Bingo**. Bingo = outside CB locks #1 man if he stays outside, falls back to Box rules if #1 crosses in. A pressed corner in an otherwise-quarters shell may be a Bingo check, not man — check the menu-intel lane before calling Cover 1.
- The in-game coach-cam draws zone landmarks (DEEP ZONE / HOOK/CURL / CURL/FLAT / SEAM FLAT / 3 REC HOOK bubbles) — when opponent film shows this overlay, the labels are ground truth for their coverage's intended structure. "Cover 4 Palms" appears by name in play-call menus — a menu-intel tile beats any behavior read.
- **Zone-color decoder for the game's play art / coach cam** (full art: `visual-passes/playart/`, key: `playart-key.jpg`): dark blue = deep quarters/halves/thirds; yellow-olive = hook curl / 3 rec hook / mid read; teal = cloud flat; translucent baby blue = hard flat; opaque baby blue = soft squat; royal purple = curl flat; lavender = seam flat; orange circle = QB spy; a lone dot with no zone = man-to-man. Every play-art image also carries the game's own MAN/ZONE/MATCH/BLITZ badge (bottom-left) — verbatim classification. **No "Cover 0" play exists in CFB 27** — all-out man pressure is named ZERO BLITZ etc.; read "0" in a tile as a blitz name.
- Madden UI (vision-bubble variants, Reinforcement ability cards) looks similar but is NOT CFB 27 — `benkert-madden-reads-visual.md` documents the differences; never import Madden UI specifics into CFB 27 claims.
- Time-sensitive: charted "match" busts (carriers releasing verticals) appear in this game generation — treat single blown-coverage reps as possible game bugs, not scheme identity.

## Cross-check: NFL Next Gen Stats coverage model (AWS ML blog, tracking-data)

The NFL's own 8-class coverage classifier (player tracking, ensemble model) independently validates this framework and sharpens a few rules:

- **Man-vs-zone FIRST, family second** — their binary hit 95.4% while 8-way managed 88.9%; the binary is the reliable call. Matches our tell-vote-then-family order; report `man_zone_verdict` confidence separately from family confidence.
- **Cover 1 vs Cover 3 is THE confusion pair** — their embeddings overlap even with tracking data. On any 1-high shell, weight CB technique (trail/chase = C1, bail/land = C3) and LB pass action (run-with = man, spot = zone) heaviest — those visually-read tells are precisely the features their position-only model lacked.
- **Top-2 honesty**: their top-2 accuracy was 97.6% — real coverages often have a legitimate second-best answer. A split vote on a 1-high shell should output "C3, C1 plausible" with confidence, never a forced single call.
- **Measure relative, not absolute**: CB depth relative to the WR, safety width relative to hash/numbers — relative geometry survives camera variance.
- **Second look at ball-release**: rotation/match disguises declare late; when the +1.5s read is ambiguous, check the latest strip tiles before settling.
- **Cover 6/rotations stay hard even for the NFL's model** — reinforces the standing rule: call C6 only when the field/boundary split is positively seen.
- **Motion response is our edge** — NGS doesn't decompose it as a feature; the motion test stays our highest-value man/zone discriminator.
- **Prevent** is a situational class: gate it on down/distance/clock context, not shell geometry alone.

## Leverage & field geometry (feeds `cb_leverage_pre`/`ball_hash`, v3)

- **Leverage is assignment leaked pre-snap:** a corner shades where his help ISN'T. Inside shade = funneling out = he expects to carry the receiver himself (man lean); outside shade = funneling into help = zone/C1-with-hole lean; squared head-up over the receiver = read technique (quarters/match lean). Principle is real football; the game-verified depth/shade numbers live in `references/presnap-tells.md` (mechanics authority) — and **coverage shells can fake all of it on human opponents**, so leverage informs, post-snap confirms.
- **Hash sets the field:** the ball on a hash creates a field (wide) side and a boundary (short) side. Defenses declare strength and rotate help to the field; the boundary corner lives alone. Read field/boundary BEFORE formation — space is the first constraint on both call sheets ("the side with the most space you cover first"). Feeds derived `field_side`; split-field calls (C6/C9) only make sense against this read.
- **Depth stagger between the two sides** (one corner low/squatted, the other deep/square) is the split-field giveaway — chart it as `cb_leverage_pre: mixed` / `saf_depth_band: split`, never as a family name.

## Pre-play & audible interpretation (feeds `presnap_adjust`/`def_adjust`)

- "**You don't audible for no reason**" — every check is set-up or answer. Formation audible after seeing the shell = attacking a structural weakness; log WHAT they checked into vs. which look.
- Offense re-aligning same personnel (shift) ≠ audible — shifts hunt leverage/strength; audibles change the play.
- Defense's answer is scoutable: shell-shift after offense sets = coverage check; front-shift/stunt = run-fit answer; late pressure show = disguise timing. A coach whose defense NEVER adjusts post-set is playing static calls — exploitable with any check system.
- Motion ≈ heavily pass-leaning in H2H play; opponent formations repeat — "every offense has tendencies… that is your job to pick up."

## Run-game recognition (feeds `concept`/`run_direction`/`routes_or_blocking`)

Read the offensive line's first steps in ghost/strip, not the back's path (backs cut; blockers commit):

- **Puller key (cleanest discriminator):** no puller + OL stepping playside in unison = **zone family** (inside vs outside by aim point: guard's inside leg vs tackle's outside hip); no puller + double-teams straight ahead = **Duo**; 1 puller wrapping upfield = **Power O**; 2 pullers = **Counter**; 1 puller flat down the line = **Trap**; backside TACKLE pulling = **Dart**.
- **Split zone** = zone flow one way + a TE/H crossing against the grain to kick the backside end. **Lead/Iso** = FB/H straight into the hole ahead of the back.
- **Stretch** stresses over-pursuit — the cutback crease appears behind the first cut-off block; defenders who "meet him where he's at" get cut back on.
- Visual anchors: run-blocking diagram frames in `visual-passes/frames/` (Of_TwCsCETs-*) + `faf-run-concepts-visual.md`; full rules in `wiki/football-iq/run-concepts.md`. Sub-variants without a distinct visual key (zone read, wham, jet zone…) are flagged in the visual pass — don't force those calls from one frame.

## Blitz & protection quick rules

- Blitz math: send more than they can block; blitz OPEN sets (TE detached), avoid closed sets (TE+RB max-pro).
- Scat back (releases immediately) frees no one; back stays to block → **green dog** (his defender adds to the rush).
- Elite LBs blitz; DBs as blitzers get swallowed. Every blitz needs coordinated secondary shade (inside leverage kills slants/drags).
- Protections: 5/6/7-man; full-slide leaves the opposite edge weak; half-slide leaves 1-on-1s; RB checks then releases (jet). Cover-0 answer: keep the back, motion a receiver to widen launch points, throw hot. *(Madden)*

## Scouting a QB's processing (dossier lens)

Benkert's sequence: shell ID → post-snap confirm → attack the family's soft spot → leverage-aware throw. Grade opposing QBs on film: do their eyes follow a progression or drop to the rush? Do they take the open first read or predetermine? Rushed feet = rushed arm (sacks/fumbles cluster behind it). The Maye/Darnold film reviews in `wiki/football-iq/reading-coverage-as-a-qb.md` are the reference template.

## Sources

Wiki: `wiki/football-iq/` (9 pages, full citations). Visual passes (frame-verified 2026-07-30): `references/visual-passes/sam-cover3-variations-visual.md`, `sam-lockdown-cover4-visual.md`, `sam-cover3-vs-man-visual.md`. Also: `sam-quarters-vs-palms-visual.md`, `benkert-every-coverage-cfb26-visual.md`, `benkert-madden-reads-visual.md`, `faf-*-visual.md`. **Visual layers** (all internal reference use only): `visual-passes/diagrams/` (our 14 schematics, `diagrams.py`), `visual-passes/frames/` (61 teaching-video exemplars + `coverage-key.jpg` — **`frames/INDEX.md` maps every frame to its timestamp, source video, and the visual-pass note that explains it**; never treat a frame as standalone), `visual-passes/web-diagrams/` (34 curated coaching-site diagrams + MANIFEST.md with source attribution and terminology mappings — e.g. "Rat"/"Plugger" hole-defender names, Palms="2-Read"), `visual-passes/playart/` (171 CFB 27 in-game defensive play-art images + `playart-key.jpg` zone-color legend — the game's own menu art). Proof chain for a coverage call: web/own diagram → in-game play art → game exemplar → the play film.
