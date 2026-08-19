#!/usr/bin/env python3
"""Canonical chart schema (v3) — single source of truth for field enums and
column order. Doc twin: references/chart-schema.md (keep both in sync; the doc
explains each field, this module is what scripts import).

History: v2 = the 2026-07/08 superset (see calibration-history.md). v3 adds the
pre-snap tell fields (leverage/depth/hash/QB animation), mesh-behavior fields
(pa_fake / rpo_look), dl_stunt_seen, def_bust, screen_dir, the play-art fields,
the full-frame HUD cross-check fields, and the derived columns
(schema_version, field_side, coverage_candidates, play_style, def_coverage_src,
def_rotation_lc, hud_conflict).
"""

SCHEMA_VERSION = "3"

# --- vision-charted enums (superset JSON keys -> allowed values).
# Free-text fields are listed with None (no enum check).
ENUMS = {
    "play_type": {"run", "pass", "non-play", "unknown", ""},
    "motion": {"yes", "no", "unknown", ""},
    "def_front": {"4-2-5", "3-3-5", "4-3", "3-4", "5-2", "6-1", "dime", "unknown", ""},
    "def_shell_pre": {"2-high", "1-high", "0-high", "3-high", "unknown", ""},
    "def_safeties_post": {"3", "2", "1", "0", "unknown", ""},
    "def_cb_technique": {"press", "off", "bail", "mixed", "unknown", ""},
    "def_zone_type": {"spot-drop", "match", "man", "unknown", ""},
    "confidence": {"high", "medium", "low", "unknown", ""},
    "motion_type": {"jet", "orbit", "short", "across", "shift", "none", "unknown", ""},
    "motion_response": {"follow", "slide", "static", "no-motion", "unknown", ""},
    "cb_depth_pre": {"press", "off", "mixed", "unknown", ""},
    "nickel_present": {"true", "false", "unknown", ""},
    "cb_relation": {"chase", "squat", "land", "mixed", "unknown", ""},
    "lb_pass_action": {"run-with", "spot", "blitz", "run-fit", "unknown", ""},
    "crosser_handoff": {"trail", "pass-off", "none", "unknown", ""},
    "qb_drop": {"3-step", "5-step", "rollout-L", "rollout-R", "boot", "n/a", "unknown", ""},
    "pressure": {"clean", "hurried", "hit", "sacked", "n/a", "unknown", ""},
    "presnap_adjust": {"audible", "shift", "motion-only", "none", "unknown", ""},
    "def_adjust": {"shell-shift", "front-shift", "late-show", "none", "unknown", ""},
    "menu_side": {"offense", "defense", "both", "none", "unknown", ""},
    # --- v3 pre-snap tell fields
    "cb_leverage_pre": {"inside", "outside", "head-up", "mixed", "unknown", ""},
    "saf_depth_band": {"<10", "10-14", "15+", "split", "unknown", ""},
    "saf_nickel_trips_side": {"both", "safety-opposite", "n/a", "unknown", ""},
    "ball_hash": {"left", "middle", "right", "unknown", ""},
    "qb_presnap_anim": {"wave", "squat", "double-tap", "helmet-touch", "none", "unknown", ""},
    # --- v3 mesh/flow behavior fields
    "pa_fake": {"yes", "no", "n/a", "unknown", ""},
    "rpo_look": {"yes", "no", "n/a", "unknown", ""},
    "dl_stunt_seen": {"twist", "slant", "loop", "none", "unknown", ""},
    "def_bust": {"yes", "no", "unknown", ""},
    "screen_dir": {"L", "R", "middle", "n/a", "unknown", ""},
    # --- v3 full-frame HUD cross-check (vision-read off fullframe.jpg)
    "hud_poss": {"L", "R", "unknown", ""},
    # --- 2026-08-14 ordered pre-play read (presnap_seq lane; adjust_seq,
    # playart_delta and postsnap_confirms are free text, listed in V2_FIELDS only)
    "def_shell_initial": {"2-high", "1-high", "0-high", "3-high", "unknown", ""},
}

# Normalisation map applied before enum checks (case drift, synonyms agents
# actually produce). Off-schema values NOT covered here get flagged, never
# silently rewritten — "unknown beats a guess" applies to the fixer too.
NORMALISE = {
    "nickel_present": {"True": "true", "False": "false"},
    "def_zone_type": {"zone": "unknown"},   # ambiguous — spot-drop vs match unstated
    "def_safeties_post": {"2-high": "2", "1-high": "1", "0-high": "0", "3-high": "3",
                          "two": "2", "one": "1", "zero": "0"},
    "qb_presnap_anim": {"double-toe-tap": "double-tap", "toe-tap": "double-tap"},
    "saf_depth_band": {"under-10": "<10", "over-15": "15+"},
    "lb_pass_action": {"spot-drop": "spot", "run-fill": "run-fit"},
    "qb_drop": {"none": "n/a"},
}
# "n/a" is a legal charted value on every enum (non-plays fill fields n/a per
# the charting prompt) — allowed globally rather than per-enum.
for _vals in ENUMS.values():
    _vals.add("n/a")

# Fields whose target column carries a v2_ prefix (the vision-lane merge).
# Order here IS the column order in the CSV.
V2_FIELDS = [
    "off_formation", "def_shell_pre", "cb_depth_pre", "play_type",
    "motion_type", "motion_response", "def_front", "box_count", "nickel_present",
    "rushers", "cb_relation", "lb_pass_action", "crosser_handoff",
    "qb_drop", "target_area", "run_direction", "pressure",
    # v3 additions
    "cb_leverage_pre", "saf_depth_band", "saf_nickel_trips_side", "ball_hash",
    "qb_presnap_anim", "pa_fake", "rpo_look", "dl_stunt_seen", "def_bust",
    "screen_dir",
    "off_playart", "def_playart_zones", "def_playart_coverage",
    "hud_dd", "hud_poss", "hud_score",
    # 2026-08-14 ordered pre-play read (presnap_seq grid)
    "def_shell_initial", "adjust_seq", "playart_delta", "postsnap_confirms",
    # menu intel stays last
    "menu_visible", "menu_side", "screen_call", "menu_tiles",
]

# Canonical assembled-CSV column order (header-name reads stay the contract;
# this list exists so every game's CSV lands in the SAME order).
BASE_COLUMNS = [
    "n", "qtr", "clock", "dd", "poss", "poss_src", "score",
    "snap_t", "sec_since_prev_snap", "playclock_at_snap", "tempo",
    "formation", "personnel", "formation_src", "motion", "play_type",
    "play_type_vision", "play_type_transcript", "concept", "routes_or_blocking",
    "def_front", "def_shell_pre", "def_post_snap", "def_safeties_post",
    "def_cb_technique", "def_zone_type", "def_coverage", "def_coverage_src",
    "coverage_candidates", "def_rotation", "def_rotation_lc",
    "formation_initial", "presnap_adjust", "adjust_note", "def_adjust",
    "confidence", "note", "transcript",
    "result", "yards", "key_event",
]
DERIVED_COLUMNS = ["man_zone_verdict", "mz_confidence", "field_side",
                   "play_style", "hud_conflict", "schema_version", "v2_src"]
FINAL_COLUMNS = BASE_COLUMNS + ["v2_" + f for f in V2_FIELDS] + DERIVED_COLUMNS


def normalise(field, value):
    """Case-fold + synonym-map a charted value; returns the value unchanged
    when no rule applies (never guesses)."""
    v = ("" if value is None else str(value)).strip()
    v = NORMALISE.get(field, {}).get(v, v)
    if field in ENUMS and v.lower() in ENUMS[field]:
        return v.lower() if field != "screen_dir" else v
    if field == "screen_dir" and v in ENUMS[field]:
        return v
    return v


def enum_violations(field, value):
    """True when the value is off-schema for an enum field (after normalise)."""
    if field not in ENUMS:
        return False
    return normalise(field, value) not in ENUMS[field]


def ordered_columns(present):
    """Stable ordering for whatever columns a CSV actually has: canonical order
    first, unknown/legacy extras appended in their original order (never drop)."""
    known = [c for c in FINAL_COLUMNS if c in present]
    extras = [c for c in present if c not in FINAL_COLUMNS]
    return known + extras
