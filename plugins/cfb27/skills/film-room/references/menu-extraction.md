# Lane C — what menu extraction actually gets wrong

Measured, not assumed. Every rule below comes from a spike that hand-labeled 17
real menu screens (1,130 cells) from the 2027 W9 and W10 dumps and scored three
model tiers and three prompt versions against them. Numbers in parentheses are
what was observed, so a future reader can tell a measurement from an opinion.

Headline: at the current prompt, a Sonnet-class model reads **97.4%** of cells
correctly on clean frames. The failures are not random — they cluster into six
specific, fixable classes, and four of them are silent.

---

## 1. Run the frame-quality gate BEFORE any model sees a frame

`scripts/frame_quality.py FRAMES_DIR OUT.json` — variance of the Laplacian over
the table band. Frames below threshold are excluded from transcription.

**Why it cannot be skipped:** a vision model does not refuse an illegible
frame. Handed a motion-blurred standings screen, it returned a complete 9-row
table, an empty "unreadable" list, and a note saying values were "transcribed
with moderate confidence". Against the same screen captured sharp, **52% of
those cells were correct** — a coin flip, delivered with no distress signal.

The tier-1 `readable` flag does not catch this. On that exact frame it recorded
`"readable": true, "visible_rows": 9`. A model cannot be the judge of whether
it can read something.

About **10% of distinct screen runs have no usable frame at all**. Excluding
them up front is the difference between a gap you can see and a table of
invented numbers.

`scores_schedule` is the worst family (4 of 12 sampled runs unusable) because it
gets paged through fast.

## 2. Screens scroll in BOTH directions

Vertical scroll is already handled — merge a run of frames into one table.

**Horizontal scroll is not.** The Player Stats tables carry a horizontal
scrollbar under the table; `KICKING` shows ten columns ending at `FGM29` with
more off-screen to the right. A run merged by row gives complete *rows* and
silently incomplete *columns* — the worst failure mode for a stats screen,
because the output looks well-formed.

- Note the scrollbar whenever it appears, and say which columns are the last
  visible ones.
- When capturing, page the full **width** of wide tables, not just the height.

## 3. Side panels are per-frame state — never merge them into the run

On an 8-frame recruiting run the model merged 29 prospect rows correctly and
then attached the **detail card from the last frame** while the rows start at
the first. Neither is wrong: the card tracks the cursor, so it shows a different
player in every frame.

The merged record therefore has no defined answer, and the result is one
recruit's height, hometown, archetype and star rating written under a different
recruit's name — invisible to every consistency check, because both halves are
internally consistent.

**Rule: the table merges across the run. The side panel does not.** Emit one
detail block per frame, each cited to its own `f_NNNN`. An 8-frame run yields
one table plus eight cards, which is strictly more data than one card.

## 4. Do not count stars — measure them

`scripts/stars_cv.py FRAME.jpg` counts filled star glyphs by ink density per
glyph cell.

Hand-checked against six recruits: the script got **6/6**. The model got 3/6,
and after a prompt fix that explicitly explained solid-versus-outline glyphs it
got **2/6 — the instruction made it worse.**

Every model error is an over-count by exactly one, and the cause is mechanical:
an unfilled star is a hollow outline that still carries ink, so anything that
reasons about "how far the stars extend" counts it. Filled glyphs measure ~440
ink units against an outline's ~70 — a 5.5× gap that is trivial to measure and
apparently impossible to eyeball.

Treat every glyph- or colour-encoded field the same way: star ratings, the
depth chart's red injured rows, green/red progression arrows, P-Tier pins.
Transcribe them as *observations* ("row is rendered red"), never as decoded
values, and let a script decode.

## 5. Numbers on the same screen check each other — use it

The strongest positive result in the spike: **every numeric error found was
catchable by an arithmetic identity already printed on the screen.**

| screen | identity |
|---|---|
| box score | quarter scores sum to Final (**including OT columns**) |
| box score | Rushing Yards + Passing Yards = Total Offense |
| box score | Total Yards = Total Offense + PR Yards + KR Yards |
| box score | the two T.O.P values sum to 24:00 |
| standings | DIFF = PF − PA; MOV × games ≈ DIFF |
| team stats | TD% = TD/ATT; DEFTD% = DTD/DATT |
| player stats | AVG = YARDS/attempts; FG% = FGM/FGA; XP% = XPM/XPA |

Run these after transcription and before merging to the vault. In the spike
they caught a wrong Total Offense (481 for 491), two wrong PF values, a wrong
PA, and — worth saying — **one error in the human's own hand label**.

An identity that fails is a re-read instruction, not a repair instruction.
Never "fix" a cell to satisfy the arithmetic; go back to the frame.

## 6. A screen category is not a schema

The tier-1 categories are too coarse to drive transcription. Measured:

- **12 of 20 frames classified `recruiting_board` were not recruiting boards.**
  Ten were the **My School** tab (playing style, school letter grades, Players
  At Risk, national Top Schools) and one was Coach Abilities outright.
- `standings` is two different screens: the full-column table (CONF, CPF, CPA,
  W-L, PCT, PF, PA, DIFF, MOV, HOME) and a compact rank/record card list from
  the CFB tab with only overall and conference records.
- `team_stats` is two: a team leaderboard, and the **Player Stats** tab whose
  rows are players, not teams.
- Coach ability trees vary in size (8 icons on TALENT DEVELOPER, 16 on ELITE
  RECRUITER).

So always record the **layout variant** — screen title plus tab and chip state —
alongside the category, and let the variant decide what shape to transcribe.
When a screen does not match the shape you were expecting, say so and emit no
rows. The model is reliable at this: handed a recruiting schema and a My School
screen it correctly returned nothing and explained why.

## 7. Column names must be stable across captures

On the header-less standings card list, one run emitted a single
`"W-L (CONF)": "8-1 (4-1)"` column where the hand label had `OVERALL: 8-1` and
`CONF: 4-1`. Both readings are faithful; neither is wrong.

Across two captures of the same screen that produces two different column
families, so nothing joins and nothing diffs week to week. In the spike this
also masqueraded as a 6.4% accuracy loss until it was separated out.

**Where a table has printed headers, use them verbatim.** Where it does not,
use the canonical names below and do not invent a combined column:

| layout | canonical columns |
|---|---|
| standings card list | `OVERALL`, `CONF` |
| Recruiting Board prospect list | `HOURS` (stopwatch icon), `NIL` (gem icon) — the board's numbers are NOT the table view's `OFFER` |

Team names have the same problem one level up: the same screen was read as
"UNC" and as "North Carolina". Pick the full school name as printed on the
screen's own header, and record it once per capture, not per screen.

## 8. Most screens cannot tell you which week they are

The full-column `CONFERENCE STANDINGS` screen carries a conference chip and
**no year anywhere**. Team stats and depth charts show a team and a category
but no week. In the spike the model correctly abstained on `season` and the
*hand label* was the thing that was wrong — it had inferred the year from the
capture.

Season and week are **capture-level context**, resolved once from a screen that
actually states them (the dynasty home screen and Scores/Schedules both show
`WEEK 10, 2027`) and applied to the whole capture. A capture containing no
week-bearing screen cannot be merged without asking the user.

## 9. Small things that cost real cells

- **`---` means the game is showing no value.** That is null/unknown — never
  zero, never false. It is perfectly legible, so it does not belong in an
  unreadable list either.
- **Overtime adds columns** to the box-score quarter line (OT, 2OT, …) between
  period 4 and Final. Read the column headers; if the periods do not sum to the
  final, a column was missed. This silently cost two quarter lines before it
  was caught.
- **Roster/depth-chart ratings are EFFECTIVE; player-card ratings are BASE.**
  The D. Green case (OVR 85 with a green up-arrow in the table row, 84 on his
  detail card, both verified at 6×) is NOT a disagreement — the up-arrow is a
  coach-ability **boost** indicator, not progression (user correction
  2026-08-21; dynasty-hq `dictionary/README.md` + schema-design §5.3). The
  table shows the boosted (*effective*) value, the card the true (*base*) one.
  Commit both under distinct keys (`ovr_effective` / `ovr_base` — never bare
  `ovr`), never reconcile, never flag as a conflict. Validator: arrow present
  ⇒ effective > base; arrow absent ⇒ equal; violation ⇒ re-read. A capture
  with no player-card screens is **effective-only coverage** — say so in its
  ledger rather than letting boosted values pass as true ratings.
- **In-game toast notifications** ("Charge On - UCF") overlay the bottom-right
  and can cover a table row. They pass the sharpness gate, so they need naming
  explicitly whenever they obscure a value.
- **Capture at 1080p or better.** Classical OCR reads the standings block at
  1100×618 and is unusable at 960×540, and the model's accuracy follows the
  same direction. Resolution is the cheapest quality lever available.

## 10. Model tier is not a free choice

Same 101 screens, same prompt:

| | Sonnet-class | Haiku-class |
|---|---:|---:|
| precision | **98.5%** | 76.5% |
| confidence 1.00 → actually correct | **97.8%** | 43.2% |

Haiku is ~2.9× cheaper and unusable for transcription. The decisive row is the
second: its self-reported confidence is **anti-informative** — its 0.90 bucket
scored better than its 1.00 bucket. Any workflow that routes low-confidence
output to review needs a model whose confidence means something.

Reasoning effort matters less than tier, and lower is the wrong trade here:
`low` was 20% cheaper and 40% faster but 1.9 points less precise, and a wrong
cell reaches the vault while a missing one goes to review.
