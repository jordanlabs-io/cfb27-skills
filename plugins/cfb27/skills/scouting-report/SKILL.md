---
name: scouting-report
description: Build a full matchup scouting report + game plan ("the book") on a CFB 27 league opponent, for the user's own upcoming game OR to hand to another league member you want to win. Fuses the rival dossier, every charted film-room game, call-sheet counter ledgers, H2H/season context, and cited wiki strategy into a vault markdown report plus a school-branded multi-page visual scouting report (PDF). Use whenever the user says "scouting report", "game plan", "scout <team>", "prep me for <team/coach>", "help <league member> beat <team>", "put together the book on <coach>", or wants opponent tendencies packaged as a document — even if they don't name a deliverable format. The branded standard is the multi-page image-led visual report; a phone-ready 2-page PDF brief is the compact alternate. Capturing dynasty data belongs to dynasty-tracker; charting new film belongs to film-room; this skill only reads what they produced.
---

# Scouting Report — the book on one opponent

One report = scope → gather → weigh → write → brand → verify. The deliverable is
two artifacts: a fully-sourced vault markdown report and a school-branded visual
report PDF. The markdown report is always written — it is the source of record
that both PDF formats read from. The worked example that set the branded format:
`dynasties/north-carolina/film-room/2027-unc-vs-vanderbilt-gameplan.md` (+ the
Vanderbilt visual report). The earlier 2-page-brief example
(`2027-wvu-vs-maryland-gameplan.md`) is superseded as the visual standard.

## 1. Scope the request

Pin down three things before reading a single file:

- **Opponent** — the team/coach being scouted.
- **Beneficiary** — whose game plan this is. Usually the user's own team; sometimes
  an ally (another league member whose win helps the user). The plan must be
  executable *with the beneficiary's actual scheme*, so their film matters too.
- **Recipient** — who will read it. If the beneficiary is NOT the user, ask two
  questions before writing (AskUserQuestion if available):
  1. **Scope:** full send (include the beneficiary's own self-scout fixes, which
     reveals the user has film on them) vs opponent-intel only.
  2. Confirm the deliverable (vault doc only / + PDF / + phone-ready text).

## 2. The intel-protection rule (non-negotiable)

Menu-tile counter data (call counts and avg-yds harvested from a coach's own
screen, e.g. "WS BLITZ 3 — 30 CALLS, 8.7 AVG") is the vault's most sensitive
intel — it proves exactly how much film the user holds on that coach.

- **The recipient's own counter numbers NEVER appear in anything handed to them.**
  Self-scout advice is delivered qualitatively ("your safety-blitz calls have
  leaked chunk plays on film; your zone looks have been far stingier").
- Behavioral game stats about the recipient are fine (3rd-down rates, formation
  tells) — those could come from anyone's memory of playing them.
- The **opponent's** counter numbers are used freely; that's the product.
- When the beneficiary is the user themself, the rule is moot — use everything.

## 3. Gather (all read-only)

From the dynasty (`dynasties/<slug>/`):

- `league/teams/<opponent>.md` — the dossier: identity claims, "the book", data caveats.
- Every `film-room/games/*.md` involving the opponent — read them, not just the
  dossier; game reports carry situational detail (drive tables, money-down splits,
  turnover ledgers) the dossier compresses away.
- `film-room/call-sheets/<opponent>.csv` — the counter ledger. Also the
  beneficiary's ledger *if the user's own planning needs it* (never quoted to them).
- `league/teams/<beneficiary>.md` + their film — what they can actually execute,
  and the self-scout material.
- `league/h2h.md`, `seasons/<year>.md`, `_dynasty.md` — who controls whom, stakes,
  standings context.
- Note explicitly when no head-to-head film exists between the two teams — the
  report is then "the opponent book projected onto the beneficiary's scheme."

From the wiki: coverage/scheme/mechanics/game-management pages that match the
opponent's identified scheme (e.g. opponent lives in Cover 3 Cloud → the cover-3
family, seam-flat conflict, and hole-shot pages). **Copy each claim's citation
verbatim** in the vault's standard format `([[<transcript-file>|Title]] **[MM:SS]**)`
— never fabricate or paraphrase a citation, and never cite wiki claims that aren't
actually on the page. If the wiki has no page for a recommendation (e.g. 4th-down
math), ground it in film evidence and say so rather than inventing a citation.

## 4. Weigh the evidence (source authority)

Inherited from the film-room skill's calibration — apply, and disclose in the report:

1. **Menu counters are verbatim call-sheet truth** and outrank behavior-derived
   reads where they conflict (pressed cloud corners fake out man/zone tell stacks).
2. Single-sighting counter reads are leads, not facts — flag them.
3. Trailing-script / garbage-time film grades a coach under duress, not identity —
   weight neutral-script film for who they are; use the duress film for how they
   break.
4. Matchup-dependence is real: a defensive profile shown vs one offense may not
   travel. Say which version the beneficiary should expect and why.
5. Provenance tiers (pro > frames > flash) carry into confidence language.

## 5. Write the vault report

File: `dynasties/<slug>/film-room/<season>-<beneficiary>-vs-<opponent>-gameplan.md`.
**No `type:` frontmatter** (the dynasty verifier whitelists types when present).
Links to dynasty files are path-qualified; links to wiki pages use bare filenames.

Structure (adapt emphasis to the matchup, keep the spine):

1. **Header** — who it's for, who it's on, sources listed with wikilinks, the
   no-direct-film disclosure if applicable.
2. **What to look out for** — opponent identity: offensive identity + signature
   calls, pre-snap tells (formation weights, motion rate, screen alerts), QB
   profile, defensive call-sheet truth, personnel danger men. Lead with the single
   most game-shaping thesis (e.g. "he is a front-runner — deny the lead and he has
   no plan B").
3. **How to attack** — vs their defense, married to what the beneficiary already
   runs well ("your Smash family is already the cloud-beater" lands better than a
   generic concept list). Wiki citations on every strategy claim.
4. **How to stop** — vs their offense: the money-down formula, spy/pressure rules,
   tells table, tempo defense.
5. **How to manage the game** — the lead/script thesis, ball-security rules,
   timeout and tempo discipline, 4th-down posture.
6. **Self-scout** (full-send only) — the beneficiary's own leaks, phrased per the
   intel-protection rule.
7. **Data quality & confidence** — sample sizes, tiers, caveats, single-sighting
   flags. A report that hides its uncertainty gets a coach beat.

Number the plan lists — order = priority, and a coach mid-game reads ranked keys.

## 6. Pick the deliverable format

The markdown vault report (§5) is always produced. On top of it, one of two PDFs:

- **The visual report** (§6a) — **the default and the branded standard.** 6 to 8
  Letter pages in the school's real brand with game renders, the full call sheet,
  personnel, head-to-head and game management. This is what a scouting report
  looks like unless there is a reason it can't be.
- **The 2-page PDF brief** (§6b) — the compact alternate. A phone read for one
  coach the night before: keys only, one chalk diagram, no photos. Use it when the
  recipient asked for something short, when no charted film exists to illustrate,
  or when the vault report has less ranked content than the visual pages need.

Default to the visual report; ask only if the request implies the short form.
Building both is fine and cheap — the brief is a subset of the visual report's
content. Either way, re-check §2 before handing a PDF to a recipient who is not
the user: more pages means more chances to leak counter numbers.

## 6a. The visual report (default)

Read `references/visual-report.md` for the build order, the chrome and type
system, brand-asset rules, imagery sizing, the page inventory, and the
fixed-height layout failures that eat the most time (`align-content:
space-between` phantom gutters above all). Essentials: read the school's real
brand assets before laying anything out; identical chrome on every page; three
typefaces (condensed display, serif body, mono labels) and an eight-color palette;
one captioned render per content page at its true aspect ratio, never cropped or
letterboxed; explicit `grid-template-rows` with a single `1fr` track; every
pixel of freed space filled with real vault content. Start from
`assets/visual-report-template.dc.html` (the Vanderbilt document source) and
check your work against `assets/visual-report-example-vanderbilt.html` (the
rendered bundle). Save the PDF next to the vault report; deliver via
SendUserFile.

## 6b. The 2-page PDF brief (compact alternate)

Read `references/pdf-brief.md` for the design system, school color tokens, layout
rules, and render pipeline. Essentials: 2 fixed Letter pages in the beneficiary's
school colors, keys only (no citations, no methodology, no recipient counter
numbers), one chalk-style SVG diagram of the highest-leverage concept, a
three-keys band. Start from `assets/brief-template.html`, render with
`scripts/render_pdf.sh`, then **look at every rendered page yourself** (the Read
tool renders PDFs) — fixed pages clip overflow silently. Save the PDF next to the
vault report; deliver via SendUserFile.

## 7. Verify, log

- `verify_dynasties.py` (dynasty-tracker skill's scripts) must pass — the new
  file's path-qualified links are checked.
- Spot-check every copied wiki citation against its source page (grep the
  timestamp markers) — citations are copied, never authored.
- Append a deliverable entry to `operations/activity-log/YYYY-MM-DD.md`.
- Sending the brief to the recipient (iMessage etc.) is the user's move — offer,
  don't send.

## Boundaries

- Read-only toward film-room data and dossiers; if film is missing, say what an
  iPad capture of the opponent would add — don't chart here (that's film-room).
- Game results/H2H tallies are dynasty-tracker's; never update them from here.
- `wiki/` is cited, never edited, and never receives dynasty data (one-directional
  coupling).
