# The PDF brief — design system + render pipeline

Two fixed Letter pages. Page 1 = "The Book on <coach>" (identity, tells, QB,
danger men, three-keys band). Page 2 = "The Game Plan" (diagram, attack, stop,
manage, self-scout band). The template (`assets/brief-template.html`) is the
shipped WVU-vs-Maryland brief — swap tokens and content, keep the system.

## Who it's for shapes everything

The brief is read by one coach, probably on a phone, probably the night before
the game. Keys only: every line must be actionable or a tell. Citations,
methodology, sample-size hedging, and the recipient's own counter numbers stay in
the vault report. Confidence language survives only where it changes a decision
("single-sighting read — treat as a lead").

## Design tokens

Brand the brief in the **beneficiary's** school colors. CSS custom properties at
the top of the template; change only these. Tint neutrals toward the primary hue
(never pure #fff/#000). League palette (Weef, primary/secondary):

| School | Primary | Accent |
| --- | --- | --- |
| West Virginia | `#002855` navy | `#EAAA00` old gold |
| North Carolina | `#4B9CD3` carolina | `#13294B` navy |
| Maryland | `#E03a3e` red | `#FFD520` gold |
| Baylor | `#154734` green | `#FFB81C` gold |
| Arizona | `#AB0520` cardinal | `#0C234B` navy |
| Northwestern | `#4E2A84` purple | `#d8d8d8` grey-tinted |
| Vanderbilt | `#1C1C1C` near-black (tint!) | `#A8996E` gold |
| NC State | `#CC0000` red | `#1f2429` ink |
| Kansas State | `#512888` purple | `#D1D1D1` silver-tinted |
| Rutgers | `#CC0033` scarlet | `#1f2328` ink |

Dark-primary schools (Vanderbilt, Northwestern): keep the masthead in the primary,
move body accents to the secondary, and verify text contrast on the tint boxes.

Type (all macOS system fonts — no web fonts, they silently fail in headless
print): Avenir Next Condensed for display (all-caps, the gameday-graphic
vernacular), Avenir Next for body, Menlo for stats/tells values (call-sheet
precision). Sports-brief conventions that earn their place: the striped
masthead rule, the full-width thesis band (the report's single biggest finding),
the vertical "THE KEYS" tab.

Design rules carried from the polish pass: no left/right border-stripe accents
(use full-border tint boxes for hot items), no em dashes in copy, numbered
markers only where order = priority, stat digits in Menlo.

## The diagram (the signature)

One chalk-on-navy SVG panel diagramming the highest-leverage concept of THIS plan
(e.g. Smash + hole shot vs Cover 3 Cloud Press). Draw it real: offense as gold
circles, defenders as white letter marks with Menlo labels, routes as gold
arrowed paths, the exploited window as a dashed translucent rect. A caption line
ties it to the recipient's own concepts. If the plan has no single diagrammable
concept, replace the panel with the tells table — never ship a decorative diagram.

## Render + inspect loop

```bash
<skill-base-dir>/scripts/render_pdf.sh <brief.html> <out.pdf>
```

The script finds a headless Chromium (Playwright cache) and prints to PDF with
backgrounds, no header/footer. Then **Read the PDF and look at both pages**.
Fixed `8.5in × 11in` pages with `overflow:hidden` clip silently — the recurring
bugs, in order of frequency:

1. Bottom-band clipping: upscaled type pushes the keys band/footer off page 1.
   Fix type scale or section margins, not the band.
2. List-style leakage: any `ol`/`ul` outside the styled containers renders
   browser-default 16px.
3. Diagram label collisions: route paths crossing label text — move labels, not
   routes.
4. Unbalanced pages: one page dense, one half-empty. Rebalance sections or scale
   type per-page (a page-scoped class), never globally.

Iterate render → look → fix until both pages are clean. Keep the PDF under ~3MB
if it may travel by iMessage.
