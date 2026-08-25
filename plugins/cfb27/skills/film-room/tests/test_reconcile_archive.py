import csv
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock
from types import SimpleNamespace


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import archive_sweep
import archive_audit
import audit_clips
import assemble
import chart_schema
import reconcile_film


class FilmGateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.film = self.root / "film"
        self.vault = self.root / "vault"
        self.film.mkdir()
        (self.vault / "operations").mkdir(parents=True)
        self.ledger = self.vault / "operations" / "film-ingest-ledger.csv"

    def tearDown(self):
        self.tmp.cleanup()

    def make_game(self, slug="2027-test-vs-team", dynasty="north-carolina",
                  game_slug=None, note=True, matching=True, receipt="pass"):
        game_slug = game_slug or slug
        workspace = self.film / slug
        workspace.mkdir()
        chart = workspace / "plays_charted.csv"
        chart.write_text("n,play_type\n1,run\n")
        target = self.vault / "dynasties" / dynasty / "film-room"
        (target / "games").mkdir(parents=True)
        (target / "plays").mkdir(parents=True)
        if note:
            (target / "games" / f"{game_slug}.md").write_text("# report\n")
        vault_csv = target / "plays" / f"{game_slug}.csv"
        vault_csv.write_text(chart.read_text() if matching else "n,play_type\n1,pass\n")
        if receipt:
            digest = reconcile_film.sha256(chart)
            if receipt == "stale":
                digest = "0" * 64
            (workspace / "chart_validation.json").write_text(json.dumps({
                "status": "pass" if receipt in ("pass", "stale") else "fail",
                "chart_sha256": digest,
            }))
        return workspace

    def test_drive_receipt_does_not_replace_missing_note(self):
        workspace = self.make_game(note=False)
        (workspace / "drive_upload.json").write_text(json.dumps({
            "files": [{"name": "source.mov", "id": "drive", "md5": "abc"}]
        }))
        result = reconcile_film.game_result(self.film, self.vault, workspace)
        self.assertEqual(result.content_status, "chart_only")
        self.assertEqual(result.deletion_status, "blocked")

    def test_mismatched_vault_csv_blocks_deletion(self):
        workspace = self.make_game(matching=False)
        result = reconcile_film.game_result(self.film, self.vault, workspace)
        self.assertEqual(result.content_status, "chart_only")
        self.assertEqual(result.deletion_status, "blocked")

        problems, _ = archive_audit.audit(self.film, self.vault, self.ledger)
        reasons = dict(problems)[workspace.name]
        self.assertIn("[MISMATCHED CSVs]", reasons)

    def test_stale_validation_receipt_blocks_deletion(self):
        workspace = self.make_game(receipt="stale")
        result = reconcile_film.game_result(self.film, self.vault, workspace)
        self.assertEqual(result.content_status, "validation_incomplete")
        self.assertEqual(result.validation_status, "stale_receipt")
        self.assertEqual(result.deletion_status, "blocked")

    def test_failing_dynasty_verifier_blocks_deletion(self):
        workspace = self.make_game()
        result = reconcile_film.game_result(
            self.film, self.vault, workspace, vault_validation_status="failed")
        self.assertEqual(result.content_status, "validation_incomplete")
        self.assertEqual(result.deletion_status, "blocked")

    def test_known_alias_resolves_cross_dynasty(self):
        workspace = self.make_game(
            slug="2026-osu-umd-calibration", dynasty="oregon-state",
            game_slug="2026-osu-vs-umd")
        result = reconcile_film.game_result(self.film, self.vault, workspace)
        self.assertEqual(result.vault_dynasty, "oregon-state")
        self.assertEqual(result.vault_game_slug, "2026-osu-vs-umd")
        self.assertEqual(result.deletion_status, "delete_ready")

    def test_loose_media_is_discovered_and_blocked(self):
        loose = self.film / "UMD at Rutgers '27.mov"
        loose.write_bytes(b"film")
        results = reconcile_film.reconcile(self.film, self.vault, self.ledger)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].workspace_slug, "2027-maryland-vs-rutgers")
        self.assertEqual(results[0].content_status, "unprocessed")
        self.assertEqual(results[0].deletion_status, "blocked")

    def test_registered_workspace_deduplicates_retained_root_original(self):
        loose = self.film / "UMD at Rutgers '27.mov"
        loose.write_bytes(b"film")
        workspace = self.film / "2027-maryland-vs-rutgers"
        workspace.mkdir()
        results = reconcile_film.reconcile(self.film, self.vault, self.ledger)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].workspace_slug, "2027-maryland-vs-rutgers")

    def test_lane_c_requires_zero_untranscribed_coverage(self):
        workspace = self.film / "2027-eoy-screens"
        workspace.mkdir()
        index = (self.vault / "dynasties" / "north-carolina" / "film-room" /
                 "captures" / "2027-eoy-final" / "_index.md")
        index.parent.mkdir(parents=True)
        index.write_text("# capture\n## Coverage ledger\nOne screen missing.\n")
        result = reconcile_film.capture_result(self.vault, workspace)
        self.assertEqual(result.content_status, "capture_incomplete")
        self.assertEqual(result.deletion_status, "blocked")
        index.write_text("# capture\n## Coverage ledger\n21 of 21 screens transcribed\n")
        result = reconcile_film.capture_result(self.vault, workspace)
        self.assertEqual(result.content_status, "capture_complete")
        self.assertEqual(result.deletion_status, "delete_ready")

    def test_upload_can_succeed_while_vault_gate_keeps_local_files(self):
        workspace = self.film / "2027-untracked-vs-team"
        workspace.mkdir()
        original = workspace / "source.mov"
        original.write_bytes(b"film bytes")
        digest = hashlib.md5(original.read_bytes()).hexdigest()
        response = {"id": "drive-id", "md5Checksum": digest}
        with mock.patch.object(archive_sweep, "upload", return_value=response):
            ok = archive_sweep.sweep_dir(workspace, dry=False, delete_allowed=False)
        self.assertFalse(ok)
        self.assertTrue(original.exists())
        self.assertTrue((workspace / "drive_upload.json").exists())

    def test_dry_run_never_mutates(self):
        workspace = self.film / "2027-dry-vs-run"
        workspace.mkdir()
        original = workspace / "source.mov"
        original.write_bytes(b"film")
        ok = archive_sweep.sweep_dir(workspace, dry=True, delete_allowed=False)
        self.assertTrue(ok)
        self.assertTrue(original.exists())
        self.assertFalse((workspace / "drive_upload.json").exists())

    def test_complete_game_cannot_delete_while_corpus_is_incomplete(self):
        ready = SimpleNamespace(deletion_status="delete_ready")
        blocked = SimpleNamespace(deletion_status="blocked")
        self.assertFalse(archive_sweep.corpus_delete_ready([ready, blocked]))
        self.assertTrue(archive_sweep.corpus_delete_ready([ready]))

    def test_chart_manifest_includes_fullframe_and_playart(self):
        workspace = self.film / "2027-manifest-vs-test"
        (workspace / "seg").mkdir(parents=True)
        play_rows = ["n,qtr,clock,dd,poss,t_first,t_last,score_l,score_r"]
        for n in range(1, 8):
            pdir = workspace / "film" / f"play{n:03d}"
            pdir.mkdir(parents=True)
            play_rows.append(f"{n},1,5:00,1ST&10,L,{n},{n + 1},0,0")
            for name in ("presnap_seq.jpg", "presnap.jpg", "fullframe.jpg",
                         "playart.jpg", "ghost.jpg", "snap1.jpg", "snap2.jpg",
                         "snap3.jpg", "snap4.jpg", "snap5.jpg", "strip.jpg",
                         "result.jpg"):
                (pdir / name).write_bytes(b"")
        (workspace / "seg" / "plays.csv").write_text("\n".join(play_rows) + "\n")
        script = SCRIPTS / "prep_batches.py"
        proc = subprocess.run(
            [sys.executable, str(script), str(workspace), "Left", "Right"],
            text=True, capture_output=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        manifest = (workspace / "batches" / "batch01.txt").read_text()
        self.assertIn("fullframe.jpg", manifest)
        self.assertIn("playart.jpg", manifest)
        for i in range(1, 6):
            self.assertIn(f"snap{i}.jpg", manifest)
        self.assertNotIn("ghost.jpg", manifest)
        self.assertTrue((workspace / "batches" / "batch02.txt").exists())

    def test_silent_lane_b_can_assemble_without_transcript_file(self):
        workspace = self.film / "2027-silent-vs-film"
        workspace.mkdir()
        self.assertEqual(assemble.load_transcript(str(workspace)), [])

    def test_silent_lane_b_clip_audit_skips_transcript_mentions(self):
        workspace = self.film / "2027-silent-vs-audit"
        workspace.mkdir()
        self.assertFalse((workspace / "transcript.json").exists())
        self.assertEqual(audit_clips.kick_mentions(str(workspace), []), (0, []))

    def test_canonical_chart_uses_poss_source_and_transcript_sidecar(self):
        self.assertIn("poss_src", chart_schema.BASE_COLUMNS)
        self.assertNotIn("transcript", chart_schema.BASE_COLUMNS)

    def test_banner_refinement_does_not_fake_a_formation_adjustment(self):
        rows = [{
            "n": "37",
            "formation_initial": "Shotgun Doubles",
            "v2_off_formation": "Shotgun Doubles",
            "formation": "Shotgun - Wing Trips Wk",
            "presnap_adjust": "none",
        }]
        self.assertEqual(chart_schema.formation_adjustment_candidates(rows), [])

    def test_bad_timeline_snap_lane_refuses_to_overwrite_chart(self):
        workspace = self.film / "2027-bad-snap-vs-lane"
        (workspace / "seg").mkdir(parents=True)
        (workspace / "seg" / "hud_timeline.csv").write_text(
            "t,playclock\n0,5\n1,4\n2,3\n3,\n")
        (workspace / "seg" / "plays.csv").write_text(
            "n,poss,t_first,t_last\n1,L,0,3\n")
        chart = workspace / "plays_charted.csv"
        chart.write_text(
            "n,poss,snap_t,playclock_at_snap,sec_since_prev_snap,tempo\n"
            "1,L,99,22,,normal\n")
        before = chart.read_bytes()
        proc = subprocess.run(
            [sys.executable, str(SCRIPTS / "timeline_snaps.py"), str(workspace)],
            text=True, capture_output=True)
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("REFUSED", proc.stderr)
        self.assertEqual(chart.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
