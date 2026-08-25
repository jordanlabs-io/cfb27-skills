#!/usr/bin/env python3
"""Step-11 archive sweep: upload originals to Drive (md5-verified), then clean up.

Drains the backlog archive_audit.py reports. Per flagged game dir:
  1. Candidates = original recordings (ScreenRecording*, *.MP4/*.mov/*.mp4
     excluding video.mp4/audio.wav); if none exist, video.mp4 is the archival copy.
  2. Skip any candidate whose name+md5 already appears verified in drive_upload.json.
  3. Upload the rest via gws; compare Drive's md5Checksum to local `md5 -q`.
     NOTHING is deleted unless its upload verified.
  4. Rewrite drive_upload.json (uniform shape: {"folder_id", "files":[{name,
     drive_name, id, size, md5, verified: true}], "swept": date}).
  5. Delete bulky regenerables: verified originals, video.mp4, audio.wav,
     retranscode/, seg/hud_frames/, seg_new/hud_frames/.

Dirs with nothing bulky to archive get {"nothing_to_archive": true} so the
audit stops flagging them.

Usage: archive_sweep.py [FILM_ROOT] [--dry-run] [--only SLUG]
Exit 0 = every processed dir finished clean; non-zero otherwise.
"""
import argparse
import datetime
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

FOLDER_ID = "1RHufk2iZPnoPACIue0LYGWW4MPzcnYoO"
FOLDER_NAME = "CFB27 Film Room"
SLUG_RE = re.compile(r"^\d{4}-")
ORIG_GLOBS = ["ScreenRecording*", "*.MP4", "*.mov", "*.mp4"]
NEVER_CANDIDATES = {"video.mp4", "audio.wav"}  # regenerables, not originals
CLEANUP_FILES = ["video.mp4", "audio.wav"]
CLEANUP_DIRS = ["retranscode", "seg/hud_frames", "seg_new/hud_frames"]


def sh(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


def local_md5(path: Path) -> str:
    r = sh(["md5", "-q", str(path)])
    if r.returncode != 0:
        raise RuntimeError(f"md5 failed for {path}: {r.stderr.strip()}")
    return r.stdout.strip()


def load_marker(d: Path):
    marker = d / "drive_upload.json"
    if not marker.exists():
        return {}
    raw = marker.read_text()
    start = min((i for i in (raw.find("{"), raw.find("[")) if i >= 0), default=-1)
    if start < 0:
        return {}
    try:
        data = json.loads(raw[start:])
    except json.JSONDecodeError:
        return {}
    if isinstance(data, dict) and "error" in data:
        return {}
    return data if isinstance(data, dict) else {"files": data}


def verified_names(marker: dict):
    """Names already uploaded WITH an md5 recorded, across historical marker shapes."""
    out = {}
    entries = marker.get("files") or marker.get("uploads") or []
    if not entries and ("local_md5" in marker or "md5" in marker):
        entries = [marker]
    for e in entries:
        if not isinstance(e, dict):
            continue
        md5 = e.get("md5") or e.get("md5Checksum") or e.get("local_md5")
        if not md5:
            continue
        # local_source (upload_only.sh shape) holds the LOCAL path; "name" in
        # that shape is the Drive-side rename and never matches a local file.
        for key in ("file", "name", "local_source"):
            if e.get(key):
                out[os.path.basename(str(e[key]))] = md5
    return out


def candidates(d: Path):
    """Returns (upload candidates, are_originals).

    are_originals=True (licenses deleting video.mp4 as a regenerable transcode)
    ONLY for true capture files: ScreenRecording*, *.MP4, *.mov. Stray lowercase
    .mp4 helpers (audio_src.mp4 etc.) are uploaded but do NOT license it — in a
    data-dump dir video.mp4 IS the original VOD and must be uploaded itself.
    """
    strict = sorted({p for g in ("ScreenRecording*", "*.MP4", "*.mov") for p in d.glob(g)
                     if p.is_file() and p.name not in NEVER_CANDIDATES})
    extra = sorted({p for p in d.glob("*.mp4")
                    if p.is_file() and p.name not in NEVER_CANDIDATES and p not in strict})
    if strict:
        return strict + extra, True
    v = d / "video.mp4"
    return (extra + ([v] if v.exists() else []), False)


def upload(path: Path, drive_name: str):
    # gws refuses --upload paths outside the cwd -> run from the file's dir.
    meta = json.dumps({"name": drive_name, "parents": [FOLDER_ID]})
    r = sh(["gws", "drive", "files", "create", "--upload", path.name,
            "--json", meta, "--params", '{"fields":"id,name,size,md5Checksum"}'],
           cwd=str(path.parent))
    raw = r.stdout
    start = raw.find("{")
    if r.returncode != 0 or start < 0:
        raise RuntimeError(f"gws upload failed: {r.stderr.strip()[:300] or raw[:300]}")
    resp = json.loads(raw[start:])
    if "error" in resp:
        raise RuntimeError(f"gws upload error: {resp['error']}")
    return resp


def sweep_dir(d: Path, dry: bool, delete_allowed: bool = False):
    slug = d.name
    marker = load_marker(d)
    known = verified_names(marker)
    cands, are_originals = candidates(d)
    records, failures = [], []

    if not cands and not any((d / f).exists() for f in CLEANUP_FILES) \
            and not any((d / s).is_dir() for s in CLEANUP_DIRS):
        if not known and not marker.get("nothing_to_archive"):
            print(f"[{slug}] nothing bulky to archive — writing marker")
            if not dry:
                (d / "drive_upload.json").write_text(json.dumps(
                    {"nothing_to_archive": True, "folder_id": FOLDER_ID,
                     "swept": str(datetime.date.today())}, indent=1))
        return True

    for p in cands:
        lmd5 = local_md5(p)
        if known.get(p.name) == lmd5:
            print(f"[{slug}] {p.name}: already uploaded+verified — will delete")
            records.append({"name": p.name, "md5": lmd5, "verified": True,
                            "note": "verified in prior marker"})
            continue
        drive_name = f"{slug}.mp4" if p.name == "video.mp4" else p.name
        size_gb = p.stat().st_size / 1e9
        print(f"[{slug}] uploading {p.name} ({size_gb:.1f} GB) as {drive_name}...")
        if dry:
            continue
        try:
            resp = upload(p, drive_name)
        except (RuntimeError, json.JSONDecodeError) as e:
            print(f"[{slug}] UPLOAD FAILED for {p.name}: {e}")
            failures.append(p.name)
            continue
        rmd5 = resp.get("md5Checksum", "")
        if rmd5 != lmd5:
            print(f"[{slug}] MD5 MISMATCH {p.name}: local {lmd5} drive {rmd5} — NOT deleting")
            failures.append(p.name)
            continue
        print(f"[{slug}] {p.name}: verified (drive id {resp['id']})")
        records.append({"name": p.name, "drive_name": drive_name, "id": resp["id"],
                        "size": p.stat().st_size, "md5": lmd5, "verified": True})

    if dry:
        return not failures
    if failures:
        print(f"[{slug}] {len(failures)} upload(s) failed — keeping ALL local files")
        return False

    # Rewrite the marker only when THIS run uploaded something new — a dir
    # whose files were all verified by a prior marker keeps that marker
    # (it carries drive ids this run never saw).
    if any("id" in r for r in records):
        (d / "drive_upload.json").write_text(json.dumps(
            {"folder": FOLDER_NAME, "folder_id": FOLDER_ID,
             "swept": str(datetime.date.today()), "files": records}, indent=1))

    # Upload and deletion are intentionally separate authorities. A verified
    # Drive copy preserves bytes, but only live vault parity licenses removing
    # the local source or transcode.
    if not delete_allowed:
        print(f"[{slug}] VAULT GATE BLOCKED — upload preserved; deleting NOTHING")
        return False

    # Delete: verified candidates + regenerables. video.mp4 goes only if it was
    # itself verified or the verified set covered the originals.
    for p in cands:
        if any(r["name"] == p.name for r in records):
            p.unlink()
            print(f"[{slug}] deleted {p.name}")
    for f in CLEANUP_FILES:
        p = d / f
        if p.exists() and (are_originals or f != "video.mp4"):
            p.unlink()
            print(f"[{slug}] deleted {f}")
    for s in CLEANUP_DIRS:
        p = d / s
        if p.is_dir():
            shutil.rmtree(p)
            print(f"[{slug}] deleted {s}/")
    return True


def corpus_delete_ready(states) -> bool:
    """Deletion stays frozen until every discovered game/capture is complete."""
    states = list(states)
    return bool(states) and all(s.deletion_status == "delete_ready" for s in states)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("film_root", nargs="?", default="~/CFB27-film")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--only")
    parser.add_argument("--vault-root", default="~/CFB27")
    parser.add_argument("--ledger")
    args = parser.parse_args()
    dry = args.dry_run
    only = args.only
    root = Path(args.film_root).expanduser().resolve()
    vault_root = Path(args.vault_root).expanduser().resolve()
    ledger = Path(args.ledger).expanduser().resolve() if args.ledger else (
        vault_root / "operations" / "film-ingest-ledger.csv")

    sys.path.insert(0, str(Path(__file__).parent))
    from archive_audit import audit
    from reconcile_film import reconcile
    states = reconcile(root, vault_root, ledger)
    reconciled = {r.workspace_slug: r for r in states if r.workspace_slug}
    corpus_ready = corpus_delete_ready(states)
    problems, _ = audit(root, vault_root, ledger)
    ok = True
    for name, reason in problems:
        if only and name != only:
            continue
        target = root / name
        if not target.is_dir():
            print(f"=== {name}: {reason} — not a workspace; deleting NOTHING")
            ok = False
            continue
        print(f"=== {name}: {reason}")
        try:
            state = reconciled.get(name)
            can_delete = bool(
                corpus_ready and state and state.deletion_status == "delete_ready")
            if state and state.deletion_status == "delete_ready" and not corpus_ready:
                print(f"[{name}] GLOBAL FILM FREEZE — another source is incomplete")
            ok = sweep_dir(target, dry, delete_allowed=can_delete) and ok
        except Exception as e:  # keep sweeping other dirs
            print(f"[{name}] SWEEP ERROR: {e}")
            ok = False
    print("sweep complete" + (" (dry run)" if dry else "") + ("" if ok else " — WITH FAILURES"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
