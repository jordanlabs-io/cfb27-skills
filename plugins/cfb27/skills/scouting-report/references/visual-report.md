# The visual report — multi-page, image-led, school-branded

**This is the default branded deliverable** — the standard a CFB 27 scouting
report ships in, on top of the markdown vault report. 6–8 Letter pages, real game
imagery, full call sheet, personnel, head-to-head history: the coaches' copy. The
worked example that set this format is UNC vs Vanderbilt, Week 11 2027, shipped
in `assets/` as two files:

- **`assets/visual-report-template.dc.html`** — start here. The document source:
  every page's markup, the shared chrome, and the explicit `grid-template-rows`
  declarations (`auto auto 277px`, `96px 1fr auto 322px`, …) that make the
  fixed-height pages behave. Asset ids for images and fonts do not resolve
  outside the bundle, so it reads as structure, not as a rendering.
- **`assets/visual-report-example-vanderbilt.html`** — the self-contained bundled
  export (3.5MB). Open it in a browser to see the finished document with real
  imagery and type. This is the visual target; the template is the starting point.

**When the brief instead.** `pdf-brief.md` is the compact alternate — the phone
read the night before: 2 fixed Letter pages, keys only, one chalk diagram, no
photos. Reach for it when the recipient asked for something short, when no charted
film exists to illustrate, or when the vault report has less ranked content than
these pages need. Building one does not require the other; both read the same
markdown vault report.

## Build order

1. **Read the school's brand assets first, before any layout.** Pull the real
   files — primary mark, secondary/tag mark, pattern tiles, ornament glyphs — and
   the official color and type specs. Do not approximate a logo, and do not
   substitute a lookalike typeface for a specified one. Copy the assets you need
   into the working folder; reference them relatively.
2. **Fix the chrome before the content.** Every page gets the identical frame, so
   the pages read as one document and content differences never move the
   furniture. The UNC build: 22px argyle band top *and* bottom, a 76px header
   band (large accent-color page number, section title in condensed display caps,
   one-line subtitle, primary mark right-aligned), a footer line pairing a
   "what we still don't know" note with `NN / NN` pagination.
3. **Set the type system.** Three faces, one job each: a condensed display face
   for all-caps headers and stat figures, a **serif** for body copy (editorial
   weight — a humanist sans reads like a web page, not a book), a mono for
   labels, tells, and stat values. Label rows run 8px mono, uppercase,
   0.15–0.19em tracking, grey.
4. **Set the palette and stop.** Primary, accent, one mid tone between them,
   paper, one warm tint for callouts, one rule color, one brick red reserved for
   `NEVER` / hot items, one grey for labels. UNC: `#13294B` `#4B9CD3` `#2C5080`
   `#F2EFE6` `#EAE5D8` `#DCD6C6` `#8C2F1F` `#5B6670`. Nothing else gets invented.
5. **Place the imagery.** Renders from the film-action-shot skill, one per major
   page, each captioned with a mono chip in the corner naming the play. See
   *Imagery* below.
6. **Fill from the vault report, page by page**, then run the layout pass below.

## Page inventory (7-page UNC build)

| # | Page | Carries |
| --- | --- | --- |
| 01 | Cover | Hero render, opponent name at 76px, coach + rank, the one-paragraph thesis, season form strip (one cell per game, W/L colored) |
| 02 | Who he is | Identity, signature calls, coach-card profile, pre-snap and dead-read tells |
| 03 | The precedent | The game that exposed him — full drive/box detail, what it proves about his off-script self |
| 04 | Personnel | Danger men with a render of the primary one, pass/run rate split as a proportional bar chart |
| 05 | Stopping him | The full situation → call → why table, hard-rule callouts, the one weak down split by film |
| 06 | Head to head | Prior meetings, front/technique counts, what he saw from you last time |
| 07 | Manage the game | Script thesis, ball security, timeout and 4th-down posture, the unknowns line |

Adapt the middle pages to the matchup; keep 01, 05, and 07.

## Imagery

- One render per content page maximum. A page with no render must be dense enough
  to justify it (the call-sheet page is).
- **Size the container to the render's real aspect ratio.** `object-fit: contain`
  letterboxes and `cover` crops off the thing you generated the image for — both
  are failures. Compute the box from the file's actual dimensions and let the
  image fill it edge to edge, bleeding to the page margin.
- Caption every render: mono, 8px, uppercase, on a primary-color chip in the
  bottom-left corner, naming the actual play ("QB #15 Maiden — designed keep,
  A-gap"). A render without a caption reads as decoration.
- Expose a single `showPhotos` boolean so the document can print text-only for a
  staff that wants the call sheet without the pictures.

## The layout pass (where the time actually goes)

Fixed-height pages fail silently. Every page in the UNC build needed this, and
the same four bugs recurred:

1. **`align-content: space-between` is the enemy.** On a fixed-height grid page
   it distributes *all* leftover space into the row gaps — measured 54px to 301px
   of phantom gutter against a declared 12px on four different pages. Removing it
   from four pages freed ~690px. Never use it on a paginated page. Instead
   declare explicit `grid-template-rows` and give exactly one track `1fr` so the
   slack lands somewhere you chose.
2. **Measure the gaps; do not eyeball them.** Read the rendered rects of adjacent
   children and compare the deltas against the declared `gap`. A page that looks
   "a bit airy" is usually 200px of accidental gutter.
3. **Freed space gets filled with content, not stretched.** After the fix, go back
   to the vault report for what was cut for space — the coach-card profile, the
   precedent game's specifics, the by-film split of the money down, the
   front/technique counts. Whitespace you did not choose is a bug; whitespace you
   chose is design.
4. **`min-height: 0` on every grid and flex child**, or tables and long copy
   refuse to shrink and blow the page height.

Other fixes from the same pass:

- When a stats row has vertical room, a proportional bar chart beats four numbers
  in boxes. When it does not, keep the numbers.
- Tables carry a `1fr` row so the rows breathe into leftover height rather than
  leaving a gap under the last one.
- Callout boxes get a full border plus a 4px left border in brick (hot) or accent
  (note). Two per row, `justify-content: center` so short and long copy align.

## Reviewing with the coach

Expect content cuts, not layout notes. The recurring one: intel that is real but
not actionable *this week* (injury status that has since cleared, a special-teams
fake never seen on film). Cut it and reflow the page — remove the row from
`grid-template-rows` too, or the gap stays behind. When the user says something is
"blocking the info above and behind it", they mean the page is overfull, not that
the z-order is wrong.

## Delivery

The document is already print-geometry-correct via the paged-document shell, so
PDF export needs no extra print CSS. Save the PDF next to the vault report, and
look at every page in the rendered PDF before sending — the same clipping rules
from `pdf-brief.md` apply, across more pages.
