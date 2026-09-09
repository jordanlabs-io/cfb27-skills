"""Rescore snap_refine.refine_snap against truth_v3 (see calibration-history.md A14/A15).

Usage: score_snap_estimator.py   (needs ~/CFB27-film/2028-rutgers-vs-northwestern/video.mp4)
"""
import csv, os, statistics, sys
SK=os.path.expanduser("~/cfb27-skills/plugins/cfb27/skills/film-room/scripts")
sys.path.insert(0,SK)
import segment as seg, snap_refine
V="/Users/elijah/CFB27-film/2028-rutgers-vs-northwestern/video.mp4"
vw,vh,_=seg.video_info(V); hbox=(0,int(vh*0.88),vw,vh-int(vh*0.88))
rows=list(csv.DictReader(open(os.path.join(os.path.dirname(os.path.abspath(__file__)),"truth_v3.csv"))))
errs=[]
print(f"{'play':>5} {'truth_v3':>9} {'shipped':>9} {'err':>5}  src")
for r in rows:
    t=float(r["truth_v3"])
    s,src,u=snap_refine.refine_snap(V,hbox,float(r["coarse_snap"]))
    errs.append(abs(s-t))
    print(f"{r['play']:>5} {t:>9.2f} {s:>9.2f} {errs[-1]:>5.2f}  {src}")
print("\nmedian=%.3f P90=%.3f within0.3=%d/20"%(statistics.median(errs),sorted(errs)[17],sum(1 for e in errs if e<=0.3)))
