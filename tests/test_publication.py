from copy import deepcopy
from pathlib import Path
import tempfile
import tomllib
import unittest

from psybench.core import read_json
from psybench.publication import install_publication, prepare_publication
from psybench.runner import write_json


class PublicationTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.hardware = {"cpu": "private-machine", "memory": "private-memory"}
        self.manifest = {
            "model_id": "fixture", "config": {"questionnaire": {"items": [{"id": "image", "text": "Describe"}]}},
            "artifact": {"name": "fixture:1", "digest": "model-sha", "details": {"family": "fixture", "private": "local"},
                         "show": {"modelfile": "FROM /private/model/path"}},
            "backend": {"name": "ollama", "version": "fixture"}, "hardware": self.hardware,
            "runtime_model_metadata": {"modelfile": "/private/path"}, "image_hashes": {"image": "image-sha"},
        }
        self.results = {"runs": [], "visual": [{"run_id": "run", "item": "image", "response": "<Raw response unchanged>", "image": "assets/stimuli/old.jpg"}]}
        write_json(self.root / "site/assets/downloads/manifests.json", {"run": self.manifest})
        write_json(self.root / "site/_data/results.json", self.results)
        write_json(self.root / "site/_data/comparison.json", {"cohorts": [{"id": "original-group", "hardware": self.hardware, "rows": []}]})
        write_json(self.root / "assets/rorschach/manifest.json", {"stimuli": [{"sha256": "image-sha", "file": "assets/rorschach/image.jpg"}]})
        (self.root / "site/assets/downloads/scores.csv").write_text("score\n3\n")
        write_json(self.root / "site/assets/downloads/targets.json", {"run": 3})

    def test_snapshot_preserves_responses_and_ids_without_private_metadata(self):
        original = deepcopy(self.manifest)
        prepare_publication(self.root)
        manifest = read_json(self.root / "publication/manifests.json")["run"]
        self.assertEqual(manifest["run_id"], "run")
        self.assertEqual(manifest["config"], original["config"])
        self.assertEqual(manifest["artifact"]["digest"], "model-sha")
        self.assertNotIn("show", manifest["artifact"])
        self.assertNotIn("private", manifest["artifact"]["details"])
        self.assertNotIn("runtime_model_metadata", manifest)
        self.assertNotIn("cpu", manifest["hardware"])
        result = read_json(self.root / "publication/results.json")["visual"][0]
        self.assertEqual(result["response"], "<Raw response unchanged>")
        self.assertEqual(result["image"], "assets/rorschach/image.jpg")
        cohort = read_json(self.root / "publication/comparison.json")["cohorts"][0]
        self.assertEqual(cohort["id"], "original-group")
        self.assertEqual(cohort["hardware"], manifest["hardware"])
        self.assertEqual(read_json(self.root / "site/assets/downloads/manifests.json")["run"], original)
        self.assertFalse((self.root / "publication/responses.jsonl").exists())

    def test_install_uses_snapshot_without_needing_sqlite(self):
        prepare_publication(self.root)
        install_publication(self.root)
        self.assertTrue((self.root / "site/_data/publication.json").exists())
        self.assertFalse(read_json(self.root / "site/_data/publication.json")["raw_responses_available"])
        self.assertFalse((self.root / "data").exists())

    def test_missing_snapshot_fails_before_changing_outputs(self):
        before = (self.root / "site/_data/results.json").read_bytes()
        with self.assertRaisesRegex(ValueError, "Missing public snapshot"):
            install_publication(self.root)
        self.assertEqual(before, (self.root / "site/_data/results.json").read_bytes())

    def test_unknown_archived_images_require_explicit_review(self):
        (self.root / "assets/rorschach/manifest.json").unlink()
        with self.assertRaisesRegex(ValueError, "No publishable source image"):
            prepare_publication(self.root)

    def test_netlify_build_uses_public_mode_and_raw_files_are_excluded(self):
        root = Path(__file__).resolve().parents[1]
        config = tomllib.loads((root / "netlify.toml").read_text())
        self.assertIn("build --public", config["build"]["command"])
        self.assertEqual(config["build"]["publish"], "_site")
        self.assertIn("assets/downloads/responses.jsonl", (root / "site/_config.public.yml").read_text())
