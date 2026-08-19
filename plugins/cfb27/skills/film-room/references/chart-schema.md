# Chart schema v3 — canonical field reference

Single source of truth for the play-chart schema. The machine twin is
`scripts/chart_schema.py` (imported by `validate_chart.py`, `merge_v2_local.py`,
`apply_recheck.py`) — **edit both together**. `references/charting-prompts.md`
carries the agent-facing prompt version of the same schema; on any conflict,
this file + `chart_schema.py` win.

Consumption contract: **CSVs are read by header name, never by position.**
`chart_schema.FINAL_COLUMNS` fixes the write order so every game lands the same
way; a chart missing a v3 column is a pre-v3 chart (`schema_version` column
absent or <3) and consumers must report those fields as `n/a (pre-v3)`, never
as zero.

## v2 → v3 changelog

Added (charted, vision): `cb_leverage_pre`, `saf_depth_band`,
`saf_nickel_trips_side`, `ball_hash`, `qb_presnap_anim`, `pa_fake`, `rpo_look`,
`dl_stunt_seen`, `def_bust`, `screen_dir`, `off_playart`, `def_playart_zones`,
`def_playart_coverage`, `hud_dd`, `hud_poss`, `hud_score` (all land as `v2_*`
columns — the prefix means "vision lane", versioning is the `schema_version`
column).
Added (derived): `schema_version`, `field_side`, `coverage_candidates`,
`play_style`, `def_coverage_src`, `def_rotation_lc`, `hud_conflict`.
Retired: `references/extraction-framework.md`'s divergent `play_type` enum
(`pa-pass`/`rpo`/`screen`) — `play_type` stays `run|pass|non-play`; the
pa/rpo/screen distinction now lives in `pa_fake`/`rpo_look`/`screen_dir` and
the derived `play_style`.
New keyframe artifacts (`frames.py`): `fullframe.jpg` (uncropped, snap−1.2s —
the HUD cross-check source) and `playart.jpg` (pre-snap play-art preview
overlay, only when detected).

## v3 charted fields (haiku vision — behaviors, never scheme conclusions)

| Field | Enum | Read from | What it captures |
| --- | --- | --- | --- |
| `cb_leverage_pre` | inside\|outside\|head-up\|mixed\|unknown | presnap.jpg | Outside-CB shade relative to the WR. Inside shade is the strongest static man tell; head-up squared (survives press) leans quarters/match; per-side difference = `mixed` (C6/C9 candidate). |
| `saf_depth_band` | <10\|10-14\|15+\|split\|unknown | presnap.jpg | Deepest safety's depth band. `split` = the two safeties sit in clearly different bands (stagger → split-field candidate). |
| `saf_nickel_trips_side` | both\|safety-opposite\|n/a\|unknown | presnap.jpg | Trips only: safety + nickel on the trips side (`both`, C1 lean) vs safety opposite (C3 lean). n/a for non-trips sets. |
| `ball_hash` | left\|middle\|right\|unknown | presnap.jpg / fullframe.jpg | Ball spot; feeds derived `field_side`. |
| `qb_presnap_anim` | wave\|squat\|double-tap\|helmet-touch\|none\|unknown | preplay.jpg grid | QB pre-snap animation (ZAN tells) or the helmet-touch hot-route tell. Multi-second animations; low fire rate is expected — a positive read is gold, `none` means "no animation seen", not "pass". |
| `pa_fake` | yes\|no\|n/a\|unknown | ghost/strip | Mesh/boot fake then throw look. n/a on runs/non-plays. |
| `rpo_look` | yes\|no\|n/a\|unknown | ghost/strip | Mesh held while QB reads a defender. |
| `dl_stunt_seen` | twist\|slant\|loop\|none\|unknown | ghost trails | DL trails crossing/looping — behavior only; the stunt NAME (TEX/EXIT/…) is analyst-tier (`defense-catalog.md` + menu tiles). |
| `def_bust` | yes\|no\|unknown | ghost/strip | A receiver running uncovered / a defender clearly abandoning his zone — blown-assignment flag feeding failure attribution. |
| `screen_dir` | L\|R\|middle\|n/a\|unknown | ghost/strip | Direction of a screen's release, when the play is a screen. |
| `off_playart` | free text | playart.jpg only | Offensive concept read from the previewed route stems/blocking arrows. |
| `def_playart_zones` | free text | playart.jpg only | Verbatim zone colors/shapes seen (e.g. "2 deep dark-blue, 4 yellow hooks"). |
| `def_playart_coverage` | coverage family | playart.jpg only | Family per the zone-color decoder (playart-key.jpg). The ONE pre-snap scheme name allowed — the art IS the call, not an inference. Omit when no preview overlay exists. |
| `hud_dd` / `hud_poss` / `hud_score` | text / L\|R\|unknown / text | fullframe.jpg | Vision's independent read of the scorebug: down&distance, possession side, score. Always-on second reader for the machine HUD lane. |

## Derived columns (never charted)

| Column | Derived by | Rule |
| --- | --- | --- |
| `schema_version` | merge_v2_local | "3". Absent = pre-v3 chart. |
| `def_coverage_src` | merge_v2_local | `playart` (def_playart_coverage present — outranks all) > `agent` (positively seen post-snap) > `derived` (COVERAGE_TABLE) > "". |
| `coverage_candidates` | merge_v2_local | When `def_coverage` is unknown: top-2 families from shell + leverage + depth-band + trips-side ("cover-3, cover-1 plausible"). Candidates are leans, never counted in tendency splits as calls. |
| `field_side` | merge_v2_local | From `ball_hash`: left hash → field = right, right → left, middle → balanced. |
| `play_style` | merge_v2_local | play_type refined: pass + pa_fake=yes → `pa-pass`; rpo_look=yes → `rpo`; concept/screen fields say screen → `screen`; else play_type. |
| `hud_conflict` | merge_v2_local | Non-empty when vision `hud_dd`/`hud_poss` disagrees with the machine `dd`/`poss` row — the deterministic value stays primary, the conflict is flagged for the possession-rescue/adjudication lanes. |
| `def_rotation` | assemble | shell_pre vs safeties_post (unchanged rule, normalisation widened). |
| `def_rotation_lc` | assemble | Low-confidence fallback: regex over `def_post_snap` free text ("spin", "rotat", "single high") when `def_rotation` is unknown. Never merged into `def_rotation`. |
| `man_zone_verdict` / `mz_confidence` | assemble (via merge) | Tell-stack vote; v3 adds `cb_leverage_pre=inside` as a weak (+1) man tell. Man side still unvalidated — see extraction-framework.md. |

## Enum hygiene

`chart_schema.NORMALISE` fixes known drift (`False`→`false`,
`def_zone_type: zone`→`unknown` — ambiguous, never guessed into spot-drop).
`validate_chart.py` reports every off-schema value per field; `apply_recheck.py`
applies the normalisation map. Anything not covered by the map is flagged for
recheck, never silently rewritten.
