#!/usr/bin/env python3
"""Verify playbook rows (category + set + play name) against the local CFB Labs play DB.

Matching is exact on the three fields TOGETHER after normalisation (lower-case, punctuation
and underscores -> spaces, whitespace collapsed). There is no fuzzy matching in the verdict;
"closest names" are printed only as suggestions on rows that did not verify.

Status per row:
  verified       category + set + play all exist together
  name-mismatch  the set exists, the play is not in it (closest 3 play names in that set listed)
  set-mismatch   the set does not exist as given, but the play name exists under other sets
  not-in-db      neither; nearest set names listed as a hint

Usage:
  verify_plays.py ROWS.csv|json --db cfblabs-plays.json [--out results.csv]
                  [--category-col category] [--set-col set] [--play-col play_name]
                  [--side offense|defense] [--report-only]
  verify_plays.py --selftest --db cfblabs-plays.json

Exit code is non-zero if any row is not verified (or the selftest fails), unless --report-only.
"""
import argparse, csv, difflib, json, random, re, sys
from collections import defaultdict

STATUSES = ["verified", "name-mismatch", "set-mismatch", "not-in-db"]


def norm(s):
    s = re.sub(r"[^0-9a-z]+", " ", str(s if s is not None else "").lower())
    return " ".join(s.split())


class DB:
    def __init__(self, path, side=None):
        rows = json.load(open(path, encoding="utf-8"))
        if side:
            rows = [r for r in rows if r["side"] == side]
        self.rows = rows
        self.keys = {}                      # (cat,set,play) -> row
        self.sets = defaultdict(dict)       # (cat,set) -> {norm play: display play}
        self.set_disp = {}                  # (cat,set) -> "CATEGORY / SET"
        self.plays = defaultdict(list)      # norm play -> [(cat,set)]
        for r in rows:
            c, s, p = norm(r["category"]), norm(r["set"]), norm(r["play_name"])
            self.keys[(c, s, p)] = r
            self.sets[(c, s)][p] = r["play_name"]
            self.set_disp[(c, s)] = f'{r["category"]} / {r["set"]}'
            self.plays[p].append((c, s))

    def check(self, cat, st, play):
        c, s, p = norm(cat), norm(st), norm(play)
        r = self.keys.get((c, s, p))
        if r:
            return "verified", "", r
        if (c, s) in self.sets:
            near = difflib.get_close_matches(p, list(self.sets[(c, s)]), n=3, cutoff=0.0)
            other = [self.set_disp[k] for k in self.plays.get(p, [])]
            d = "closest in set: " + "; ".join(self.sets[(c, s)][n] for n in near)
            if other:
                d += " | play also exists under: " + "; ".join(other[:5]) + (f" (+{len(other) - 5} more)" if len(other) > 5 else "")
            return "name-mismatch", d, None
        if p in self.plays:
            loc = [self.set_disp[k] for k in self.plays[p]]
            return "set-mismatch", "play exists under: " + "; ".join(loc[:10]) + (f" (+{len(loc) - 10} more)" if len(loc) > 10 else ""), None
        near = difflib.get_close_matches(f"{c} {s}", [f"{a} {b}" for a, b in self.sets], n=3, cutoff=0.0)
        disp = {f"{a} {b}": self.set_disp[(a, b)] for a, b in self.sets}
        return "not-in-db", "nearest sets: " + "; ".join(disp[n] for n in near), None


def read_rows(path):
    if path.lower().endswith(".json"):
        data = json.load(open(path, encoding="utf-8"))
        return data if isinstance(data, list) else data["rows"]
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def run(rows, db, cat_col, set_col, play_col):
    if not rows:
        raise SystemExit("no input rows")
    cols = rows[0].keys()
    if cat_col is None:
        cat_col = "category" if "category" in cols else "formation" if "formation" in cols else None
    for name, c in (("category", cat_col), ("set", set_col), ("play", play_col)):
        if c not in cols:
            raise SystemExit(f"{name} column {c!r} not found in input columns {list(cols)}")
    out = []
    for r in rows:
        st, detail, hit = db.check(r[cat_col], r[set_col], r[play_col])
        o = dict(r)
        o.update({"status": st, "detail": detail,
                  "db_side": hit["side"] if hit else "", "db_art_url": (hit or {}).get("art_url") or ""})
        out.append(o)
    return out


def selftest(dbpath):
    db = DB(dbpath)
    rnd = random.Random(27)
    rows = sorted(db.rows, key=lambda r: (r["side"], r["category"], r["set"], r["play_name"]))
    off = rnd.sample([r for r in rows if r["side"] == "offense"], 4)
    de = rnd.sample([r for r in rows if r["side"] == "defense"], 4)
    cases = []
    for r in (off[0], de[0]):
        cases.append((r["category"], r["set"], r["play_name"], "verified"))
    r = off[1]  # mangled but identical after normalisation
    cases.append((r["category"].lower(), "  " + r["set"].replace(" ", "_") + " ", r["play_name"].lower().replace(" ", "_"), "verified"))
    r = de[1]
    cases.append((r["category"], r["set"], r["play_name"].title() + ".", "verified"))
    r = off[2]
    cases.append((r["category"], r["set"], "ZZ NOT A REAL PLAY", "name-mismatch"))
    r = de[2]
    cases.append((r["category"], r["set"], "ZZ NOT A REAL PLAY", "name-mismatch"))
    # real play under a set that does not exist -> set-mismatch (pick a play name unique to one set)
    uniq = [r for r in rows if len(db.plays[norm(r["play_name"])]) == 1]
    r = uniq[len(uniq) // 3]
    cases.append((r["category"], "ZZ NO SUCH SET", r["play_name"], "set-mismatch"))
    r = de[3]
    cases.append(("ZZ NO SUCH CATEGORY", "ZZ NO SUCH SET", "ZZ NOT A REAL PLAY", "not-in-db"))
    bad = 0
    for cat, st, pl, want in cases:
        got, detail, _ = db.check(cat, st, pl)
        ok = got == want
        bad += not ok
        print(f'{"ok  " if ok else "FAIL"} want={want:<13} got={got:<13} {cat} / {st.strip()} / {pl}  {detail[:90]}')
    print(f"selftest: {len(cases) - bad}/{len(cases)} passed")
    return 1 if bad else 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("rows", nargs="?")
    ap.add_argument("--db", required=True)
    ap.add_argument("--out")
    ap.add_argument("--category-col", default=None, help="default: 'category', else 'formation'")
    ap.add_argument("--set-col", default="set")
    ap.add_argument("--play-col", default="play_name")
    ap.add_argument("--side", choices=["offense", "defense"])
    ap.add_argument("--report-only", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest(a.db)
    if not a.rows:
        ap.error("ROWS file required (or --selftest)")
    db = DB(a.db, a.side)
    res = run(read_rows(a.rows), db, a.category_col, a.set_col, a.play_col)
    out = a.out or re.sub(r"\.(csv|json)$", "", a.rows) + ".verified.csv"
    with open(out, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(res[0].keys()))
        w.writeheader()
        w.writerows(res)
    counts = {s: sum(1 for r in res if r["status"] == s) for s in STATUSES}
    print("  ".join(f"{s}={n}" for s, n in counts.items()), f"(rows={len(res)})  -> {out}")
    for r in res:
        if r["status"] != "verified":
            print(f'  {r["status"]}: {r.get(a.category_col or "category", r.get("formation", ""))} / {r[a.set_col]} / {r[a.play_col]}  [{r["detail"]}]')
    return 0 if (a.report_only or counts["verified"] == len(res)) else 1


if __name__ == "__main__":
    sys.exit(main())
