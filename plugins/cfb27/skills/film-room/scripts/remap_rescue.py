import json, os, sys, glob
g = sys.argv[1]
frames = sorted(int(p.split("/")[-1][1:7]) - 1 for p in glob.glob(os.path.join(g, "seg/hud_frames/f*.jpg")))
fixed = skipped = 0
for path in sorted(glob.glob(os.path.join(g, "seg/rescue_json/sheet*.json"))):
    n = int(os.path.basename(path)[5:8])
    chunk = frames[(n-1)*24:n*24]
    rows = json.load(open(path))
    ts = [r.get("t") for r in rows]
    if ts == chunk:
        continue  # already correct
    if len(rows) == len(chunk):
        # positional remap: row i is the i-th frame of this sheet
        for r, t in zip(rows, chunk):
            r["t"] = t
        json.dump(rows, open(path, "w"))
        fixed += 1
    else:
        # constant-offset repair for partial sheets
        offs = {c - t for t, c in zip(ts, chunk) if isinstance(t, int)}
        if len(offs) == 1 and offs != {0}:
            o = offs.pop()
            for r in rows:
                if isinstance(r.get("t"), int):
                    r["t"] += o
            json.dump(rows, open(path, "w"))
            fixed += 1
        elif rows:
            skipped += 1
            print(f"sheet{n:03d}: {len(rows)} rows, cannot remap (chunk {len(chunk)})")
print(f"fixed {fixed}, unfixable {skipped}")
