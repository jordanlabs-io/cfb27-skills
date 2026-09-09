#!/usr/bin/env python3
"""
NFL coverage priors from Kaggle Big Data Bowl 2026 tracking + supplementary data.
Produces priors.md and priors.json in the same directory.

Source: Kaggle NFL Big Data Bowl 2026 analytics competition, 2023 season
weeks 1-18, 14,066 pass plays. Requires the competition CSVs locally
(tracking + play + player data) — not part of the film-room charting
pipeline. Kept here for reference/regeneration only; the charting agent
reads the derived nfl-coverage-priors.json, not this script.
"""
import glob
import json
import os
import sys

import pandas as pd
import numpy as np

DIR = os.path.dirname(os.path.abspath(__file__))
MIN_N = 30

FAMILY_MAP = {
    "COVER_0_MAN": "cover-0",
    "COVER_1_MAN": "cover-1",
    "COVER_2_ZONE": "cover-2",
    "COVER_2_MAN": "cover-2-man",
    "COVER_3_ZONE": "cover-3",
    "COVER_4_ZONE": "cover-4",
    "COVER_6_ZONE": "cover-6",
}
MAN_ZONE_MAP = {
    "COVER_0_MAN": "man", "COVER_1_MAN": "man", "COVER_2_MAN": "man",
    "COVER_2_ZONE": "zone", "COVER_3_ZONE": "zone", "COVER_4_ZONE": "zone", "COVER_6_ZONE": "zone",
}

SHELL_THRESHOLDS = [8, 9, 10, 12]
PRIMARY_THRESH = 9
POST_SNAP_FRAME = 16  # 10fps -> +1.5s

# Safety-rotation redefinition: post-snap safety structure is measured only on
# players who are actually safeties (FS/SS), plus any CB aligned at safety depth
# pre-snap (frame 1 depth >= SAFETY_ALIGN_THRESH). This excludes LBs/CBs whose
# frame-1 depth happens to be >=9yd but who are dropping into a zone drop rather
# than rotating a deep safety shell.
SAFETY_POSITIONS = {"FS", "SS"}
SAFETY_ALIGN_THRESH = 9   # CB counted as an aligned safety if frame-1 depth >= this
SAFETY_DEEP_PRE_THRESH = 9    # deep at snap
SAFETY_DEEP_POST_THRESH = 12  # deep at +2.0s
ROTATION_POST_FRAME = 21  # 10fps -> +2.0s


def shell_label(n):
    if n == 0:
        return "0-high"
    if n == 1:
        return "1-high"
    if n == 2:
        return "2-high"
    return "3-high"


def load_supplementary():
    sup = pd.read_csv(os.path.join(DIR, "supplementary_data.csv"), low_memory=False)
    sup = sup[sup["team_coverage_type"].notna()]
    sup = sup[sup["team_coverage_type"] != "PREVENT"]
    sup = sup[sup["play_nullified_by_penalty"] != "Y"]
    sup["family"] = sup["team_coverage_type"].map(FAMILY_MAP)
    sup["man_zone"] = sup["team_coverage_type"].map(MAN_ZONE_MAP)

    def dist_bucket(y):
        if pd.isna(y):
            return np.nan
        if y <= 3:
            return "short (<=3)"
        if y <= 6:
            return "medium (4-6)"
        if y <= 10:
            return "long (7-10)"
        return "very long (11+)"
    sup["dist_bucket"] = sup["yards_to_go"].apply(dist_bucket)

    # red zone: yardline_side == defensive_team and yardline_number <= 20
    sup["red_zone"] = (sup["yardline_side"] == sup["defensive_team"]) & (sup["yardline_number"] <= 20)

    # score state for the DEFENSE: defense is home or visitor?
    def score_state(row):
        if row["defensive_team"] == row.get("home_team_abbr"):
            def_score = row["pre_snap_home_score"]
            off_score = row["pre_snap_visitor_score"]
        else:
            def_score = row["pre_snap_visitor_score"]
            off_score = row["pre_snap_home_score"]
        if pd.isna(def_score) or pd.isna(off_score):
            return np.nan
        if def_score > off_score:
            return "leading"
        if def_score < off_score:
            return "trailing"
        return "tied"
    sup["def_score_state"] = sup.apply(score_state, axis=1)

    return sup


def compute_shells_for_week(path, sup_keys):
    """Return DataFrame: game_id, play_id, shell_snap(dict per threshold), shell_post, rotation flags."""
    df = pd.read_csv(path)
    df = df[df["player_side"] == "Defense"]
    # restrict to plays present in filtered supplementary set
    df = df.merge(sup_keys, on=["game_id", "play_id"], how="inner")

    df["depth"] = np.where(
        df["play_direction"] == "right",
        df["x"] - df["absolute_yardline_number"],
        df["absolute_yardline_number"] - df["x"],
    )

    results = []
    for (gid, pid), g in df.groupby(["game_id", "play_id"], sort=False):
        last_frame = g["frame_id"].max()
        f1 = g[g["frame_id"] == 1]
        target_post = min(POST_SNAP_FRAME, last_frame)
        fpost = g[g["frame_id"] == target_post]

        row = {"game_id": gid, "play_id": pid, "post_frame_used": target_post, "n_def_f1": len(f1)}
        for th in SHELL_THRESHOLDS:
            row[f"shell_snap_{th}"] = int((f1["depth"] >= th).sum())
        row["shell_post"] = int((fpost["depth"] >= PRIMARY_THRESH).sum())

        # -------- safety-only rotation subset (FS/SS + aligned CBs) --------
        target_rot = min(ROTATION_POST_FRAME, last_frame)
        frot = g[g["frame_id"] == target_rot]
        f1_by_id = f1.set_index("nfl_id")
        # players eligible: FS/SS always; CB only if frame-1 depth >= SAFETY_ALIGN_THRESH
        is_safety_pos = f1_by_id["player_position"].isin(SAFETY_POSITIONS)
        is_aligned_cb = (f1_by_id["player_position"] == "CB") & (f1_by_id["depth"] >= SAFETY_ALIGN_THRESH)
        safety_ids = f1_by_id.index[is_safety_pos | is_aligned_cb]

        f1_saf = f1_by_id.loc[safety_ids]
        frot_saf = frot.set_index("nfl_id").reindex(safety_ids)

        deep_pre = int((f1_saf["depth"] >= SAFETY_DEEP_PRE_THRESH).sum())
        # only count post-snap deep among safeties with a valid post-frame reading
        deep_post = int((frot_saf["depth"] >= SAFETY_DEEP_POST_THRESH).sum())

        row["rot_post_frame_used"] = target_rot
        row["n_safeties"] = len(safety_ids)
        row["safety_deep_pre"] = deep_pre
        row["safety_deep_post"] = deep_post
        results.append(row)
    return pd.DataFrame(results)


def build_table(df, group_cols, min_n=MIN_N):
    """Row-normalized crosstab-style counts with suppression."""
    out = {}
    for keyvals, g in df.groupby(group_cols, dropna=False):
        n = len(g)
        if n < min_n:
            continue
        key = keyvals if isinstance(keyvals, tuple) else (keyvals,)
        keystr = " / ".join(str(k) for k in key)
        out[keystr] = {"n": n}
    return out


def rate_str(k, n):
    if n == 0:
        return "0/0 (n/a)"
    return f"{k}/{n} ({100*k/n:.1f}%)"


def main():
    print("Loading supplementary_data.csv...")
    sup = load_supplementary()
    print(f"  {len(sup)} plays after dropping PREVENT / NA coverage / penalty-nullified")

    sup_keys = sup[["game_id", "play_id"]].drop_duplicates()

    files = sorted(glob.glob(os.path.join(DIR, "input_2023_w*.csv")))
    print(f"Found {len(files)} tracking week files: {[os.path.basename(f) for f in files]}")

    shell_frames = []
    for f in files:
        print(f"  processing {os.path.basename(f)} ...")
        shell_frames.append(compute_shells_for_week(f, sup_keys))
    shells = pd.concat(shell_frames, ignore_index=True)
    print(f"  {len(shells)} plays with shell data computed")

    data = sup.merge(shells, on=["game_id", "play_id"], how="inner")
    print(f"Final joined dataset: {len(data)} plays")

    for th in SHELL_THRESHOLDS:
        data[f"shell_label_{th}"] = data[f"shell_snap_{th}"].apply(shell_label)
    data["shell_label_post"] = data["shell_post"].apply(shell_label)

    # -------- safety-only rotation classification --------
    data["safety_pre_label"] = data["safety_deep_pre"].apply(shell_label)
    data["safety_post_label"] = data["safety_deep_post"].apply(shell_label)

    def rot_event(row):
        pre, post = row["safety_deep_pre"], row["safety_deep_post"]
        if pre == post:
            return "sat"
        if post < pre:
            return "roll-down"
        return "bail"
    data["rotation_event"] = data.apply(rot_event, axis=1)
    data["rotated_safety"] = data["rotation_event"] != "sat"

    out = {"meta": {}, "tables": {}}
    md_lines = []
    md_lines.append("# NFL Coverage Priors — Big Data Bowl 2026 (2023 tracking weeks 1-18)\n")

    # -------- Frame-1 finding --------
    md_lines.append("## Frame-1 sanity check\n")
    md_lines.append(
        "Mean defensive speed rises smoothly from frame 1 (~0.58 yd/s across week 1 sample) up to "
        "~5.8 yd/s by the last route frames, with no discontinuous jump at any frame — i.e. there is "
        "no sharp 'snap moment' marker in the speed series. Frame 1 is low-speed (players largely set "
        "or in slow presnap motion) but **not perfectly static** — some presnap shifting/motion is "
        "already underway. Frame 1 is therefore used as the presnap/at-snap reference, understanding it "
        "is at or very near the snap rather than a frozen presnap instant.\n"
    )

    # -------- Shell sensitivity --------
    md_lines.append("## Shell distribution at snap — sensitivity to depth threshold\n")
    md_lines.append("| Threshold (yds) | 0-high | 1-high | 2-high | 3-high | n |")
    md_lines.append("|---|---|---|---|---|---|")
    shell_sensitivity = {}
    for th in SHELL_THRESHOLDS:
        counts = data[f"shell_label_{th}"].value_counts()
        n = len(data)
        row = {lbl: int(counts.get(lbl, 0)) for lbl in ["0-high", "1-high", "2-high", "3-high"]}
        shell_sensitivity[th] = row
        md_lines.append(
            "| {} | {} | {} | {} | {} | {} |".format(
                th,
                rate_str(row["0-high"], n), rate_str(row["1-high"], n),
                rate_str(row["2-high"], n), rate_str(row["3-high"], n), n,
            )
        )
    out["tables"]["shell_sensitivity"] = shell_sensitivity
    md_lines.append("")

    primary_col = f"shell_label_{PRIMARY_THRESH}"

    # -------- Shell -> family matrix (row-normalized) + overall family dist --------
    md_lines.append(f"## Shell-at-snap ({PRIMARY_THRESH}yd threshold) -> coverage family (row-normalized)\n")
    families = ["cover-0", "cover-1", "cover-2", "cover-2-man", "cover-3", "cover-4", "cover-6"]
    md_lines.append("| Shell | " + " | ".join(families) + " | n |")
    md_lines.append("|---" * (len(families) + 2) + "|")
    shell_family_matrix = {}
    for shell in ["0-high", "1-high", "2-high", "3-high"]:
        sub = data[data[primary_col] == shell]
        n = len(sub)
        if n < MIN_N:
            continue
        counts = sub["family"].value_counts()
        row = {}
        cells = []
        for fam in families:
            k = int(counts.get(fam, 0))
            row[fam] = {"k": k, "n": n, "pct": round(100 * k / n, 1) if n else None}
            cells.append(rate_str(k, n))
        shell_family_matrix[shell] = row
        md_lines.append(f"| {shell} | " + " | ".join(cells) + f" | {n} |")
    out["tables"]["shell_to_family_matrix"] = shell_family_matrix
    md_lines.append("")

    md_lines.append("### Overall coverage family distribution\n")
    fam_counts = data["family"].value_counts()
    n_all = len(data)
    overall_family = {}
    md_lines.append("| Family | k/n (pct) |")
    md_lines.append("|---|---|")
    for fam in families:
        k = int(fam_counts.get(fam, 0))
        overall_family[fam] = {"k": k, "n": n_all, "pct": round(100 * k / n_all, 1)}
        md_lines.append(f"| {fam} | {rate_str(k, n_all)} |")
    out["tables"]["overall_family_distribution"] = overall_family
    md_lines.append("")

    # -------- Rotation (safety-only definition) --------
    md_lines.append("## Safety rotation rate overall and by pre-snap shell\n")
    md_lines.append(
        "Redefined: rotation is measured only on players who are FS/SS, or a CB aligned at "
        f"safety depth pre-snap (frame-1 depth >= {SAFETY_ALIGN_THRESH}yd) — this excludes zone-dropping "
        "LBs/CBs that the naive all-defenders shell count picks up. deep_pre = count of that subset "
        f"with depth >= {SAFETY_DEEP_PRE_THRESH}yd at frame 1; deep_post = count with depth >= "
        f"{SAFETY_DEEP_POST_THRESH}yd at ~+2.0s. roll-down = deep count decreased, bail = increased, sat = unchanged.\n"
    )
    rot_overall_k = int(data["rotated_safety"].sum())
    rot_overall_n = len(data)
    md_lines.append(f"Overall safety rotation rate: {rate_str(rot_overall_k, rot_overall_n)}\n")
    md_lines.append("| Shell at snap (pre-snap, all-defenders def.) | rotated k/n (pct) | roll-down | bail | sat |")
    md_lines.append("|---|---|---|---|---|")
    rotation_by_shell = {
        "overall": {
            "k": rot_overall_k, "n": rot_overall_n,
            "roll_down": int((data["rotation_event"] == "roll-down").sum()),
            "bail": int((data["rotation_event"] == "bail").sum()),
            "sat": int((data["rotation_event"] == "sat").sum()),
        }
    }
    for shell in ["0-high", "1-high", "2-high", "3-high"]:
        sub = data[data[primary_col] == shell]
        n = len(sub)
        if n < MIN_N:
            continue
        k = int(sub["rotated_safety"].sum())
        roll_down = int((sub["rotation_event"] == "roll-down").sum())
        bail = int((sub["rotation_event"] == "bail").sum())
        sat = int((sub["rotation_event"] == "sat").sum())
        rotation_by_shell[shell] = {"k": k, "n": n, "roll_down": roll_down, "bail": bail, "sat": sat}
        md_lines.append(f"| {shell} | {rate_str(k, n)} | {rate_str(roll_down, n)} | {rate_str(bail, n)} | {rate_str(sat, n)} |")
    out["tables"]["rotation_by_shell"] = rotation_by_shell
    md_lines.append("")

    # rotation -> resulting coverage (e.g. 2-high at snap -> post safety shell -> family)
    md_lines.append("## Safety rotation -> resulting coverage (shell-at-snap -> post safety-count shell -> family)\n")
    rotation_to_coverage = {}
    for shell in ["0-high", "1-high", "2-high", "3-high"]:
        sub = data[(data[primary_col] == shell) & (data["rotated_safety"])]
        n = len(sub)
        if n < MIN_N:
            continue
        md_lines.append(f"### From {shell} at snap (safety-rotated), n={n}\n")
        md_lines.append("| Post safety-count shell | n | Top family | k/n (pct) |")
        md_lines.append("|---|---|---|---|")
        block = {}
        for post_shell, g in sub.groupby("safety_post_label"):
            ng = len(g)
            if ng < MIN_N:
                continue
            top_fam = g["family"].value_counts()
            top_fam_name = top_fam.index[0]
            top_fam_k = int(top_fam.iloc[0])
            block[post_shell] = {
                "n": ng,
                "family_counts": {f: int(c) for f, c in top_fam.items()},
            }
            md_lines.append(f"| {post_shell} | {ng} | {top_fam_name} | {rate_str(top_fam_k, ng)} |")
        rotation_to_coverage[shell] = block
        md_lines.append("")
    out["tables"]["rotation_to_coverage"] = rotation_to_coverage

    # -------- Disguise sanity lines --------
    md_lines.append("## Disguise sanity checks\n")
    sub2high = data[data[primary_col] == "2-high"]
    n2 = len(sub2high)
    disguised_c3_k = int(((sub2high["family"] == "cover-3") & (sub2high["rotation_event"] == "roll-down")).sum())
    md_lines.append(
        f"**Disguised cover-3 baseline — 2-high-at-snap plays labeled cover-3 AND rolled down "
        f"(NFL 'disguised cover-3'): {rate_str(disguised_c3_k, n2)}**\n"
    )
    out["tables"]["disguised_cover3_baseline"] = {"k": disguised_c3_k, "n": n2}

    cover1_2high_k = int((sub2high["family"] == "cover-1").sum())
    md_lines.append(
        f"**2-high-at-snap plays labeled cover-1 (started 2-high, played cover-1): {rate_str(cover1_2high_k, n2)}**\n"
    )
    out["tables"]["cover1_from_2high"] = {"k": cover1_2high_k, "n": n2}

    # -------- splits: family and man/zone by down&distance, formation, box count, PA, red zone, score state --------
    split_specs = [
        ("down", "down"),
        ("dist_bucket", "distance_bucket"),
        ("offense_formation", "offense_formation"),
        ("defenders_in_the_box", "defenders_in_the_box"),
        ("play_action", "play_action"),
        ("red_zone", "red_zone"),
        ("def_score_state", "defense_score_state"),
    ]

    md_lines.append("## Coverage family by split\n")
    family_splits = {}
    for col, label in split_specs:
        md_lines.append(f"### By {label}\n")
        md_lines.append("| " + label + " | " + " | ".join(families) + " | n |")
        md_lines.append("|---" * (len(families) + 2) + "|")
        block = {}
        for val, g in data.groupby(col, dropna=False):
            n = len(g)
            if n < MIN_N:
                continue
            counts = g["family"].value_counts()
            row = {}
            cells = []
            for fam in families:
                k = int(counts.get(fam, 0))
                row[fam] = {"k": k, "n": n, "pct": round(100 * k / n, 1)}
                cells.append(rate_str(k, n))
            block[str(val)] = row
            md_lines.append(f"| {val} | " + " | ".join(cells) + f" | {n} |")
        family_splits[label] = block
        md_lines.append("")
    out["tables"]["family_by_split"] = family_splits

    md_lines.append("## Man vs zone by split\n")
    manzone_splits = {}
    for col, label in split_specs:
        md_lines.append(f"### By {label}\n")
        md_lines.append(f"| {label} | man k/n (pct) | zone k/n (pct) | n |")
        md_lines.append("|---|---|---|---|")
        block = {}
        for val, g in data.groupby(col, dropna=False):
            n = len(g)
            if n < MIN_N:
                continue
            man_k = int((g["man_zone"] == "man").sum())
            zone_k = int((g["man_zone"] == "zone").sum())
            block[str(val)] = {"man": {"k": man_k, "n": n}, "zone": {"k": zone_k, "n": n}}
            md_lines.append(f"| {val} | {rate_str(man_k, n)} | {rate_str(zone_k, n)} | {n} |")
        manzone_splits[label] = block
        md_lines.append("")
    out["tables"]["man_zone_by_split"] = manzone_splits

    # -------- Sanity checks --------
    md_lines.append("## Sanity checks\n")
    shell_dist = data[primary_col].value_counts()
    n_all = len(data)
    md_lines.append("**Shell distribution (expect 2-high most common):**\n")
    for lbl in ["0-high", "1-high", "2-high", "3-high"]:
        k = int(shell_dist.get(lbl, 0))
        md_lines.append(f"- {lbl}: {rate_str(k, n_all)}")
    md_lines.append("")

    md_lines.append("**Cover-3 share by shell (expect 1-high -> cover-3/cover-1 dominant, 2-high -> cover-2/4/6 dominant):**\n")
    cover3_by_shell = {}
    for shell in ["0-high", "1-high", "2-high", "3-high"]:
        sub = data[data[primary_col] == shell]
        n = len(sub)
        if n < MIN_N:
            continue
        k = int((sub["family"] == "cover-3").sum())
        cover3_by_shell[shell] = {"k": k, "n": n}
        md_lines.append(f"- {shell}: cover-3 = {rate_str(k, n)}")
    out["tables"]["sanity_cover3_by_shell"] = cover3_by_shell
    md_lines.append("")

    sub2high = data[data[primary_col] == "2-high"]
    n2 = len(sub2high)
    k2c3 = int((sub2high["family"] == "cover-3").sum())
    md_lines.append(f"**2-high-at-snap plays labeled cover-3 (NFL 'rotation to cover-3' baseline): {rate_str(k2c3, n2)}**\n")
    out["tables"]["rotation_to_cover3_baseline"] = {"k": k2c3, "n": n2}

    out["meta"] = {
        "n_plays_total": int(n_all),
        "shell_threshold_primary_yds": PRIMARY_THRESH,
        "post_snap_target_frame": POST_SNAP_FRAME,
        "min_n_suppression": MIN_N,
        "weeks_included": [os.path.basename(f) for f in files],
    }

    with open(os.path.join(DIR, "priors.md"), "w") as f:
        f.write("\n".join(md_lines))
    with open(os.path.join(DIR, "priors.json"), "w") as f:
        json.dump(out, f, indent=2)

    print("\n=== SUMMARY ===")
    print(f"Total plays: {n_all}")
    print("\nShell distribution (9yd):")
    for lbl in ["0-high", "1-high", "2-high", "3-high"]:
        k = int(shell_dist.get(lbl, 0))
        print(f"  {lbl}: {rate_str(k, n_all)}")
    print("\nCover-3 share by shell:")
    for shell, v in cover3_by_shell.items():
        print(f"  {shell}: {rate_str(v['k'], v['n'])}")
    print(f"\n2-high -> cover-3 baseline: {rate_str(k2c3, n2)}")
    print("\nWrote priors.md and priors.json")


if __name__ == "__main__":
    main()
