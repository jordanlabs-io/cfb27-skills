#!/usr/bin/env python3
"""Archive-backlog gate for the film-room workspace (SKILL.md step 0 / step 11).

Scans ~/CFB27-film/<game-slug>/ dirs and exits non-zero if any of them still
owes an archive pass:

  - no drive_upload.json                          -> NEVER ARCHIVED
  - drive_upload.json parses to an error payload  -> ARCHIVE FAILED (the
    2027-rutgers-vs-vanderbilt case: a gws 401 body was saved as the marker,
    so mere file-existence reads as "archived" when nothing was uploaded)
  - drive_upload.json lacks any md5Checksum entry -> ARCHIVE UNVERIFIED
  - archived, but bulky regenerables still on disk (originals, video.mp4,
    audio.wav, retranscode/, seg/hud_frames/)     -> CLEANUP OWED

Usage: archive_audit.py [FILM_ROOT]          (default ~/CFB27-film)
Exit 0 = clean. Exit 1 = backlog listed on stdout; run step 11 before ingesting.
"""
import json
import re
import sys
from pathlib import Path

SLUG_RE = re.compile(r"^\d{4}-")
# Bulky regenerables step 11 deletes after a verified upload.
LEFTOVER_GLOBS = [
    "ScreenRecording*",
    "*.MP4",
    "*.mov",
    "video.mp4",
    "audio.wav",
]
LEFTOVER_DIRS = ["retranscode", "seg/hud_frames"]


def du_bytes(path: Path) -> int:
    if path.is_file():
        return path.stat().st_size
    return sum(f.stat().st_size for f in path.rglob("*") if f.is_file())


def upload_ok(marker: Path):
    """Return (ok, reason). ok=True only for a parseable record set with md5s."""
    try:
        raw = marker.read_text()
    except OSError as e:
        return False, f"unreadable drive_upload.json ({e.__class__.__name__})"
    # Some markers were written with gws log lines prefixed before the JSON body.
    start = min((i for i in (raw.find("{"), raw.find("[")) if i >= 0), default=-1)
    if start < 0:
        return False, "drive_upload.json contains no JSON"
    try:
        data = json.loads(raw[start:])
    except json.JSONDecodeError:
        return False, "drive_upload.json is not parseable JSON"
    if isinstance(data, dict) and data.get("nothing_to_archive"):
        return True, ""
    entries = data if isinstance(data, list) else [data]
    for ent in entries:
        if isinstance(ent, dict) and "error" in ent:
            code = ent["error"].get("code") if isinstance(ent["error"], dict) else ""
            return False, f"drive_upload.json is an ERROR payload (code {code}) — upload never happened"
    # Historical marker shapes use md5/md5Checksum/local_md5, under files/uploads/top-level.
    blob = json.dumps(data)
    if not any(k in blob for k in ('"md5"', '"md5Checksum"', '"local_md5"')):
        return False, "drive_upload.json has no md5 entries — upload unverified"
    return True, ""


def audit(root: Path):
    problems = []
    reclaim = 0
    for d in sorted(root.iterdir()):
        if not d.is_dir() or not SLUG_RE.match(d.name):
            continue
        marker = d / "drive_upload.json"
        if not marker.exists():
            sz = du_bytes(d)
            reclaim += sz
            problems.append((d.name, f"NEVER ARCHIVED ({sz / 1e9:.1f} GB on disk)"))
            continue
        ok, reason = upload_ok(marker)
        if not ok:
            sz = du_bytes(d)
            reclaim += sz
            problems.append((d.name, f"{reason} ({sz / 1e9:.1f} GB on disk)"))
            continue
        # Archived for real — check for cleanup step 11 should have done.
        leftovers = sorted({p for g in LEFTOVER_GLOBS for p in d.glob(g) if p.is_file()})
        for sub in LEFTOVER_DIRS:
            p = d / sub
            if p.is_dir():
                leftovers.append(p)
        if leftovers:
            sz = sum(du_bytes(p) for p in leftovers)
            reclaim += sz
            names = ", ".join(p.name for p in leftovers[:6])
            problems.append((d.name, f"archived but cleanup owed: {names} ({sz / 1e9:.1f} GB deletable)"))
    return problems, reclaim


def main():
    root = Path(sys.argv[1]).expanduser() if len(sys.argv) > 1 else Path("~/CFB27-film").expanduser()
    if not root.is_dir():
        print(f"archive_audit: {root} does not exist — nothing to audit")
        return 0
    problems, reclaim = audit(root)
    if not problems:
        print(f"archive_audit: clean — every game dir in {root} is archived and swept")
        return 0
    print(f"archive_audit: {len(problems)} game dir(s) owe an archive/cleanup pass "
          f"(~{reclaim / 1e9:.1f} GB reclaimable):")
    for name, reason in problems:
        print(f"  {name}: {reason}")
    print("Run SKILL.md step 11 against each before ingesting anything new.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
