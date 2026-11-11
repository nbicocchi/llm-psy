from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from psybench.stimuli import build_stimuli


class StimulusCatalogTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.digest = hashlib.sha256(b"fixture image").hexdigest()
        path = self.root / "assets/blots-organic-v1"
        path.mkdir(parents=True)
        (path / "one.png").write_bytes(b"fixture image")
        (path / "manifest.json").write_text(json.dumps({
            "generator": "fixture", "width": 640, "height": 640,
            "stimuli": [{"id": "one", "title": "Fixture", "file": "assets/blots-organic-v1/one.png", "sha256": self.digest, "seed": 1}],
        }))
        self.manifest = {"image_hashes": {"one": self.digest}, "artifact": {"digest": "model-digest"},
                         "backend": {"version": "fixture"}, "hardware": {"cpu": "fixture"},
                         "config": {"questionnaire": {"items": [{"id": "one"}]}}}
        self.response = {"run_id": "a", "model": "fixture-model", "experiment": "visual", "item": "one",
                         "image": "assets/stimuli/fixture.png", "repetition": 1, "response": "<Raw & unchanged>",
                         "prompt": "Original prompt", "status": "ok", "error": None}

    def build(self, responses=None, manifests=None):
        responses = responses or []
        runs = [{"run_id": run_id, "expected": 3} for run_id in {response["run_id"] for response in responses}]
        return build_stimuli(self.root, {"runs": runs, "visual": responses}, manifests or {"a": self.manifest})["stimuli"]

    def test_unrun_stimulus_has_image_but_no_invented_observations(self):
        stimulus = self.build()[0]
        self.assertEqual(stimulus["observations"], 0)
        self.assertEqual(stimulus["models"], [])
        self.assertEqual(stimulus["image"], "/assets/blots-organic-v1/one.png")
        self.assertTrue(stimulus["url"].startswith("/stimuli/one-"))

    def test_models_variants_and_repetitions_remain_separate(self):
        second = self.response | {"repetition": 2, "status": "error", "response": "", "error": "technical error"}
        third = self.response | {"run_id": "b"}
        other_model = self.response | {"run_id": "c", "model": "other-model"}
        stimulus = self.build([second, self.response, third, other_model], {"a": self.manifest, "b": self.manifest, "c": self.manifest})[0]
        self.assertEqual(stimulus["model_count"], 2)
        self.assertEqual(stimulus["observations"], 4)
        model = stimulus["models"][0]
        self.assertEqual(len(model["variants"]), 2)
        variant = model["variants"][0]
        self.assertEqual(variant["planned"], 3)
        self.assertEqual(variant["valid"], 1)
        self.assertEqual([r["repetition"] for r in variant["responses"]], [1, 2])
        self.assertEqual(variant["responses"][0]["response"], "<Raw & unchanged>")

    def test_matching_uses_hash_not_reused_item_id(self):
        changed = deepcopy(self.manifest)
        changed["image_hashes"]["one"] = "b" * 64
        stimuli = self.build([self.response], {"a": changed})
        self.assertEqual(len(stimuli), 2)
        current = next(stimulus for stimulus in stimuli if stimulus["sha256"] == self.digest)
        archived = next(stimulus for stimulus in stimuli if stimulus["sha256"] == "b" * 64)
        self.assertEqual(current["observations"], 0)
        self.assertEqual(archived["observations"], 1)
        self.assertNotEqual(current["url"], archived["url"])

    def test_modified_stimulus_is_not_silently_published(self):
        (self.root / "assets/blots-organic-v1/one.png").write_bytes(b"modified")
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            self.build()

    def test_current_repository_has_nineteen_retained_stimuli(self):
        root = Path(__file__).resolve().parents[1]
        stimuli = build_stimuli(root, {}, {})["stimuli"]
        self.assertEqual(len(stimuli), 19)
        self.assertEqual(sum(stimulus["historical"] for stimulus in stimuli), 10)
        self.assertFalse(any(stimulus["id"] in {"blot-001", "blot-002", "blot-003"} for stimulus in stimuli))
