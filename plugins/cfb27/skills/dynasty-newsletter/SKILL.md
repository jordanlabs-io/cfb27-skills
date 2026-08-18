---
name: dynasty-newsletter
description: Produce an issue of a dynasty's newsletter — a branded, iMessage-ready PDF recapping or featuring a CFB 27 dynasty game (the flagship example is Tarstool Sports, the student-voice paper covering the UNC/Weef dynasty). Runs the full editorial pipeline - pull game truth from the film-room files, fill vault gaps by asking the user, write in the publication's voice, generate photoreal action shots via the film-action-shot skill, lay out in the publication's design system, render to PDF, and fact-check every number before delivery. Use when the user says "newsletter", "Tarstool issue", "write up the game", "issue N", or wants any recap/feature of a dynasty game packaged as a document.
---

# Dynasty newsletter — issue production

One issue = profile → facts → story → images → layout → verify → deliver. Work the
phases in order.

## 0. Resolve the publication profile

Every dynasty can run its own paper with its own voice and brand. Resolve, in order:

1. **`dynasties/<dynasty>/newsletter/profile.md`** in the vault — the publication's
   own profile: name/masthead, voice reference, universe bible (nicknames, venues,
   running jokes, continuity threads), brand sources (colors, fonts, logo assets,
   layout example), delivery preferences.
2. **Bundled default: Tarstool Sports** (UNC / the Weef). Voice + universe bible:
   `references/tarstool-voice.md`. Worked layout: `assets/issue-01-example.html`
   (Issue 1, "WE'RE BACK.", UNC 37-14 at #4 Maryland). Clean NC mark:
   `assets/nc_mark.png`.

Starting a paper for a dynasty that has no profile? Offer to create
`newsletter/profile.md` from the Tarstool one as a template — capture the voice in
the profile, not in ad-hoc conversation memory, so issues stay consistent.

## 1. Facts first — the film room is ground truth

- Primary source: `dynasties/<dynasty>/film-room/games/<season>-<matchup>.md`
  (game flow table, turnover ledger, tendencies, data-quality caveats). The plays
  CSV sits next to it for drive-level detail and commentary quotes.
- Context: `seasons/<year>.md`, `league/h2h.md`, `league/teams/<opponent>.md`, and
  any podcast transcript for callbacks.
- **The vault lags the dynasty.** Uncaptured weeks are normal. Ask the user to fill
  gaps rather than guessing — and when their account conflicts with a scorebug or
  season file, surface the discrepancy and let them adjudicate before print.
- Names come from rosters, not commentary phonetics (commentary "O'Neal" = roster
  Miles O'Neill). Check jersey numbers against film frames or the user.
- **No invented stats.** Every number must trace to a film file, a season file, or
  the user. Color/dramatization only where it can't be mistaken for a stat; name
  any such line to the user at delivery.

## 2. Story — voice and continuity

Read the resolved voice reference before drafting. Structure that works: cold open
on the emotional stake → the wound/backstory → how both sides arrived → the game
in movements (not a drive log) → a unit that deserves its own section → "what it
means" → a kicker that answers a running thread. Each issue plants or pays off at
least one continuity thread from the universe bible.

## 3. Images

Invoke the **film-action-shot** skill: 2-3 action renders from the game's decisive
moments (hero shot = the play the theme hangs on) plus, for a Player of the Week
box, an editorial portrait with likeness from the in-game player card. Compress
finals to JPEG quality ~87, max ~2200px wide, before layout.

## 4. Layout — the publication's design system, applied

Use the brand sources from the profile (Tarstool default: Carolina Blue `#4B9CD3`
leads ~40%, navy `#13294B` ~15%, argyle as ONE edge accent only, Oswald all-caps
display / Open Sans meta / Source Serif 4 prose, diamond section markers,
interlocking NC undistorted). Reuse the profile's layout example — masthead,
issuebar, hero, scoreboard + quarter line, two-column serif body with drop cap,
section headers, pull quotes, figure cards, statbar, Player of the Week box,
hairline footer. New issues change content and imagery, not the system; one new
layout move per issue max.

## 5. Render — HTML → PDF, and the traps

- **Fonts fail silently.** Headless print does not reliably fetch Google Fonts.
  Download the TTFs and rewrite the CSS to local `@font-face` before rendering
  (curl each css2 URL, extract `fonts.gstatic.com` URLs, download in order,
  rewrite `url(...)` → `url(fonts/fN.ttf)`).
- Render headless Chromium print-to-PDF (Letter, backgrounds on, no
  header/footer). The scouting-report skill ships `scripts/render_pdf.sh` that
  locates a Chromium; reuse it. Pages are fixed `8.5in × 11in` divs with
  `overflow:hidden` — overflow is silently CLIPPED, not flowed.
- **Rasterize or Read every page and look at it yourself.** Recurring bugs: column
  text clipped mid-sentence at the page bottom (rebalance), edge tag overlapping
  header meta (pad right), figure boxes overflowing a column (constrain img
  height, drop a stat row).
- Keep the finished PDF under ~3MB for iMessage (JPEG the images; fonts are small).

## 6. Verify, deliver

Fact-check pass: read the rendered pages against the film-room file line by line —
scores, quarter line, rankings, records, down-and-distance claims, names, jersey
numbers. Deliver the PDF in chat. Don't commit issues or working files into the
vault unless asked; when asked, `dynasties/<dynasty>/media/` is the home.

## Known pitfalls

- Device-bridge staging flakes above ~3MB per file — split with `split -b 3m`,
  stage chunks, reassemble, retry failed chunks singly.
- The example HTML references per-issue images under `img/` — rebuilt every issue,
  not shipped with this skill.
- If a podcast/audio source has no transcript, transcribe it locally
  (`faster-whisper`, base.en, vad_filter) rather than skipping the source.
