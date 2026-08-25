#!/usr/bin/env python3
"""Archive-backlog gate for the film-room workspace (SKILL.md step 0 / step 11).

Scans ~/CFB27-film/<game-slug>/ dirs and exits non-zero if any of them still
owes reconciliation, preservation, or cleanup. Findings are grouped so a
missing vault artifact cannot be mistaken for an upload problem:

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
import argparse
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

CATEGORY_ORDER = (
    "LOOSE RECORDINGS",
    "UNPROCESSED GAMES",
    "MISSING REPORTS",
    "MISSING VAULT CSVs",
    "MISMATCHED CSVs",
    "INVALID VALIDATION RECEIPTS",
    "CAPTURE COVERAGE FAILURES",
    "ARCHIVE FAILURES",
    "ARCHIVE CLEANUP OWED",
)


def finding(category: str, detail: str) -> str:
    return f"[{category}] {detail}"


def split_finding(reason: str) -> tuple[str, str]:
    if reason.startswith("[") and "] " in reason:
        category, detail = reason[1:].split("] ", 1)
        return category, detail
    return "ARCHIVE FAILURES", reason


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


def audit(root: Path, vault_root: Path | None = None, ledger: Path | None = None):
    problem_map = {}
    reclaim = 0
    for d in sorted(root.iterdir()):
        if not d.is_dir() or not SLUG_RE.match(d.name):
            continue
        marker = d / "drive_upload.json"
        if not marker.exists():
            sz = du_bytes(d)
            reclaim += sz
            problem_map.setdefault(d.name, []).append(finding(
                "ARCHIVE FAILURES", f"NEVER ARCHIVED ({sz / 1e9:.1f} GB on disk)"))
            continue
        ok, reason = upload_ok(marker)
        if not ok:
            sz = du_bytes(d)
            reclaim += sz
            problem_map.setdefault(d.name, []).append(finding(
                "ARCHIVE FAILURES", f"{reason} ({sz / 1e9:.1f} GB on disk)"))
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
            problem_map.setdefault(d.name, []).append(finding(
                "ARCHIVE CLEANUP OWED",
                f"archived but cleanup owed: {names} ({sz / 1e9:.1f} GB deletable)"))

    # Vault parity is a separate gate from Drive preservation. Keep it in the
    # same audit so archive_sweep can never delete media whose report/CSV is
    # missing, mismatched, or validated against an older chart hash.
    if vault_root:
        sys.path.insert(0, str(Path(__file__).parent))
        from reconcile_film import reconcile
        ledger = ledger or vault_root / "operations" / "film-ingest-ledger.csv"
        for result in reconcile(root, vault_root, ledger):
            key = result.workspace_slug or result.source_name
            if result.deletion_status == "delete_ready":
                continue
            workspace_exists = bool(result.workspace_slug and
                                    (root / result.workspace_slug).is_dir())
            if not workspace_exists:
                problem_map.setdefault(key, []).append(finding(
                    "LOOSE RECORDINGS",
                    "unregistered root media; finish full vault output before deletion"))
                continue
            if result.source_kind == "capture":
                problem_map.setdefault(key, []).append(finding(
                    "CAPTURE COVERAGE FAILURES",
                    f"{result.content_status}; capture index/zero-untranscribed gate not satisfied"))
                continue
            if result.content_status == "unprocessed":
                problem_map.setdefault(key, []).append(finding(
                    "UNPROCESSED GAMES", "plays_charted.csv is missing"))
            note_exists = bool(result.note_path and (vault_root / result.note_path).is_file())
            if not note_exists:
                problem_map.setdefault(key, []).append(finding(
                    "MISSING REPORTS", result.note_path or "game-note mapping missing"))
            if result.workspace_sha256 and not result.vault_sha256:
                problem_map.setdefault(key, []).append(finding(
                    "MISSING VAULT CSVs", "mapped vault play CSV is missing"))
            elif (result.workspace_sha256 and result.vault_sha256 and
                  result.workspace_sha256 != result.vault_sha256):
                problem_map.setdefault(key, []).append(finding(
                    "MISMATCHED CSVs",
                    f"workspace {result.workspace_sha256[:12]} != vault {result.vault_sha256[:12]}"))
            if result.validation_status != "pass" and result.workspace_sha256:
                problem_map.setdefault(key, []).append(finding(
                    "INVALID VALIDATION RECEIPTS", result.validation_status))

    problems = [(name, "; ".join(reasons))
                for name, reasons in sorted(problem_map.items())]
    return problems, reclaim


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("film_root", nargs="?", default="~/CFB27-film")
    parser.add_argument("--vault-root", default="~/CFB27")
    parser.add_argument("--ledger")
    args = parser.parse_args()
    root = Path(args.film_root).expanduser().resolve()
    vault_root = Path(args.vault_root).expanduser().resolve()
    ledger = Path(args.ledger).expanduser().resolve() if args.ledger else None
    if not root.is_dir():
        print(f"archive_audit: {root} does not exist — nothing to audit")
        return 0
    problems, reclaim = audit(root, vault_root, ledger)
    if not problems:
        print(f"archive_audit: clean — every source in {root} is vault-complete, "
              "archived, and swept")
        return 0
    print(f"archive_audit: {len(problems)} source(s) owe reconciliation/archive work "
          f"(~{reclaim / 1e9:.1f} GB reclaimable):")
    grouped = {category: [] for category in CATEGORY_ORDER}
    for name, joined in problems:
        for reason in joined.split("; "):
            category, detail = split_finding(reason)
            grouped.setdefault(category, []).append((name, detail))
    for category in CATEGORY_ORDER:
        entries = grouped.get(category, [])
        if not entries:
            continue
        print(f"\n{category} ({len(entries)}):")
        for name, detail in entries:
            print(f"  {name}: {detail}")
    print("Run SKILL.md step 11 against each before ingesting anything new.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
