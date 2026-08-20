# Tier-2 prompt — verbatim transcription

Substitute `<WORKSPACE>`, `<BATCH>`, and the save identity line before dispatch. One agent per
batch, **~14 frames each**, batched in time order so one agent sees a whole scroll.

Dispatch every batch built from the `.keep` file. `dump_reconcile.py` gates on exactly that set.

---

Transcribe screen data VERBATIM from full-resolution frames of a College Football 27 screen-share.
This is the user's own dynasty save (`<DYNASTY>`, coach `<COACH>`, `<SEASON>` season, week `<WEEK>`).

## Steps
1. Read your batch list: `<WORKSPACE>/t2/<BATCH>.txt` (one filename per line).
2. Read EVERY image at `<WORKSPACE>/frames/<filename>` (full-res 1920x1080).
3. Write a markdown digest to `<WORKSPACE>/t2/<BATCH>.md`.
4. Reply with ONE line: `<BATCH>: <n> frames read, <what you captured>`.

`f_0720.jpg` is frame 720 = second 719 → timestamp `[11:59]`. Always cite the frame + timestamp
for each block.

## Absolute rules
- **Transcribe verbatim. Never infer, never compute, never fill a blank from another frame.**
- **"unknown" beats a guess.** A digit you cannot resolve (78-or-76) is `?`. Never coin-flip.
  A team logo you cannot name is `unknown`, never a plausible guess.
- Numbers matter more than prose. Get every digit right; re-read the frame if unsure.
- **Check the screen's own arithmetic and re-read anything that fails.** Quarter scores sum to
  Final (**including OT / 2OT columns — read the period headers, do not assume four**);
  Rushing + Passing = Total Offense; Total Yards = Total Offense + PR + KR; the two T.O.P
  values sum to 24:00; DIFF = PF − PA; TD% = TD/ATT; AVG = YARDS/attempts; FG% = FGM/FGA.
  A failed identity means **go back and re-read the cell** — never adjust a number to make the
  arithmetic work, and never compute a cell you could not read.
- **Use the printed column headers verbatim.** Where a table has none, do not invent a combined
  column: the standings card list is `OVERALL` and `CONF` (from `8-1 (4-1)`), never a single
  `W-L (CONF)`. Two captures that name columns differently cannot be compared week to week.
- **Do not supply the season or week from context.** Most screens do not state them — the
  full-column standings screen carries no year anywhere. Record what is printed; if nothing is,
  leave it out. The capture supplies the coordinate, not you.
- Many consecutive frames show the SAME screen with a different row highlighted or scrolled.
  **Merge them into ONE table** — union of all rows seen, no duplicate rows. If a scroll skipped
  rows (a gap in an obvious sequence), say so explicitly with the word `GAP`.
- **The table merges. The side panel does NOT.** The detail card tracks the cursor, so it shows
  a DIFFERENT player in every frame of a scroll. Emit one card block per frame, each headed by
  its own `f_NNNN`. Merging a run's rows with one arbitrary card writes one player's height,
  hometown, archetype and rating under another player's name, and nothing downstream can
  detect it because both halves are internally consistent.
- **Tables also scroll SIDEWAYS.** If a horizontal scrollbar sits under the table, name the
  first and last visible columns and write `H-SCROLL: columns beyond <LAST> not captured`.
  A merged run gives you complete rows and silently incomplete columns.
- If a frame is blurred/mid-transition, skip it and note `f_XXXX unreadable`. (Frames that
  failed `frame_quality.py` have already been removed from your batch — but say so if one
  slipped through. Do NOT transcribe a frame you cannot read: a previous pass produced a
  complete standings table from an illegible frame that was **52% correct**.)
- **`---` on screen means the game is showing NO VALUE.** Record it as `---`. It is not zero,
  not "no", and not unreadable — it was perfectly legible and simply empty.
- **Never count star glyphs.** Record the rating cell as an observation (`4 solid + 1 outline`)
  or just `stars: see stars_cv`. A filled star is solid and an unfilled one is a hollow
  outline that still carries ink, and every attempt to eyeball this over-counts by exactly
  one. `scripts/stars_cv.py` measures it correctly; you will not. The same applies to any
  colour-coded field — say "row rendered in red", not "injured".
- Do NOT summarise or editorialise. Output the data.
- **A side panel can lag the list.** When a highlighted row and its card disagree, the card may
  still be rendering the previously-selected player. Transcribe what you see and say the two
  disagree; do not silently drop either, and do not treat a lagging value as a placeholder.

## EVERYTHING ON THE SCREEN MEANS SOMETHING
Table bodies are the easy half. For every screen also record, when present:

- **Header/HUD chips** — record (W-L), week/year, coach name, LVL, Job Security, the two currency
  counters, and on Recruiting screens: Remaining / Targets / Hours / Scholarships.
- **Tab state** — which `L1`/`R1` tab and which sub-tab is selected, and any `L2` filter value.
  On a recruit card the sub-tabs read `Overview | Recruiting | Scouting (N%)` — **always record N**.
- **Icons and badges, described literally** — lock, "locked out", crossed-out handshake
  (dealbreaker), star (favorited), binoculars/magnifier (scouting), document (offer),
  green up-arrow / red down-arrow (trending), map-pin next to a hometown, coloured P-Tier pins
  **and the letter or number inside them**, person silhouette next to a school or opponent row,
  and any **green gem** in the icon stack under a player portrait.
  Say where the icon is and which row it belongs to. Do not interpret what it means.
- **Bars and meters** — the OPEN / TOP 5 / TOP 3 interest bar: say which markers are passed and
  roughly how far the fill reaches. Influence bars: colour and relative length per row.
- **Dividers inside tables** — "Projected Cutoff", "Locked Out" — and which rows fall under them.
- **Side panels** — Action Summary, Dealbreaker (Have/Need grades), next-opponent card.
- **Anything that would be a scouted reveal**: an OVR number, a gem indicator, revealed attribute
  ratings, a development trait. If you see one, transcribe it exactly. If the screen has none, say
  so — do not invent one, and do not report a "bust" marker from the mere absence of a gem.
- **Ad overlays / now-playing popups are NOT game data.** Note them only when they obscure a value.

## Output shape
For each distinct screen in your batch, emit:

```
### <SCREEN TITLE> — <context chips>  ·  frames f_0101–f_0118 [01:40–01:57]

<a markdown table with the EXACT column headers shown on screen, one row per data row>

Notes: <on-screen extras: highlighted row, totals, legends, icons, meters, GAP warnings>
```

Escape any literal `|` inside a cell as `\|`.

At the end of the file add:
```
## Coverage
frames read: N ; unreadable: <list or none> ; screens found: <list>
```
