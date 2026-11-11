from copy import deepcopy
import unittest

from psybench.profiles import build_profiles, model_slug, model_url


class ModelProfileTests(unittest.TestCase):
    def setUp(self):
        self.models = [{"id": "tiny:fixture", "model": "tiny:1", "capabilities": ["text"], "think": False}]
        self.q = {"kind": "likert", "title": "Fixture", "requires": ["text"], "items": [{"id": "one", "text": "Original"}]}
        self.experiments = [{"id": "test", "definition": self.q, "repetitions": 3}]
        self.run = {"run_id": "run-a", "model": "tiny:fixture", "experiment": "test", "digest": "digest-a", "backend_version": "test-1", "expected": 3, "kind": "likert", "counts": {"ok": 1, "invalid": 0, "refusal": 1, "error": 0}, "traits": []}
        self.manifest = {"config": {"questionnaire": deepcopy(self.q)}, "artifact": {"name": "tiny:1", "details": {"parameter_size": "123M", "quantization_level": "Q4", "family": "fixture", "format": "gguf"}}}

    def profiles(self, runs=None, manifests=None, visual=None):
        return build_profiles(self.models, self.experiments, {"runs": runs or [], "visual": visual or []}, manifests or {})["models"]

    def test_configured_unrun_model_has_no_invented_artifacts(self):
        profile = self.profiles()[0]
        self.assertTrue(profile["configured"])
        self.assertEqual(profile["artifacts"], [])
        self.assertEqual(profile["expected"], 0)
        self.assertEqual(profile["coverage"][0]["status"], "Not run")
        self.assertIs(profile["think"], False)

    def test_saved_metadata_coverage_and_pending_trials(self):
        profile = self.profiles([self.run], {"run-a": self.manifest})[0]
        self.assertEqual(profile["coverage"][0]["status"], "Recorded")
        self.assertEqual(profile["coverage"][0]["planned_trials"], 3)
        self.assertEqual(profile["pending"], 1)
        self.assertEqual(profile["counts"]["refusal"], 1)
        self.assertEqual(profile["artifacts"][0]["quantization"], "Q4")

    def test_historical_model_survives_removal_from_configuration(self):
        self.models = []
        profile = self.profiles([self.run], {"run-a": self.manifest})[0]
        self.assertFalse(profile["configured"])
        self.assertIsNone(profile["tag"])
        self.assertEqual(profile["coverage"], [])
        self.assertEqual(profile["artifacts"][0]["tag"], "tiny:1")

    def test_variants_are_not_merged_or_hidden(self):
        second = deepcopy(self.run)
        second.update(run_id="run-b", digest="digest-b", backend_version="test-2")
        profile = self.profiles([self.run, second], {"run-a": self.manifest, "run-b": self.manifest})[0]
        self.assertEqual(len(profile["runs"]), 2)
        self.assertEqual(len(profile["artifacts"]), 2)
        self.assertEqual(profile["coverage"][0]["matching_runs"], 2)
        self.assertEqual(profile["recorded_experiments"], 1)

    def test_modified_questionnaire_does_not_claim_matching_coverage(self):
        self.q["items"][0]["text"] = "Changed"
        profile = self.profiles([self.run], {"run-a": self.manifest})[0]
        self.assertEqual(profile["coverage"][0]["status"], "Other versions only")
        self.assertEqual(len(profile["runs"]), 1)

    def test_missing_manifest_is_explicitly_unverified(self):
        profile = self.profiles([self.run])[0]
        self.assertEqual(profile["coverage"][0]["status"], "Version not verified")
        self.assertIsNone(profile["artifacts"][0]["quantization"])

    def test_incompatible_experiment_has_no_zero_score_or_trial_target(self):
        self.q["requires"] = ["vision"]
        profile = self.profiles()[0]
        self.assertEqual(profile["coverage"][0]["status"], "Not applicable")
        self.assertIsNone(profile["coverage"][0]["planned_trials"])

    def test_visual_results_are_model_specific(self):
        rows = [{"model": "tiny:fixture", "response": "Keep this exact text"}, {"model": "other", "response": "Not this model"}]
        profile = self.profiles(visual=rows)[0]
        self.assertEqual(profile["visual"], [rows[0]])

    def test_safe_stable_urls_and_distinct_normalization(self):
        self.assertEqual(model_url("qwen3-0.6b"), "/models/#qwen3-0.6b")
        ids = ["a/b", "a b", "A B", "../escape", "模型", "a-b"]
        slugs = [model_slug(name) for name in ids]
        self.assertEqual(len(set(slugs)), len(ids))
        for name, slug in zip(ids, slugs):
            self.assertNotIn("/", slug)
            self.assertNotIn("..", slug)
            self.assertEqual(slug, model_slug(name))
