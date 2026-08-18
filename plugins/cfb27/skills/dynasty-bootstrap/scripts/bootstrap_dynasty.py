#!/usr/bin/env python3
"""Bootstrap a new CFB 27 dynasty folder from a CFB Labs team roster.

Scrapes https://www.cfblabs.com/teams/<slug> (team page + every player detail
page) and generates the dynasty folder per dynasty-tracker conventions:

  dynasties/<slug>/
    roster.csv        full ratings snapshot (id..TGH, ~64 cols)
    roster.md         standard 8-col roster table (Archetype/Dev trait = TBD)
    records.md        append-only records file with import milestone
    _dynasty.md       hub with DEFAULT frontmatter (mode: offline, members: 1)
                      -- Claude must confirm mode/league with the user after
    recruiting/team-needs.md   depth/OVR/departing-seniors per position group
    league/h2h.md
    seasons/<year>.md
    League.base  Recruiting.base

It does NOT touch dynasties/_index.md (Claude edits that) and never overwrites
an existing dynasty folder unless --force.

Usage:
  python3 bootstrap_dynasty.py <team-slug> [--vault PATH] [--season YEAR] [--force]
  e.g. python3 bootstrap_dynasty.py mississippi-state --season 2026
"""
import argparse, csv, datetime, json, os, re, sys, time, urllib.request

BASE = "https://www.cfblabs.com"
UA = {"User-Agent": "Mozilla/5.0 (Macintosh) roster-import/1.0"}
CLS = {"FRESHMAN": "FR", "SOPHOMORE": "SO", "JUNIOR": "JR", "SENIOR": "SR"}
POS_ORDER = ["QB", "HB", "FB", "WR", "TE", "LT", "LG", "C", "RG", "RT",
             "LEDG", "REDG", "DT", "SAM", "MIKE", "WILL", "CB", "FS", "SS", "K", "P"]
GROUPS = {"QB": ["QB"], "RB": ["HB", "FB"], "WR": ["WR"], "TE": ["TE"],
          "OL": ["LT", "LG", "C", "RG", "RT"], "EDGE": ["LEDG", "REDG"],
          "DT": ["DT"], "LB": ["SAM", "MIKE", "WILL"], "CB": ["CB"],
          "S": ["FS", "SS"], "ST": ["K", "P"]}
META = ["id", "first_name", "last_name", "position", "number", "height", "weight",
        "tendency", "class", "hometown", "hometown_coordinates", "team",
        "team_index", "player_index", "physicals", "mentals"]


def get(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "replace")


def slugify(name):
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def title_name(s):
    t = s.title()
    t = re.sub(r"\b(ii|iii|iv|vii?i?)\b", lambda m: m.group(0).upper(), t, flags=re.I)  # II, III, IV, V-VIII
    t = re.sub(r"'([A-Z])", lambda m: "'" + m.group(1).lower(), t)  # Pome'E -> Pome'e
    return t


def cls_of(p):
    c = p.get("class", "")
    if c.startswith("REDSHIRT_"):
        return "RS-" + CLS.get(c.replace("REDSHIRT_", ""), c)
    return CLS.get(c, c)


def posgroup(p):
    return (p.get("position_detail") or p["position"]).split(" ")[0]


def scrape(slug, delay):
    html = get(f"{BASE}/teams/{slug}")
    ix = html.find('"allPlayers":')
    if ix == -1:
        sys.exit(f"allPlayers payload not found on {BASE}/teams/{slug} — "
                 "check the slug, or the site layout changed (see SKILL.md fallback).")
    players, _ = json.JSONDecoder().raw_decode(html[ix + len('"allPlayers":'):])
    if not players:
        sys.exit(f"cfblabs.com has NO roster data for '{slug}' (allPlayers is empty on the "
                 "site itself — known for some teams, e.g. Mississippi State as of 2026-07). "
                 "Verify the slug via the sitemap "
                 "(curl -sL https://www.cfblabs.com/sitemap-0.xml | grep -oE '/teams/[a-z0-9-]+'); "
                 "if the slug is right, the site lacks this team — import the roster manually "
                 "from in-game screens instead.")
    print(f"team page: {len(players)} players", flush=True)
    failed = []
    for i, p in enumerate(players):
        name = f"{p['first_name']} {p['last_name']}"
        url = f"{BASE}/teams/{slug}/{p['id']}-{slugify(name)}"
        try:
            m = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>',
                          get(url), re.S)
            detail = m.group(1)
            detail = json.loads(detail)["props"]["pageProps"]["initialPlayer"]
            p["position_detail"] = detail.get("position", "")
            for k, v in detail.items():
                if k not in ("__typename", "position") and v is not None:
                    p[k] = v
        except Exception as e:
            failed.append((name, url, str(e)))
            p["position_detail"] = ""
        time.sleep(delay)
        if (i + 1) % 20 == 0:
            print(f"  fetched {i+1}/{len(players)}", flush=True)
    return players, failed


def write_all(players, slug, team_name, season, out, today):
    for d in ("recruiting", "league", "seasons"):
        os.makedirs(os.path.join(out, d), exist_ok=True)
    rating_keys = [k for k in players[0] if k not in META
                   and k not in ("__typename", "position_detail")]

    # roster.csv
    cols = ["id", "name", "position", "position_detail", "number", "class",
            "height", "weight", "hometown", "abilities"] + rating_keys
    with open(os.path.join(out, "roster.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(cols)
        for p in players:
            abil = ";".join((p.get("physicals") or []) + (p.get("mentals") or []))
            w.writerow([p["id"], f"{p['first_name']} {p['last_name']}", p["position"],
                        p.get("position_detail", ""), p.get("number", ""), p.get("class", ""),
                        p.get("height", ""), p.get("weight", ""), p.get("hometown", ""), abil]
                       + [p.get(k, "") for k in rating_keys])

    # roster.md
    def key(p):
        g = posgroup(p)
        return (POS_ORDER.index(g) if g in POS_ORDER else 99, -p["OVR"])
    rows = []
    for p in sorted(players, key=key):
        name = title_name(f"{p['first_name']} {p['last_name']}")
        abil = (p.get("physicals") or []) + (p.get("mentals") or [])
        top = abil[0].replace("_", " ") if abil else ""
        notes = f"#{p.get('number', '')}" + (f" · {top}" if top else "")
        rows.append(f"| {name} | {posgroup(p)} | {cls_of(p)} | TBD | {p['OVR']} | TBD |  | {notes} |")
    with open(os.path.join(out, "roster.md"), "w") as f:
        f.write(f"""# {team_name} — Roster

Current players, one row each. Persistent across seasons — players age up at archive time, never cleared. Imported from CFB Labs (cfblabs.com) {today}; ratings snapshot in `roster.csv`.

<!--
Class enum: FR | SO | JR | SR (RS- prefixes allowed, e.g. RS-SO for a redshirt sophomore).
Status conventions: active is the default (leave blank or "active"); other values —
  injured | review | transferred | graduated.
  "review" = flagged at season archive for the user to confirm graduated/drafted (never auto-deleted).
Archetype / OVR = TBD when unknown at capture time (append the gap to _dynasty.md ## Loose ends).
-->

| Name | Pos | Class | Archetype | OVR | Dev trait | Status | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- |
""" + "\n".join(rows) + "\n")

    # team-needs.md
    lines = []
    for g, poss in GROUPS.items():
        m = sorted([p for p in players if posgroup(p) in poss], key=lambda p: -p["OVR"])
        if not m:
            lines.append(f"## {g}\n\n- Depth: 0 — no players at this group; recruiting priority\n")
            continue
        ovrs = [p["OVR"] for p in m]
        srs = sum(1 for p in m if p.get("class") == "SENIOR")
        top = ", ".join(f"{p['first_name'].title()} {p['last_name'].title()} ({p['OVR']} {cls_of(p)})"
                        for p in m[:3])
        lines.append(f"## {g}\n\n- Depth: {len(m)} · top OVR {max(ovrs)} · avg {sum(ovrs)/len(ovrs):.0f}"
                     f" · {srs} seniors departing after {season}\n- Top: {top}\n")
    with open(os.path.join(out, "recruiting", "team-needs.md"), "w") as f:
        f.write(f"# {team_name} — Team Needs\n\nPosition-group priorities. Resets each season. "
                f"Seeded {today} from the CFB Labs roster import — adjust priorities once the save is live.\n\n"
                + "\n".join(lines))

    # records.md / h2h.md / season file / hub / bases
    with open(os.path.join(out, "records.md"), "w") as f:
        f.write(f"# {team_name} — Records\n\nAppend-only. Awards, program records, milestones.\n\n"
                f"## Player awards\n\n## Team & program records\n\n## Milestones\n\n"
                f"- {today} — Dynasty started; roster imported from CFB Labs ({len(players)} players).\n")
    with open(os.path.join(out, "league", "h2h.md"), "w") as f:
        f.write(f"# {team_name} — Head-to-head\n\nCanonical record vs. each league member. "
                "One `##` section per member.\n")
    with open(os.path.join(out, "seasons", f"{season}.md"), "w") as f:
        f.write(f"""---
type: season
dynasty: {slug}
year: {season}
record: ""
postseason: ""
---

# {team_name} — {season} Season

## Results

| Week | Opponent | H/A | W/L | Score | Notes |
| --- | --- | --- | --- | --- | --- |
""")
    with open(os.path.join(out, "_dynasty.md"), "w") as f:
        f.write(f"""---
type: dynasty
team: "{team_name}"
mode: offline
league_name: ""
members: 1
current_season: {season}
started: {season}
tags: [type/dynasty, dynasty/{slug}]
---

# {team_name} — Dynasty Hub

Offline save (DEFAULT — confirm with user). Live season: **{season}**. Roster imported from CFB Labs on {today}.

## League members

| Person | Team |
| --- | --- |
| (you) | {team_name} |

All-time record:

## Pages

- [[dynasties/{slug}/roster|Roster]] — current players (single table); full ratings snapshot in `roster.csv`
- [[dynasties/{slug}/Recruiting.base|Recruiting board]] — live + all-time recruit views
- [[dynasties/{slug}/recruiting/team-needs|Team needs]] — position-group priorities (resets each season)
- [[dynasties/{slug}/league/h2h|Head-to-head]] — canonical record vs. each league member
- [[dynasties/{slug}/League.base|League teams]] — rival team notes
- [[dynasties/{slug}/seasons/{season}|{season} season]] (live)
- [[dynasties/{slug}/records|Records]] — awards, program records, milestones (append-only)

## Loose ends

<!-- Landing zone for facts the user mentioned but couldn't fully specify. Reconciled opportunistically next session; never blocks a capture. -->

- Archetype and Dev trait for all {len(players)} imported players are TBD — CFB Labs does not publish them; fill from in-game roster screens.
- `mode: offline`, `members: 1`, and `league_name` are defaults — confirm with user.
""")
    with open(os.path.join(out, "League.base"), "w") as f:
        f.write(f"""filters:
  and:
    - 'file.inFolder("dynasties/{slug}/league/teams")'
    - 'type == "rival-team"'
views:
  - type: table
    name: "League teams"
    order:
      - team
      - controlled_by
""")
    with open(os.path.join(out, "Recruiting.base"), "w") as f:
        f.write(f"""views:
  - type: table
    name: "Live board"
    filters:
      and:
        - 'file.inFolder("dynasties/{slug}/recruiting")'
        - 'type == "recruit"'
        - 'archived != true'
    order:
      - name
      - position
      - stars
      - state
      - status
      - priority
    sort:
      - property: stars
        direction: DESC
    groupBy:
      property: source
      direction: ASC
  - type: table
    name: "All-time"
    filters:
      and:
        - 'type == "recruit"'
        - 'dynasty == "{slug}"'
    order:
      - name
      - position
      - stars
      - state
      - status
      - priority
      - season
    groupBy:
      property: season
      direction: DESC
""")
    return rating_keys


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("slug", help="cfblabs.com team slug, e.g. oregon-state")
    ap.add_argument("--vault", default=".", help="vault root (default: cwd)")
    ap.add_argument("--season", type=int, default=2026)
    ap.add_argument("--delay", type=float, default=0.3)
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()

    out = os.path.join(a.vault, "dynasties", a.slug)
    if os.path.exists(out) and not a.force:
        sys.exit(f"{out} already exists — pass --force to overwrite.")

    players, failed = scrape(a.slug, a.delay)
    team_name = players[0].get("team", a.slug.replace("-", " ")).title()
    today = datetime.date.today().isoformat()
    rating_keys = write_all(players, a.slug, team_name, a.season, out, today)

    missing_ovr = sum(1 for p in players if not p.get("OVR"))
    print(f"\nwrote {out}: {len(players)} players, {len(rating_keys)} rating cols")
    print(f"missing OVR: {missing_ovr}; detail-page failures: {len(failed)}")
    for fl in failed:
        print("  FAIL:", fl)
    if missing_ovr or failed:
        print("WARNING: incomplete data above — investigate before reporting success.")


if __name__ == "__main__":
    main()
