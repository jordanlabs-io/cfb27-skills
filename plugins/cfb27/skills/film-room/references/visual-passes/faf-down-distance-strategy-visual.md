---
context: real-football
source: Fourth and Film, "Every Down & Distance Strategy Explained in 18 Minutes" (YouTube gnU4IAiCncw)
pass_type: visual
---

# Fourth and Film — Down & Distance Strategy — Visual Pass

Two recurring graphic types, both whiteboard/motion-graphic style (not raw NFL/college
film): **(1) labeled play-diagram cards** — full 11-personnel formation on a green
field with position boxes color-coded by role (QB=black, RB/FB=red, OL=blue,
TE=pink, WR=yellow, defense=white), a bold title naming the exact play call, and a
small playbook-style route thumbnail in the bottom-left corner tagged with the
down-and-distance situation (e.g. "1st & Short," "3rd & Long") — and **(2)
text-only stat/strategy cards** (green/black marker on white) showing conversion
percentages or defensive/offensive goals as bullet checkmarks.

## Down-by-down: what's drawn

- **First & 10** [00:00–01:00]: Stat card, green text "20-25% [convert play]",
  black "Convert Play." Frame: `gnU4IAiCncw-0050-stat-card-1stand10-conversion.jpg`.
- **First & Short** [01:08–04:56]: Full play-diagram card, **"Gun Doubles Right
  Inside Zone"** — doubles formation (2x2), gun QB, RB offset, tagged "1st & Short"
  in the corner thumbnail. This is the example play walked through in detail
  (defensive tendency/tell setup for the whole video). Frame:
  `gnU4IAiCncw-0200-gun-doubles-right-inside-zone-1stshort.jpg`.
- **First & Long** [04:56–05:57]: No dedicated diagram captured in this pass —
  narration only (quick/safe throws, low sack risk).
- **Second & Short** [05:57–09:00]: Full play-diagram card, **"I Right Slot 28
  Boot Left Z-Pop X-Post"** — I-formation with FB+RB stacked behind QB under
  center, TE strong right, Z receiver moved to slot, tagged "2nd & Short." This
  is a play-action boot naming convention example (hole number + route names in
  the title itself). Frame:
  `gnU4IAiCncw-0707-i-right-slot-28-boot-left-2ndshort.jpg`.
- **Second & Medium** [09:00–10:07]: Mesh-concept diagram with a pre-snap motion
  receiver and two shallow crossing ("mesh") routes drawn — used to illustrate
  reading coverage off motion. Frame:
  `gnU4IAiCncw-0900-mesh-concept-motion-3rdmedium.jpg` (captured near this
  region; note mesh is described in narration under Third & Medium at ~13:47 too
  — the diagram may be the shared reference image, re-verify exact down tag in
  its corner thumbnail before citing).
- **Second & Long** [10:07–11:07]: No dedicated diagram — narration only
  (checkdowns, tackle-in-space math).
- **Second & Very Long** [11:07–12:00]: Diagram showing a draw-play concept —
  offensive line pass-set while backfield holds/hits a delayed run lane; yellow
  route lines show the delayed handoff path. Frame:
  `gnU4IAiCncw-1150-draw-play-2ndverylong.jpg`.
- **Third & Short** [12:00–13:39]: Full play-diagram card, **"I Right Duo"** —
  I-formation, FB lead block, RB following, tagged "3rd & Short." Illustrates
  double-team/gap-scheme blocking (duo) as the go-to short-yardage run. Frame:
  `gnU4IAiCncw-1306-i-right-duo-3rdshort.jpg`.
- **Third & Medium** [13:39–14:31]: Mesh concept described again here in
  narration (motion receiver + criss-crossing routes to create natural picks) —
  same diagram type as the Second & Medium frame above; confirm which down tag
  the actual on-screen thumbnail carries if citing precisely.
- **Third & Long** [14:31–15:19]: Full play-diagram card, **dagger concept** — TE
  running a vertical go/seam route (long yellow line straight upfield) with two
  stacked WRs underneath running a dig, tagged "3rd & Long." Frame:
  `gnU4IAiCncw-1443-dagger-concept-3rdlong.jpg`.
- **Third & Very Long** [15:19–16:12]: No dedicated diagram — narration only
  (draw/screen plays, conservative deep-shell defense).
- **Fourth & Inches** [16:12–16:44]: No diagram — narration only (tush push/QB
  sneak).
- **Fourth & Short** [16:44–17:56]: Full play-diagram card, **"Slant Flat"** —
  standard pro-style formation, outside WRs running slant, TE/inside WR running
  quick flat/out routes, tagged "4th & Short." Frame:
  `gnU4IAiCncw-1645-slant-flat-4thshort.jpg`.
- **Fourth & Medium** / **Fourth & Long** [17:56–end]: No dedicated diagrams —
  narration only (quick high-percentage throws / low-percentage long-developing
  passing concepts).

## Notes for charting agents

- Every play-diagram card **names the exact play call in its title bar** and tags
  the down/distance in a small corner thumbnail (mini field with the actual
  route tree drawn) — this is a directly reusable template for validating our
  `play_call` and `down_distance` charting fields against a canonical example.
- Color coding is consistent across every diagram: QB=black, RB/FB=red, OL=blue,
  TE=pink/magenta, WR=yellow, all defenders=white. Useful as a fast visual
  legend when auto-classifying frame screenshots.
- Stat/strategy cards (percentages, "DEFENSE GOAL" bullet lists, "Run = More
  likely" field-position notes) appear as plain marker-on-whiteboard text with no
  play diagram — these encode the situational tendency data (conversion %s by
  down-distance bucket) that could seed a reference table for `situational
  tendency` scoring, but are not visual/diagram content per se.
