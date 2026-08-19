import json, os, sys, glob
g = sys.argv[1]
fdir = os.path.join(g, "seg/hud_frames")
frames = sorted(int(p.split("/")[-1][1:7]) - 1 for p in glob.glob(os.path.join(fdir, "f*.jpg")))
chunks = {i//24 + 1: set(frames[i:i+24]) for i in range(0, len(frames), 24)}
dropped = kept = 0
for path in sorted(glob.glob(os.path.join(g, "seg/rescue_json/sheet*.json"))):
    n = int(os.path.basename(path)[5:8])
    valid = chunks.get(n, set())
    try:
        rows = json.load(open(path))
    except Exception as e:
        print(f"BAD JSON {path}: {e}"); continue
    good = [r for r in rows if isinstance(r, dict) and isinstance(r.get("t"), int) and r["t"] in valid]
    d = len(rows) - len(good)
    if d:
        print(f"sheet{n:03d}: dropped {d} fabricated/out-of-range rows (kept {len(good)})")
        json.dump(good, open(path, "w"))
    dropped += d; kept += len(good)
print(f"TOTAL kept {kept}, dropped {dropped}")
