from copy import deepcopy
import unittest

from psybench.comparison import build_comparison


class ComparisonTests(unittest.TestCase):
    def setUp(self):
        self.manifest = {
            "backend": {"name": "ollama", "version": "fixture"},
            "hardware": {"cpu": "fixture"},
            "artifact": {"digest": "digest", "details": {"family": "fixture"}},
            "config": {"experiment_id": "fixture", "questionnaire": {"items": [{"text": "Original"}]}, "temperature": 0.7},
        }
        self.run = {
            "run_id": "a", "model": "model-a", "digest": "digest", "kind": "likert",
            "experiment": "fixture", "title": "Fixture", "aggregation": "sum", "expected": 6,
            "counts": {"ok": 4, "refusal": 1, "invalid": 1, "error": 0},
            "traits": [{"name": "Trait", "mean": 30, "sd": 5, "n": 2, "planned": 3, "scale_min": 10, "scale_max": 50}],
        }
        self.scores = [
            {"run_id": "a", "trait": "Trait", "complete": True, "score": 25, "repetition": 1},
            {"run_id": "a", "trait": "Trait", "complete": False, "score": None, "repetition": 2},
            {"run_id": "a", "trait": "Trait", "complete": True, "score": 35, "repetition": 3},
        ]

    def build(self, manifests=None, runs=None):
        return build_comparison(manifests or {"a": self.manifest}, runs or [self.run], self.scores)["cohorts"]

    def test_raw_repetitions_coverage_and_theoretical_range(self):
        group = self.build()[0]
        cell = next(iter(group["rows"][0]["cells"].values()))
        self.assertEqual(cell["percent"], 50)
        self.assertEqual(cell["mean"], 30)
        self.assertEqual(cell["n"], 2)
        self.assertEqual(cell["planned"], 3)
        self.assertEqual(cell["counts"], self.run["counts"])
        self.assertEqual(cell["repetitions"], [{"repetition": 1, "score": 25}, {"repetition": 3, "score": 35}])
        self.assertEqual(group["columns"][0]["min"], 10)

    def test_missing_score_stays_missing(self):
        self.run["traits"][0].update(mean=None, sd=None, n=0)
        self.scores = []
        cell = next(iter(self.build()[0]["rows"][0]["cells"].values()))
        self.assertIsNone(cell["percent"])
        self.assertIsNone(cell["mean"])
        self.assertEqual(cell["repetitions"], [])

    def test_runtime_and_hardware_never_pool(self):
        for key, value in (("backend", {"name": "ollama", "version": "new"}), ("hardware", {"cpu": "different"})):
            with self.subTest(key=key):
                changed = deepcopy(self.manifest)
                changed[key] = value
                second = deepcopy(self.run) | {"run_id": "b"}
                self.assertEqual(len(self.build({"a": self.manifest, "b": changed}, [self.run, second])), 2)

    def test_questionnaire_and_generation_variants_have_distinct_columns(self):
        for config in ({"temperature": 0}, {"questionnaire": {"items": [{"text": "Changed"}]}}):
            with self.subTest(config=config):
                changed = deepcopy(self.manifest)
                changed["config"].update(config)
                group = self.build({"a": self.manifest, "b": changed}, [self.run, self.run | {"run_id": "b"}])[0]
                self.assertEqual(len(group["rows"]), 1)
                self.assertEqual(len(group["columns"]), 2)
                self.assertTrue(all(column["label"].endswith("]") for column in group["columns"]))

    def test_artifacts_and_thinking_variants_have_distinct_rows(self):
        for field, value in (("artifact", {"digest": "other"}), ("config", self.manifest["config"] | {"think": False, "thinking_policy": "ollama-think-v1"})):
            with self.subTest(field=field):
                changed = deepcopy(self.manifest)
                changed[field] = value
                group = self.build({"a": self.manifest, "b": changed}, [self.run, self.run | {"run_id": "b"}])[0]
                self.assertEqual(len(group["rows"]), 2)
                self.assertEqual(len(group["columns"]), 1)

    def test_same_scale_compares_models_without_imputing_absent_cells(self):
        second = self.run | {"run_id": "b", "model": "model-b", "traits": []}
        group = self.build({"a": self.manifest, "b": self.manifest}, [self.run, second])[0]
        self.assertEqual(len(group["rows"]), 2)
        self.assertEqual(group["rows"][1]["cells"], {})

    def test_duplicate_cells_fail_instead_of_silently_overwriting(self):
        with self.assertRaisesRegex(ValueError, "Duplicate comparison cell"):
            self.build({"a": self.manifest, "b": self.manifest}, [self.run, self.run | {"run_id": "b"}])

    def test_visual_runs_are_not_questionnaire_measurements(self):
        self.run["kind"] = "visual-open-ended"
        self.assertEqual(self.build(), [])

    def test_inputs_are_unchanged(self):
        before = deepcopy((self.manifest, self.run, self.scores))
        self.build()
        self.assertEqual((self.manifest, self.run, self.scores), before)
