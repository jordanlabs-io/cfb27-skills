#!/usr/bin/env python3
"""Coverage gate for a Lane C menu capture (see references/data-dump.md).

Usage:
  dump_reconcile.py --keep <dedupe.json.keep> --manifests <glob> [<glob> ...]
                    [--frames <framedir>] [--chapters <chapters.json>] [--markdown]

**The gate is a set difference on filenames:**

    survivors (the .keep file)  -  union(every tier-2 batch manifest)  ==  empty

Any survivor not present in a manifest was never handed to a transcription agent.
Non-empty -> exit 1 and name the frames.

This is deliberately NOT a per-category count comparison against chapters.json. Tier-1
classification covers a *subset* of survivors (719 of 1,552 in the 2027-w9 capture), so a
category-keyed assertion is structurally blind to every unclassified survivor — it would
report green over exactly the hole this script exists to catch. chapters.json feeds the
per-category *report* below, which is useful and is not the gate.

Run it after every tier-2 wave, and again before writing the capture's `_index.md`.
`--markdown` emits the coverage ledger table to paste into that file.

The failure this exists to prevent: the 2027-w9 dump transcribed 374 of its frames,
left 301 of 367 box-score frames unread, and nothing recorded the gap. The vault looked
finished for weeks.
"""
import sys, os, glob, json, re


def read_list(p):
    return {l.strip() for l in open(p) if l.strip()}


def opt(argv, flag, default=None):
    return argv[argv.index(flag) + 1] if flag in argv else default


def multi(argv, flag):
    """Every value after `flag` up to the next --option."""
    if flag not in argv:
        return []
    out = []
    for x in argv[argv.index(flag) + 1:]:
        if x.startswith("--"):
            break
        out.append(x)
    return out


def sec_of(n):
    m = re.search(r"f_(\d+)", n)
    return int(m.group(1)) if m else 0


def main(argv):
    keep_file = opt(argv, "--keep")
    if not keep_file:
        sys.exit("ERROR: --keep <dedupe.json.keep> is required. It is the survivor contract.")
    patterns = multi(argv, "--manifests")
    if not patterns:
        sys.exit("ERROR: --manifests <glob> is required (the tier-2 batch .txt files).")

    survivors = read_list(keep_file)
    manifests = sorted({p for pat in patterns for p in glob.glob(os.path.expanduser(pat))})
    if not manifests:
        sys.exit(f"ERROR: no manifest files matched {patterns}")
    transcribed = set()
    for m in manifests:
        transcribed |= read_list(m)

    never = sorted(survivors - transcribed, key=sec_of)
    extra = sorted(transcribed - survivors, key=sec_of)

    frames_dir = opt(argv, "--frames")
    extracted = len(glob.glob(os.path.join(frames_dir, "f_*.jpg"))) if frames_dir else None

    print(f"survivors (.keep):        {len(survivors)}")
    if extracted is not None:
        print(f"extracted at 1 fps:       {extracted}")
        print(f"dropped as duplicate:     {extracted - len(survivors)}")
    print(f"manifests read:           {len(manifests)}")
    print(f"frames handed to agents:  {len(transcribed)}")
    print(f"NEVER TRANSCRIBED:        {len(never)}")
    if extra:
        print(f"transcribed but not a survivor: {len(extra)} (harmless — extra reads)")

    chapters = opt(argv, "--chapters")
    rows = []
    if chapters and os.path.exists(chapters):
        data = json.load(open(chapters))
        cats = {}
        for r in data:
            c = r["screen_category"]
            d = cats.setdefault(c, [0, 0, 0])
            d[2] += 1
            if r["frame"] in transcribed:
                d[0] += 1
            else:
                d[1] += 1
        rows = sorted(cats.items(), key=lambda kv: -kv[1][2])
        print(f"\nper category (of the {len(data)} tier-1 classified):")
        print(f"  {'category':24} {'transcribed':>11} {'duplicate':>10} {'classified':>11}")
        for c, (t, d, tot) in rows:
            print(f"  {c:24} {t:>11} {d:>10} {tot:>11}")

    if "--markdown" in argv:
        print("\n--- paste into the capture _index.md ---\n")
        print("| | frames |")
        print("| --- | --- |")
        if extracted is not None:
            print(f"| Extracted at 1 fps | **{extracted}** |")
        print(f"| Survived hash dedup | **{len(survivors)}** |")
        print(f"| — handed to transcription agents | {len(transcribed & survivors)} |")
        if extracted is not None:
            print(f"| Dropped as near-duplicate | {extracted - len(survivors)} |")
        print(f"| **Never transcribed** | **{len(never)}** |")
        if rows:
            print("\n| Category | Transcribed | Dropped as duplicate | Classified |")
            print("| --- | --- | --- | --- |")
            for c, (t, d, tot) in rows:
                print(f"| `{c}` | {t} | {d} | {tot} |")

    if never:
        print(f"\nFAIL: {len(never)} survivor(s) never handed to any agent:", file=sys.stderr)
        for f in never[:60]:
            print("  " + f, file=sys.stderr)
        if len(never) > 60:
            print(f"  ... and {len(never)-60} more", file=sys.stderr)
        print("\nBuild a sweep for exactly these frames:", file=sys.stderr)
        print("  dump_batches.py <keep> <outdir> --prefix sweep --exclude <manifests...>",
              file=sys.stderr)
        sys.exit(1)

    print("\nOK: every survivor was handed to a transcription agent.")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    main(sys.argv)
