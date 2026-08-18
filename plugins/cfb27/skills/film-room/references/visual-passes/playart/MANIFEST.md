# CFB 27 in-game defensive play art (cfblabs.com/play-finder)

**Private reference use only. Not for republication.** Captured 2026-07-30 from CFB Labs' play finder (public Cloudinary CDN, source URLs per play in `_sources.json`). 171 defensive play-art PNGs — the literal images CFB 27 draws in its play-call menus — plus `playart-key.jpg` (zone-color legend + 12 canonical coverages).

## Why this layer exists

This is the **ground-truth art for the game's own zone vocabulary**. When opponent film shows a play-call menu or the coach-cam overlay, the zone shapes/colors on screen come from this same art. A menu tile identified here beats any behavior read.

## Zone color legend (user-verified 2026-07-30)

| Color | Meaning |
| --- | --- |
| Dark blue | Inside/outside QUARTERS, DEEP HALF, DEEP THIRD |
| Yellow-olive | HOOK CURL, 3 REC HOOK, MID READ |
| Teal | CLOUD FLAT |
| Translucent baby blue | HARD FLAT |
| More-opaque baby blue | SOFT SQUAT |
| Deep/royal purple | CURL FLAT |
| Lavender | SEAM FLAT |
| Orange circle | QB SPY |
| Lone dot with no zone | MAN-TO-MAN assignment |

Also on every image: bottom-left **tag badge** (MAN orange / ZONE blue / MATCH purple / BLITZ red) — the game's own classification of the play; red arrows = rushers (count them for pressure).

## Coverage inventory highlights

- Full families: COVER 1 (20 variants incl. ROBBER, HOLE, STING, CONTAIN), COVER 2 (15 incl. MAN, MATCH, INVERT, TAMPA, LURK, HARD FLAT, SINK), COVER 3 (19 incl. SKY, MATCH, BUZZ, BUZZ MATCH, CLOUD, DROP, HARD FLAT, LOCK, MAN — no MABEL, see gaps), COVER 4 (QUARTERS, PALMS, DROP, SHOW 2), COVER 6 (INVERT, PRESS, TRAP, WILLIE), TAMPA 2 family, PREVENT, plus ~90 blitzes/pressures.
- **No "COVER 0" play exists in CFB 27** — all-out pressure is named ZERO BLITZ / BLITZ LOOP 0 etc. If a menu tile says "0", it's a blitz name, not a coverage family label.
- 10 blitz-variant images 404 on the CDN (listed nowhere here) — re-check the site after their next data refresh if needed.

## Usage

- `playart-key.jpg` may be attached to charting batches as a third key (schematic → play art → game exemplar → film).
- Filenames are kebab-case play names (`cover-3-buzz-match-wk.png`); `_sources.json` maps play name → source URL (which also encodes one front/sub-formation that carries the play).

## Model-risk gaps (flagged 2026-07-30, schematic recolor pass)

1. **Play art ≠ post-snap behavior.** Zones on art (incl. MATCH-badged plays) are assignment landmarks; match coverages will still carry verticals live. Never let art zones override the hips/eyes read on film.
2. **Hard flat vs soft squat differ only by opacity** — unreliable on compressed film frames. When it matters, resolve from the tile TEXT ("HARD FLAT"/"DROP") not the color.
3. **Yellow collision inside our schematics**: hook zones (olive), man/carry arrows and tell rings (bright yellow) share a hue family. Legend disambiguates; agents decode by shape (ellipse vs arrow vs ring), not hue alone.
4. **Coach-cam overlay colors are assumed identical to menu play art** — verified from play art only. Confirm against live coach-cam footage on the next opponent film; adjust decoder if they differ.
5. **"Cover 0" and "Mabel" are not CFB 27 play names.** Menu lane can never confirm them: cover-0 family = ZERO BLITZ-style names; Mabel is Christian Sam terminology — behavior-only call, chart it as cover-3 with a note.
6. **10 blitz arts 404** on the CDN — those plays can appear in menus with no art reference here.
7. **Art is drawn vs a generic 2x2 offense** — vs trips the game re-draws zone placements; don't match zone POSITIONS literally, match color+count+structure.
