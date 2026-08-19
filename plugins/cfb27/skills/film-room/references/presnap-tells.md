# Pre-snap TELL catalog — game-verified CFB 27 indicators

> **MECHANICS AUTHORITY (game creators).** Game-verified CFB 27 tells; patch-sensitive; human ranked opponents use coverage shells that defeat static-alignment tells — CPU/offline opponents don't.

This file is the film-room skill's catalog of pre-snap indicators verified in College Football 27 itself, by game creators. It sits on the game-creator side of the knowledge firewall: `football-iq.md` owns real-football *interpretation* (coverage families, leverage theory, read protocol); this file owns the game's *specific, observable* pre-snap tells — alignment depths, canned animations, and the opponent-scouting discipline built on them. Trey Thomas states the scope caveat directly: coverage shells "make it so that everything looks exactly the same," but "CPUs don't use cover shells at all in any of the offline game modes" — so these tells are most reliable vs CPU, Dynasty, RTG, and inexperienced human opponents.

---

## CB leverage & depth stack (Trey Thomas)

Read order: safeties first (one-high vs two-high narrows the tree), then outside-corner depth and shade. "The outside corners are always going to be like your easiest read"; slot corners are hard to read outside compressed sets like gun bunch. Read before the press — "it's always easier to read these things prior to the press."

| Look | CB depth | CB shade | Coverage lean |
|---|---|---|---|
| Two-high, outside shade | ~5 yds off | Outside shoulder | Cover 2 / Tampa 2 ("five yards off the ball with outside leverage") |
| One-high, outside shade | ~7 yds off | Outside | Cover 3 ("seven yards off the ball, one safety high, cover three") |
| Two-high but safeties LOW (~7 yds, "almost in line with the outside corners"), CB squared | ~7.5–9 yds off | **Square** — "not on the outside shoulder, not on the inside shoulder" | Cover 4 / match ("completely square... this is telling me cover four or match"); squareness survives even when they press |
| Any depth, **inside shade** | — | Inside shoulder | Man — "if I ever see shaded inside, I'm always 10,000% going to assume... man-to-man coverage" |
| **Staggered sides** — one CB 5 yds outside shade, other CB over the top of his WR | Split | Split | Cover 6 / Cover 9 split-field: "cover two on one side, cover three to four shell on the other side... look at the stagger" |
| One-high, outside shade | 5–7 yds off | Outside | Cover 1 (hole/robber/blitz) — "very hard to tell the difference between cover one and cover three"; call your beaters to work vs both |

Corroborating safety-count + DB-depth table (GetLiveMar coverage-ID guide, via wiki synthesis): C3 one-high 7–8 yds; C1 one-high identical to C3 until motion is tested; C2 two-high 5 yds; C4 two-high 8 yds; C2-man two-high but pressed 2–3 yds; C0 no deep safeties, everyone tight to the line; C3 match identical to C3 sky pre-snap (only post-snap route-relating separates them).

Source: `transcripts/gameplay/mechanics/137-how-to-read-pre-snap-defenses-in-college-football-27.md` **[01:05]**–**[10:59]**; synthesis in `wiki/gameplay/reading-beating-defenses.md`.

---

## QB pre-snap animation tells (ZAN, shotgun run game)

Fixed engine animations that reveal where a shotgun run with jet motion is going — applies across wildcat, gun F over twins, empty QB-run sets, and "so many different formations":

- **Wave / "come through" arm out** toward the motion man → **jet touch pass**: "he simply puts his arm out and tells the receiver to come through... the receiver is going to be taking the handoff."
- **Squat** → **QB power, WITH the motion**: "the quarterback is literally just going to squat... he's actually going to the same side that the receiver is going to."
- **Double toe-tap** → **QB counter, AWAY from the motion**: "you tap tap. Receiver comes in motion, you know the ball's going back the other way."
- **Same wave in a pass-viable formation** (e.g. jet pass fake zone) → still the jet sweep tell: "it's the exact same as the jet sweep in pretty much any other formation."
- **NO animation at all** — receiver motions and the QB "does nothing" → **pass** (or at worst RPO/screen). The absence of the animation is itself the tell.

Caveats: "there are some small edge cases" (read-option plays where the QB can still pull it); and cover 0 is explicitly flagged as high-risk against every one of these run concepts — "you do not want to run cover zero unless you're prepared to make this tackle on your own."

Source: `transcripts/gameplay/defense/55-college-football-27-how-to-read-shotgun-runs-know-exactly-wh.md` **[01:17]**–**[06:23]**; synthesis in `wiki/gameplay/reading-opponent-tendencies.md` §4.

---

## Hot-route tell (GetLiveMar)

When the offense hot-routes, "you see the quarterback is communicating with the receiver... they're touching their helmet." The helmet-touch animation identifies exactly which receiver's route was changed — GetLiveMar watches which numbers get the touch, pre-adjusts coverage toward the likely new route, and turns it into an interception.

Source: `transcripts/gameplay/defense/65-how-to-read-any-offense-in-college-football-27.md` **[25:16]**–**[26:07]**; `wiki/gameplay/reading-opponent-tendencies.md` §3.

---

## Per-formation tells (GetLiveMar)

- **Hash first — field vs boundary:** "the side of the field with the most space, you cover first." Corner-route threat lives to the field side; the boundary rarely gets a corner route unless the RB releases there. Runs also lean toward the field — "they're going to want to run to the side of the field that has the most space."
- **Bunch:** expect TE flat + corner route from the point receiver — "most of the time... they're going to have a corner or a flat route," and the flat "is what they're going to try to throw first."
- **Single-back bunch TE:** "first thing I'm alert for is the... bubble screen" to the flanker; shift the front toward the field side.
- **Trips TE:** "soon as I see a trips tight end... I'm going to be alert for this tight end releasing on a corner route."
- **Y-off trips (TE + RB same side):** "anytime I see this... I'm already alert for an RPO."
- **Balanced set / ball on the middle hash:** no strong/weak read available — don't guess; play the LB 5 yards off and "react off the running back" path at the snap, without over-strafing.
- **Repetition rule:** "you could do it once, but you can't do it twice" — a second rep of any surprise formation/play is fully scoutable.

Source: `transcripts/gameplay/defense/65-how-to-read-any-offense-in-college-football-27.md` **[02:35]**–**[24:10]**; `wiki/gameplay/reading-opponent-tendencies.md` §3.

---

## Series-logging method (Christian Sam)

The discipline the film room's `series_book` lane implements — an ex-NFL linebacker charting a live opponent drive-by-drive:

- **Log everything as a data point:** "when a game first starts, you got to learn your opponent... what is this guy doing to me?" Every motion, formation, and personnel group goes in the book.
- **Motion → pass tracking:** the game's core discovery — this opponent's every pre-snap motion preceded a pass, "it didn't matter if it was a tight end, the receiver. If he motions, it was pass" — license to pass-commit or send pressure once confirmed.
- **Rep-count formation → play pairs:** "log it. So, now two times he's ran that formation, he's ran QB lead" — twice = scoutable (mirrors GetLiveMar's once-but-not-twice rule).
- **Sky-then-Match sequencing:** open in spot-drop — "I go on sky first so I could kind of see the kind of route combinations they're running. And once I understand the route combinations... then we go to match." Crosser-heavy offense → stay out of match; developing deep routes → switch to match.
- **First-drive probes:** the opening drive(s) are for information gathering; the payoff is scripted — "third, fourth quarter, let's start pulling away... who's going to make the quickest adjustments?"
- **Personnel-substitution signals:** a backup QB entering resets QB-run expectations — Sam stops shifting his line for designed runs the new QB hasn't shown. Down-and-distance is a tendency axis too (the 4th-down deep stop route called before the snap).
- **Failure attribution — scheme vs engine bug:** separate "we got beat by scheme" from "we got beat by a game issue" (missed tackles; the block-shed bug where defenders play "ring around the Rosy's pocket... nobody's off a block"). **Never chart a bug or a missed tackle as an opponent tendency** — that overcorrects the gameplan for something the opponent didn't earn.

Source: `transcripts/gameplay/defense/37-nfl-linebacker-breaks-down-every-defensive-stop-in-win-vs-pr.md` **[01:03]**, **[04:23]**, **[08:39]**–**[09:33]**, **[17:06]**–**[18:22]**, **[28:03]**–**[29:20]**, **[41:44]**; `transcripts/gameplay/defense/103-how-i-beat-the-1-pro-player-in-the-world-full-breakdown.md` **[06:00]**, **[14:21]**; `wiki/gameplay/reading-opponent-tendencies.md` §1.

---

## Condensed table for batch prompts

| Frame observation | Lean |
|---|---|
| Outside CB ~5yd off, outside shade, two-high | Cover 2 / Tampa 2 |
| Outside CB ~7yd off, outside shade, one-high | Cover 3 (Cover 1 possible — same look) |
| CB ~7-9yd, SQUARE over WR, low flat-footed two-high safeties | Cover 4 / match (squareness survives press) |
| CB inside shade (any depth) | Man coverage |
| Two CBs staggered — one 5yd outside shade, other over-the-top | Cover 6/9 split field |
| No deep safeties, DBs tight to line | Cover 0 / man blitz |
| QB waves motion man through = jet touch; QB squat = QB power w/ motion; double toe-tap = QB counter away; QB does NOTHING on motion = pass | Run-type lean |
| QB + receiver touch helmets | That receiver's route was hot-routed |

Tells inform reads, never override observed behavior; chart the behavior fields, not these conclusions.
