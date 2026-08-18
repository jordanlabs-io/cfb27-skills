#!/usr/bin/env python3
"""Verify imported transcript quality: timestamp monotonicity + word-count plausibility.

Usage: python3 verify_transcripts.py <transcripts-dir>

Checks every .md file (recursively, excluding INDEX files):
- **[MM:SS]** / **[H:MM:SS]** paragraph markers are strictly increasing
- word count is plausible for the video duration (~100-300 wpm window), unless the
  frontmatter carries a `pace_exempt:` reason (long silent stretches make the
  words/wall-clock ratio meaningless; the reason string must say why)
- file is non-empty and has frontmatter
- no two files share a frontmatter `video_id` (re-scraped duplicate imports)

Exit code 0 = all clean, 1 = problems found.
"""
import re
import sys
import glob
import os


def secs(ts: str) -> int:
    s = 0
    for p in ts.split(":"):
        s = s * 60 + int(p)
    return s


def main(root: str) -> int:
    problems = []
    vid_files = {}
    files = [
        f
        for f in glob.glob(os.path.join(root, "**", "*.md"), recursive=True)
        if not os.path.basename(f).upper().startswith(("INDEX", "_"))
    ]
    if not files:
        print(f"no transcript files found under {root}")
        return 1
    for f in sorted(files):
        text = open(f).read()
        name = os.path.relpath(f, root)
        if not text.strip():
            problems.append(f"{name}: EMPTY FILE")
            continue
        if not text.startswith("---"):
            problems.append(f"{name}: missing YAML frontmatter")
        vid = re.search(r"^video_id:\s*(\S+)", text, re.M)
        if vid:
            vid_files.setdefault(vid.group(1).strip("\"'"), []).append(name)
        marks = re.findall(r"\*\*\[([0-9:]+)\]\*\*", text)
        if not marks:
            problems.append(f"{name}: no **[MM:SS]** timestamp markers")
            continue
        prev = -1
        for m in marks:
            s = secs(m)
            if s <= prev:
                problems.append(f"{name}: NON-MONOTONIC timestamp at [{m}]")
            prev = s
        # word count vs duration (from frontmatter duration: HH:MM:SS)
        dur = re.search(r"^duration:\s*([0-9:]+)", text, re.M)
        if dur and not re.search(r"^pace_exempt:\s*\S", text, re.M):
            minutes = secs(dur.group(1)) / 60
            words = len(re.sub(r"^---.*?---", "", text, flags=re.S).split())
            if minutes >= 1:
                wpm = words / minutes
                # ceiling 300: jump-cut YouTube commentary runs fast — 277 wpm
                # verified word-for-word against live captions (2026-07-11)
                if not (100 <= wpm <= 300):
                    problems.append(
                        f"{name}: implausible pace {wpm:.0f} wpm "
                        f"({words} words / {minutes:.1f} min) — check for dropped or duplicated captions"
                    )
    for vid, names in sorted(vid_files.items()):
        if len(names) > 1:
            problems.append(
                f"DUPLICATE video_id {vid} in {len(names)} files: {', '.join(names)}"
            )
    print(f"checked {len(files)} transcript files")
    if problems:
        print(f"{len(problems)} problem(s):")
        for p in problems:
            print("  -", p)
        return 1
    print("all clean: monotonic timestamps, plausible word counts, frontmatter present")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "transcripts"))
