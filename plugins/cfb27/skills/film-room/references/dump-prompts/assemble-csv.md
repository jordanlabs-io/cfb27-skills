# Assembly prompt — digests → CSV

Substitute `<WORKSPACE>`, `<VAULT>`, and `<SLUG>` before dispatch. One agent per game (or per
screen family). Runs **after** `dump_reconcile.py` passes — assembling from an incomplete digest
set produces CSVs that look finished and are not.

`races.csv` is NOT assembled here: its schema is owned by the `dynasty-tracker` skill.

---

Turn already-written verbatim digests into machine-readable CSV. **This is a reshaping job, not a
reading job: never invent, compute, or "clean up" a value.** If a digest says `?`, write `?`.
If a digest flags `GAP` or "not captured", leave the row out rather than filling it.

## Inputs
Your assignment names a game and a list of digest files. Digests live in two places — read
whichever of your assigned files exist:
- `<WORKSPACE>/t2/<BATCH>.md`
- `<VAULT>/dynasties/<DYNASTY>/film-room/captures/<capture-slug>/*.md`

## Outputs — write all three, even if a file ends up header-only

**1. `<WORKSPACE>/asm/<SLUG>-team.csv`** — box-score team lines.
```
week,opponent,team,stat,value,source_frame
4,Maryland,UNC,Total Offense,386,f_0558
4,Maryland,Terps,Total Offense,167,f_0558
```
`team` is your program's short label and the short label the screen itself uses for the opponent
(`Terps`, `Zona`, `NW`, `BAY`, `WVU`). One row per stat per side. Include the quarter-by-quarter
scores as stats `Q1`..`Q4` and `Final`. Copy `stat` labels verbatim from the screen
(`Rushes - Yards - TDs`, `3rd Down Conv.`, `T.O.P.`), and copy compound values whole
(`25-131-2`, `3-8 (37%)`).

**2. `<WORKSPACE>/asm/<SLUG>-players.csv`** — per-game player stats, **LONG format**.
```
week,opponent,team,category,player,stat,value,source_frame
4,Maryland,Terps,passing,M.Washington,yards,135,f_0575
```
Long, not wide, because each category has a different column set — a wide table would be mostly
empty cells. (Team stats go wide: that stat set is identical every game.)

`category` is lowercase from the screen's stat-category chip: `passing`, `rushing`, `receiving`,
`blocking`, `defense`, `kicking`, `punting`, `kick_return`, `punt_return`, `general`.
`stat` is the column header lowercased with spaces → `_` (`YARDS`→`yards`, `COMP%`→`comp_pct`,
`RAC AVG`→`rac_avg`). One row per (player, stat). **Skip players whose entire row is zeros** —
they are roster filler, not data. Keep a zero when the rest of that player's row is non-zero.

**3. `<WORKSPACE>/asm/<SLUG>-cards.csv`** — the side-panel player cards.
```
player,team,ovr,position,jersey,archetype,class,nil,height,weight_lb,hometown,hometown_pin,physical,mental,badges,source_frame
Nathan Leacock,UNC,78,WR,82,Speedster,SR (RS),10,"6'3""",219,"Rolesville, NC",true,Human Joystick,,"A;lips",f_0484
```
- `physical` / `mental`: semicolon-joined trait names, empty if the digest says empty.
- `badges`: semicolon-joined, describing each glyph as the digest describes it.
- `hometown_pin`: `true` only if the digest explicitly notes a map-pin/location icon; else `false`.
- One row per distinct player. If the same player's card appears in several frames with identical
  values, emit ONE row. If values differ between frames, **emit both rows** and add a final column
  note — do not pick one.

## Rules
- Quote any field containing a comma or quote, per normal CSV.
- Every row carries the `source_frame` the digest cites. If a digest merges a scroll, use the first
  frame of that merge. A row with no traceable frame is a row nobody can re-verify.
- If a digest block cannot be assigned to your game with certainty, **leave it out** and list it in
  your reply. Do not guess which game a stat screen belongs to.
- **Two proofs that disagree are both recorded.** If the box score and the player table give
  different numbers for the same thing, emit both and flag it. Do not average, pick, or reconcile.
- Validate: `python3 -c "import csv,sys;[list(csv.DictReader(open(f))) for f in sys.argv[1:]]" <your three files>`

Reply with ONE line: `<SLUG>: <n> team rows, <n> player rows, <n> cards; unassigned: <list or none>`
