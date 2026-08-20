# Tier-1 prompt — classify (do not transcribe)

Substitute `<WORKSPACE>` (e.g. `~/CFB27-film/<capture-slug>`) and `<NN>` before dispatch.
One agent per batch. Runs on the **downscaled** `tier1/` copies — this pass only needs to
know *which screen* each frame is, not what is on it.

---

You are classifying frames from a College Football 27 screen-share capture. Your ONLY job is
classification — do NOT transcribe table contents in this pass.

## Steps
1. Read your batch list at `<WORKSPACE>/cm/batch_<NN>.txt` (one filename per line).
2. Read EVERY image at `<WORKSPACE>/tier1/<filename>`. Do not skip any.
3. Write your results to `<WORKSPACE>/cm/out_<NN>.json`.

## Filename → time
`f_0720.jpg` is ffmpeg frame 720 = **second 719** (frame 1 = second 0). Emit `sec` and `ts`
anyway, but know that the merge step re-derives both from the filename and ignores yours —
this is the single most common arithmetic slip in this pass.

## Output — a JSON array, one object per frame, EVERY key present
```json
{"frame":"f_0720.jpg","sec":719,"ts":"11:59",
 "screen_title":"TEAM SCHEDULE",
 "screen_category":"schedule",
 "context_chips":"NORTH CAROLINA | RECEIVING",
 "has_table":true,
 "visible_rows":9,
 "readable":true,
 "notable":"wk1-9 slate with scores, 5-3 record, 5th in conference"}
```

- `screen_title` — the LARGE header text at top-left, VERBATIM (e.g. "TEAM STATS", "COACH STATS",
  "TEAM SCHEDULE", "ROSTER", "RECRUITING", "TRANSFER PORTAL", "COACHING STAFF", "FACILITIES",
  "TEAM RANKINGS", "STANDINGS", "SCHOOL INFO", "TROPHY CASE"). If none, use "".
- `screen_category` — ONE of exactly: `schedule`, `team_stats`, `player_card`, `roster`,
  `depth_chart`, `coach_stats`, `coaching_staff`, `standings`, `rankings`, `recruiting_board`,
  `recruit_card`, `transfer_portal`, `nil`, `facilities`, `records_awards`, `trophy_case`,
  `school_info`, `dynasty_home`, `scores_schedule_league`, `menu_nav`, `loading_transition`,
  `gameplay`, `my_school`, `other`.
  Use `other` ONLY if nothing fits, and then make `screen_title` + `notable` very descriptive.
  Inventing a category value fails validation — the merge step rejects the row.
- `context_chips` — the smaller filter/tab labels (team selector, stat category, conference
  filter, L1/L2/R1/R2 tabs), joined with " | ". "" if none.
- `readable` — false if the frame is mid-transition, blurred, or a fade. true otherwise.
  **Advisory only.** Legibility is decided by `frame_quality.py`, which runs before you and
  has already excluded unreadable frames. Do not treat a frame's presence in your batch as
  proof it is readable, and do not rely on your own judgement here — a previous pass marked
  a motion-blurred standings frame `readable: true, visible_rows: 9` and its numbers were
  illegible smears.
- `layout` — the layout VARIANT, which is what decides how the screen gets transcribed later:
  the screen title plus the tab and chip state that change its shape, e.g.
  `standings/full-table`, `standings/card-list`, `team_stats/team-leaderboard`,
  `team_stats/player-stats`, `recruiting/board`, `recruiting/nil-table`, `recruiting/my-school`.
  If you cannot tell which variant, say so in `notable` rather than guessing.
- `notable` — ONE short line naming what data is actually on screen. Be specific and concrete.

## Rules
- Classify ONLY from the image. Never guess from neighbouring frames.
- **A category is not a schema — the variant is.** These categories are broad, and the
  broadest are actively misleading: in a measured pass, **12 of 20 frames classified
  `recruiting_board` were not recruiting boards** — ten were the **My School** tab
  (playing style, school letter grades, Players At Risk, national Top Schools), which now
  has its own category `my_school`. Use it. Likewise `standings` covers both the
  full-column table and the compact rank/record card list, and `team_stats` covers both the
  team leaderboard and the per-player **Player Stats** tab. Always fill `layout`.
- If you cannot read the title, set `screen_title:""`, `readable:false`, and still emit the object.
- Emit one object per frame in your batch, in order. Do not merge or drop frames.
- Reply with ONE line only: `batch <NN>: <count> frames, categories: <cat>=<n>, ...`

Merge with `dump_chapters.py <WORKSPACE>/cm <WORKSPACE>/chapters.json`.
