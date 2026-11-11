import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts.prepare_rorschach import prepare, validate_image


ROOT = Path(__file__).resolve().parents[1]


class RorschachArchiveTests(unittest.TestCase):
    def test_all_ten_local_reproductions_match_provenance(self):
        manifest = json.loads((ROOT / "assets/rorschach/manifest.json").read_text(encoding="utf-8"))
        self.assertEqual([entry["plate"] for entry in manifest["stimuli"]], list(range(1, 11)))
        for entry in manifest["stimuli"]:
            with self.subTest(plate=entry["plate"]):
                content = (ROOT / entry["file"]).read_bytes()
                self.assertEqual(validate_image(content, entry), entry["sha256"])
                public = ROOT / "site/assets/rorschach" / Path(entry["file"]).name
                self.assertEqual(public.read_bytes(), content)
                self.assertEqual(entry["license"], "Public domain")
                self.assertIn("oldid=", entry["source_revision"])

    def test_verify_mode_never_downloads_or_writes(self):
        content = b"\xff\xd8\xfffixture"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "assets/rorschach"
            target.mkdir(parents=True)
            image = target / "plate-01.jpg"
            image.write_bytes(content)
            entry = {"id": "fixture", "file": "assets/rorschach/plate-01.jpg", "bytes": len(content), "commons_sha1": hashlib.sha1(content).hexdigest(), "sha256": hashlib.sha256(content).hexdigest()}
            manifest = target / "manifest.json"
            manifest.write_text(json.dumps({"stimuli": [entry]}))
            before = manifest.read_bytes()
            with patch("scripts.prepare_rorschach.fetch") as fetch:
                prepare(root, verify_only=True)
                fetch.assert_not_called()
            self.assertEqual(before, manifest.read_bytes())
            self.assertFalse((root / "site").exists())

    def test_modified_image_is_rejected(self):
        content = b"\xff\xd8\xfffixture"
        entry = {"id": "fixture", "bytes": len(content), "commons_sha1": hashlib.sha1(content).hexdigest(), "sha256": "wrong"}
        with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
            validate_image(content, entry)
