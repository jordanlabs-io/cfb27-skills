#!/usr/bin/env python3
"""Dump the complete College Football 27 play database (offense AND defense) from cfblabs.com.

Access path (verified 2026-09-29): the /plays index page lists every category and
sub-formation as <a href="/plays/<CATEGORY>[/<SET>]">. Each set page is server-rendered
Next.js; the play list is in the __NEXT_DATA__ JSON (props.pageProps.plays) together with
pageProps.playType ("offense"/"defense"), and the page HTML carries each play's art <img>.

Standard library only. Polite (single thread, delay, backoff), resumable (raw pages are
cached gzip'd under --cache-dir; a re-run refetches nothing that is cached).

Usage:
  dump_cfblabs.py --out-dir ~/CFB27/playbook/db --cache-dir /tmp/cfblabs-cache
"""
import argparse, csv, gzip, hashlib, html, json, os, re, sys, time
import urllib.error, urllib.parse, urllib.request

BASE = "https://www.cfblabs.com"
UA = "cfb27-vault-playdb/1.0 (personal offline reference copy of the play list)"
NEXT_RE = re.compile(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', re.S)
ITEM_RE = re.compile(r'<a class="cfb-playitem" href="([^"]+)">(.*?)</a>', re.S)
IMG_RE = re.compile(r'<img src="([^"]+)"')
COUNT_RE = re.compile(r'(\d[\d,]*) plays run out of')
FLAT = ["side", "category", "set", "play_name", "play_type", "art_url", "source_url"]


class Fetcher:
    def __init__(self, cache_dir, delay, retries=4):
        self.cache_dir, self.delay, self.retries = cache_dir, delay, retries
        self.live = 0
        os.makedirs(cache_dir, exist_ok=True)

    def _path(self, url):
        return os.path.join(self.cache_dir, hashlib.sha1(url.encode()).hexdigest() + ".html.gz")

    def get(self, url):
        p = self._path(url)
        if os.path.exists(p):
            with gzip.open(p, "rt", encoding="utf-8") as f:
                return f.read()
        last = None
        for i in range(self.retries):
            try:
                req = urllib.request.Request(url, headers={"User-Agent": UA})
                with urllib.request.urlopen(req, timeout=40) as r:
                    body = r.read().decode("utf-8")
                with gzip.open(p + ".tmp", "wt", encoding="utf-8") as f:
                    f.write(body)
                os.replace(p + ".tmp", p)
                self.live += 1
                time.sleep(self.delay)
                return body
            except urllib.error.HTTPError as e:
                last = e
                if e.code == 404:
                    raise
            except Exception as e:
                last = e
            time.sleep(2 * (2 ** i))
        raise RuntimeError(f"giving up on {url}: {last}")


def list_sets(index_html):
    hrefs = sorted(set(re.findall(r'href="(/plays/[^"]*)"', index_html)))
    cats = [h for h in hrefs if h.count("/") == 2]
    sets = [h for h in hrefs if h.count("/") == 3]
    return cats, sets


def parse_set_page(page, url):
    m = NEXT_RE.search(page)
    if not m:
        raise ValueError("no __NEXT_DATA__")
    pp = json.loads(m.group(1))["props"]["pageProps"]
    side = pp["playType"]
    art = {}  # decoded play name (from anchor href) -> art url
    for href, inner in ITEM_RE.findall(page):
        name = urllib.parse.unquote(html.unescape(href).split("/")[-1])
        im = IMG_RE.search(inner)
        if im:
            art[name] = html.unescape(im.group(1))
    claimed = COUNT_RE.search(page)
    recs = []
    for p in pp["plays"]:
        name = p["play_name"]
        a = art.get(name)
        if a:
            a = a.replace("f_auto,q_auto,w_320/", "f_auto,q_auto/")  # thumbnail -> full size
        extra = {k: v for k, v in p.items() if k not in ("category", "sub_category", "play_name")}
        if a and "'" in a.rsplit("/", 1)[-1]:
            # The page's own <img> URL 404s for names with an apostrophe (e.g. "PA SHOT GO'S");
            # the CDN file stores the apostrophe as "_" (verified 200). Record that we corrected it.
            head, tail = a.rsplit("/", 1)
            a = head + "/" + tail.replace("'", "_")
            extra["art_url_note"] = "page URL 404s; apostrophe replaced with underscore (verified 200)"
        recs.append({
            "side": side, "category": p["category"], "set": p["sub_category"],
            "play_name": name, "play_type": side,
            "art_url": a, "source_url": url,
            "extra": extra,
        })
    return side, pp["category"], pp["subCategory"], recs, (int(claimed.group(1).replace(",", "")) if claimed else None)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out-dir", required=True, help="writes cfblabs-plays.json and cfblabs-plays.csv here")
    ap.add_argument("--cache-dir", default=os.path.expanduser("~/.cache/cfblabs-plays"))
    ap.add_argument("--delay", type=float, default=0.3, help="seconds between live requests")
    ap.add_argument("--limit", type=int, default=0, help="only fetch the first N sets (testing)")
    a = ap.parse_args()

    f = Fetcher(a.cache_dir, a.delay)
    cats, sets = list_sets(f.get(BASE + "/plays"))
    if a.limit:
        sets = sets[:a.limit]
    print(f"index: {len(cats)} category links, {len(sets)} set links", file=sys.stderr)

    rows, fails, warns = [], [], []
    for i, path in enumerate(sets, 1):
        url = BASE + path
        try:
            side, cat, sub, recs, claimed = parse_set_page(f.get(url), url)
        except Exception as e:
            fails.append((path, str(e)))
            print(f"FAIL {path}: {e}", file=sys.stderr)
            continue
        if claimed is not None and claimed != len(recs):
            warns.append(f"{path}: page says {claimed} plays, parsed {len(recs)}")
        rows.extend(recs)
        if i % 50 == 0:
            print(f"{i}/{len(sets)} sets, {len(rows)} plays ({f.live} live fetches)", file=sys.stderr)

    seen, dups = {}, 0
    for r in rows:
        k = (r["side"], r["category"], r["set"], r["play_name"])
        if k in seen:
            dups += 1
            warns.append("duplicate key " + " / ".join(k))
        seen[k] = r
    rows = sorted(seen.values(), key=lambda r: (r["side"], r["category"], r["set"], r["play_name"]))

    os.makedirs(a.out_dir, exist_ok=True)
    with open(os.path.join(a.out_dir, "cfblabs-plays.json"), "w", encoding="utf-8") as fh:
        json.dump(rows, fh, ensure_ascii=False, indent=1)
        fh.write("\n")
    with open(os.path.join(a.out_dir, "cfblabs-plays.csv"), "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FLAT, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)

    print("\n== summary ==")
    for side in sorted({r["side"] for r in rows}):
        rs = [r for r in rows if r["side"] == side]
        n_art = sum(1 for r in rs if r["art_url"])
        print(f"{side}: {len(rs)} plays, {len({(r['category'], r['set']) for r in rs})} sets, "
              f"{len({r['category'] for r in rs})} categories, {n_art} with art url")
    print(f"total: {len(rows)} plays, {len({(r['side'], r['category'], r['set']) for r in rows})} sets, "
          f"{len({(r['side'], r['category']) for r in rows})} categories; "
          f"live fetches this run: {f.live}; failures: {len(fails)}; duplicate keys collapsed: {dups}")
    for w_ in warns:
        print("WARN", w_)
    for p, e in fails:
        print("FAIL", p, e)
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
