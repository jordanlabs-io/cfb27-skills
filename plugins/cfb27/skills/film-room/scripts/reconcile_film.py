#!/usr/bin/env python3
"""Reconcile local CFB27 film sources against canonical dynasty-vault outputs.

This is the deletion-authority gate for film-room. A Drive receipt proves that
the source bytes are preserved; it does not prove that the game made it into
the vault. Deletion is allowed only when this script reports ``delete_ready``.

Usage:
  reconcile_film.py [FILM_ROOT] [--vault-root PATH] [--ledger PATH]
                    [--write-ledger] [--json]
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from dataclasses import dataclass, asdict
from pathlib import Path


GAME_RE = re.compile(r"^\d{4}-")
MEDIA_SUFFIXES = {".mov", ".mp4", ".mkv"}
NON_GAME_DIRS = {"2027-w9-datadump", "2027-w10-datadump",
                 "2027-bowlweek1-datadump", "2027-eoy-screens"}
ALIASES = {
    "2026-osu-umd-calibration": ("oregon-state", "2026-osu-vs-umd"),
    "2027-vand-vs-ari": ("north-carolina", "2027-vanderbilt-vs-arizona"),
}
LOOSE_MEDIA = {
    "NW at WVU.mov": ("2027-northwestern-vs-west-virginia", "12",
                       "Northwestern at West Virginia"),
    "AZ at Baylor '27.mov": ("2027-arizona-vs-baylor", "12",
                              "Arizona at Baylor"),
    "UMD at Vandy '27.mov": ("2027-maryland-vs-vanderbilt", "12",
                              "Maryland at Vanderbilt"),
    "UMD at Rutgers '27.mov": ("2027-maryland-vs-rutgers", "13",
                                "Maryland at Rutgers"),
}
CAPTURE_TARGETS = {
    "2027-w9-datadump": "2027-w9-datadump",
    "2027-w10-datadump": "2027-w10-datadump",
    "2027-bowlweek1-datadump": "2027-bowlweek1-datadump",
    "2027-eoy-screens": "2027-eoy-final",
}
LEDGER_FIELDS = [
    "source_kind", "source_name", "source_md5", "source_size_bytes",
    "workspace_slug", "lane", "season", "week", "matchup",
    "vault_dynasty", "vault_game_slug", "workspace_rows", "vault_rows",
    "workspace_sha256", "vault_sha256", "note_path", "capture_index",
    "required_capture_index", "validation_status", "content_status",
    "deletion_status", "drive_id", "drive_md5", "verified_at", "notes",
]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def csv_rows(path: Path) -> int:
    if not path.is_file():
        return 0
    with path.open(newline="", errors="replace") as f:
        return max(sum(1 for _ in csv.reader(f)) - 1, 0)


def load_json(path: Path) -> dict:
    if not path.is_file():
        return {}
    try:
        raw = path.read_text(errors="replace")
        starts = [i for i in (raw.find("{"), raw.find("[")) if i >= 0]
        data = json.loads(raw[min(starts):] if starts else raw)
        return data if isinstance(data, dict) else {"files": data}
    except (OSError, json.JSONDecodeError):
        return {}


def drive_values(workspace: Path) -> tuple[str, str, str, int]:
    marker = load_json(workspace / "drive_upload.json")
    entries = marker.get("files") or marker.get("uploads") or []
    if not entries and any(k in marker for k in ("md5", "md5Checksum", "local_md5")):
        entries = [marker]
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        md5 = entry.get("md5") or entry.get("md5Checksum") or entry.get("local_md5") or ""
        name = entry.get("name") or entry.get("file") or entry.get("local_source") or ""
        if md5:
            return str(entry.get("id") or ""), str(md5), Path(str(name)).name, int(entry.get("size") or 0)
    return "", "", "", 0


def validation_status(workspace: Path, chart_hash: str) -> str:
    receipt = load_json(workspace / "chart_validation.json")
    if not receipt:
        return "missing_receipt"
    if receipt.get("chart_sha256") != chart_hash:
        return "stale_receipt"
    return "pass" if receipt.get("status") == "pass" else "failed"


def capture_complete(index: Path) -> bool:
    if not index.is_file():
        return False
    text = index.read_text(errors="replace").lower()
    if "coverage ledger" not in text:
        return False
    zero_markers = (
        "never-transcribed = 0", "never-transcribed **= 0",
        "dump_reconcile.py` exit 0", "dump_reconcile.py exit 0",
        "21 of 21 screens transcribed", "all 21 originals were transcribed",
        "the sweep on 2026-08-18 closed it",
    )
    return any(marker in text for marker in zero_markers)


def default_vault_target(slug: str) -> tuple[str, str]:
    return ALIASES.get(slug, ("north-carolina", slug))


def read_ledger(path: Path) -> dict[str, dict[str, str]]:
    if not path.is_file():
        return {}
    with path.open(newline="") as f:
        rows = list(csv.DictReader(f))
    out = {}
    for row in rows:
        key = row.get("workspace_slug") or row.get("source_name")
        if key:
            out[key] = row
    return out


def source_from_workspace(workspace: Path) -> tuple[str, str, int]:
    media = sorted(p for p in workspace.iterdir()
                   if p.is_file() and p.suffix.lower() in MEDIA_SUFFIXES
                   and p.name != "video.mp4")
    if media:
        p = media[0]
        return p.name, "", p.stat().st_size
    _, md5, name, size = drive_values(workspace)
    return name, md5, size


@dataclass
class Result:
    source_kind: str = "game"
    source_name: str = ""
    source_md5: str = ""
    source_size_bytes: str = ""
    workspace_slug: str = ""
    lane: str = ""
    season: str = ""
    week: str = ""
    matchup: str = ""
    vault_dynasty: str = ""
    vault_game_slug: str = ""
    workspace_rows: str = ""
    vault_rows: str = ""
    workspace_sha256: str = ""
    vault_sha256: str = ""
    note_path: str = ""
    capture_index: str = ""
    required_capture_index: str = ""
    validation_status: str = "not_applicable"
    content_status: str = "discovered"
    deletion_status: str = "blocked"
    drive_id: str = ""
    drive_md5: str = ""
    verified_at: str = ""
    notes: str = ""


def game_result(film_root: Path, vault_root: Path, workspace: Path,
                seed: dict[str, str] | None = None) -> Result:
    seed = seed or {}
    slug = workspace.name
    dynasty, game_slug = default_vault_target(slug)
    dynasty = seed.get("vault_dynasty") or dynasty
    game_slug = seed.get("vault_game_slug") or game_slug
    chart = workspace / "plays_charted.csv"
    note = vault_root / "dynasties" / dynasty / "film-room" / "games" / f"{game_slug}.md"
    vault_csv = vault_root / "dynasties" / dynasty / "film-room" / "plays" / f"{game_slug}.csv"
    chart_hash = sha256(chart) if chart.is_file() else ""
    vault_hash = sha256(vault_csv) if vault_csv.is_file() else ""
    exact = bool(chart_hash and chart_hash == vault_hash and note.is_file())
    source_name, source_md5, source_size = source_from_workspace(workspace)
    drive_id, drive_md5, _, _ = drive_values(workspace)
    required_capture = seed.get("required_capture_index") or (
        "dynasties/north-carolina/film-room/captures/2027-cc-week-tail/_index.md"
        if slug == "2027-baylor-vs-rutgers-cc" else "")
    capture_ok = (not required_capture or capture_complete(vault_root / required_capture))
    val = validation_status(workspace, chart_hash) if chart_hash else "missing_chart"
    delete_ready = exact and val == "pass" and capture_ok
    files = load_json(workspace / "files.json")
    return Result(
        source_name=seed.get("source_name") or source_name,
        source_md5=seed.get("source_md5") or source_md5,
        source_size_bytes=seed.get("source_size_bytes") or (str(source_size) if source_size else ""),
        workspace_slug=slug,
        lane=seed.get("lane") or str(files.get("lane") or ""),
        season=seed.get("season") or slug[:4],
        week=seed.get("week") or "",
        matchup=seed.get("matchup") or game_slug.replace("-vs-", " vs ").replace("-", " ").title(),
        vault_dynasty=dynasty,
        vault_game_slug=game_slug,
        workspace_rows=str(csv_rows(chart)) if chart.is_file() else "",
        vault_rows=str(csv_rows(vault_csv)) if vault_csv.is_file() else "",
        workspace_sha256=chart_hash,
        vault_sha256=vault_hash,
        note_path=str(note.relative_to(vault_root)),
        required_capture_index=required_capture,
        validation_status=val,
        content_status="vault_complete" if exact else (
            "chart_only" if chart.is_file() else "unprocessed"),
        deletion_status="delete_ready" if delete_ready else "blocked",
        drive_id=drive_id,
        drive_md5=drive_md5,
        verified_at=seed.get("verified_at") or "",
        notes=seed.get("notes") or "",
    )


def capture_result(vault_root: Path, workspace: Path,
                   seed: dict[str, str] | None = None) -> Result:
    seed = seed or {}
    target = seed.get("capture_index") or (
        f"dynasties/north-carolina/film-room/captures/{CAPTURE_TARGETS[workspace.name]}/_index.md")
    index = vault_root / target
    source_name, source_md5, source_size = source_from_workspace(workspace)
    drive_id, drive_md5, _, _ = drive_values(workspace)
    complete = capture_complete(index)
    return Result(
        source_kind="capture",
        source_name=seed.get("source_name") or source_name,
        source_md5=seed.get("source_md5") or source_md5,
        source_size_bytes=seed.get("source_size_bytes") or (str(source_size) if source_size else ""),
        workspace_slug=workspace.name,
        lane="C",
        season=seed.get("season") or workspace.name[:4],
        week=seed.get("week") or "",
        matchup=seed.get("matchup") or workspace.name,
        vault_dynasty="north-carolina",
        capture_index=target,
        content_status="capture_complete" if complete else "capture_incomplete",
        deletion_status="delete_ready" if complete else "blocked",
        drive_id=drive_id,
        drive_md5=drive_md5,
        verified_at=seed.get("verified_at") or "",
        notes=seed.get("notes") or "",
    )


def loose_result(path: Path, seed: dict[str, str] | None = None) -> Result:
    seed = seed or {}
    slug, week, matchup = LOOSE_MEDIA.get(path.name, ("", "", path.stem))
    return Result(
        source_name=path.name,
        source_md5=seed.get("source_md5") or "",
        source_size_bytes=str(path.stat().st_size),
        workspace_slug=seed.get("workspace_slug") or slug,
        lane=seed.get("lane") or "B-variant-quicktime-usbc",
        season=seed.get("season") or (slug[:4] if slug else ""),
        week=seed.get("week") or week,
        matchup=seed.get("matchup") or matchup,
        vault_dynasty=seed.get("vault_dynasty") or "north-carolina",
        vault_game_slug=seed.get("vault_game_slug") or slug,
        content_status="unprocessed",
        validation_status="missing_chart",
        notes=seed.get("notes") or "loose media at film root; local deletion forbidden",
    )


def reconcile(film_root: Path, vault_root: Path, ledger: Path) -> list[Result]:
    seeds = read_ledger(ledger)
    results: list[Result] = []
    for workspace in sorted(film_root.iterdir()):
        if not workspace.is_dir() or not GAME_RE.match(workspace.name):
            continue
        seed = seeds.get(workspace.name, {})
        if workspace.name in NON_GAME_DIRS:
            results.append(capture_result(vault_root, workspace, seed))
        else:
            results.append(game_result(film_root, vault_root, workspace, seed))
    for path in sorted(film_root.iterdir()):
        if not path.is_file() or path.suffix.lower() not in MEDIA_SUFFIXES:
            continue
        planned_slug = LOOSE_MEDIA.get(path.name, ("",))[0]
        if planned_slug and (film_root / planned_slug).is_dir():
            # The original intentionally remains at the film root, but once a
            # registered workspace exists it is the same source, not a second
            # game. The ledger seed carries the root filename into that row.
            continue
        seed = seeds.get(path.name) or seeds.get(LOOSE_MEDIA.get(path.name, ("",))[0], {})
        results.append(loose_result(path, seed))
    return results


def write_ledger(path: Path, results: list[Result]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=LEDGER_FIELDS)
        writer.writeheader()
        for result in results:
            writer.writerow(asdict(result))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("film_root", nargs="?", default="~/CFB27-film")
    parser.add_argument("--vault-root", default="~/CFB27")
    parser.add_argument("--ledger")
    parser.add_argument("--write-ledger", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    film_root = Path(args.film_root).expanduser().resolve()
    vault_root = Path(args.vault_root).expanduser().resolve()
    ledger = Path(args.ledger).expanduser().resolve() if args.ledger else (
        vault_root / "operations" / "film-ingest-ledger.csv")
    results = reconcile(film_root, vault_root, ledger)
    if args.write_ledger:
        write_ledger(ledger, results)
    games = [r for r in results if r.source_kind == "game"]
    complete = sum(r.content_status == "vault_complete" for r in games)
    blocked = [r for r in results if r.deletion_status != "delete_ready"]
    payload = {
        "film_root": str(film_root), "vault_root": str(vault_root),
        "game_sources": len(games), "vault_complete_games": complete,
        "delete_ready_sources": len(results) - len(blocked),
        "blocked_sources": len(blocked), "results": [asdict(r) for r in results],
    }
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        print(f"reconcile_film: {complete}/{len(games)} games vault-complete; "
              f"{len(blocked)}/{len(results)} sources deletion-blocked")
        for r in blocked:
            print(f"  {r.workspace_slug or r.source_name}: {r.content_status}; "
                  f"validation={r.validation_status}")
    return 0 if not blocked else 1


if __name__ == "__main__":
    raise SystemExit(main())
