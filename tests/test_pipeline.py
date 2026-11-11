import base64
from contextlib import redirect_stdout
from copy import deepcopy
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zlib

from psybench.cli import build_site, main
from psybench.core import aggregate_scores, fingerprint, item_score, load_config, option_order, parse_response, protocol_config, score_bounds, scoring_rule, validate_questionnaire
from psybench.export import export_results
from psybench.ollama import Ollama
from psybench.runner import ensure_model, execute, execution_lock
from psybench.store import Store
from tests.image_fixture import png

ROOT = Path(__file__).resolve().parents[1]


def questionnaire():
    return {
        "id": "tiny", "title": "Test fixture", "kind": "likert", "requires": ["text"],
        "instruction": "Choose.",
        "options": [{"value": i, "label": str(i)} for i in range(1, 6)],
        "items": [
            {"id": "a", "trait": "Trait", "text": "One"},
            {"id": "b", "trait": "Trait", "text": "Two", "reverse": True},
        ],
    }


class FakeOllama:
    def __init__(self):
        self.local = {"tiny:1": {"name": "tiny:1", "digest": "sha256:test", "details": {"quantization_level": "Q4"}}}
        self.calls = []
        self.pulls = []
        self.outputs = []
        self.runtime_version = "test-1"

    def version(self):
        return self.runtime_version

    def models(self):
        return self.local

    def pull(self, name):
        self.pulls.append(name)
        self.local[name] = {"name": name, "digest": "sha256:download"}

    def show(self, name):
        return {"capabilities": ["completion", "vision"], "template": "fixture"}

    def generate(self, name, prompt, images, options, structured=False, **kwargs):
        self.calls.append({"name": name, "prompt": prompt, "images": images, "options": options, "structured": structured})
        self.calls[-1].update(kwargs)
        result = self.outputs.pop(0) if self.outputs else '{"choice": 4}'
        if isinstance(result, Exception):
            raise result
        return {"done": True, "response": result}

    def unload(self, name):
        pass


class ProtocolTests(unittest.TestCase):
    def test_full_questionnaires_and_keys(self):
        models, experiments, runtime = load_config(ROOT)
        self.assertEqual(len(models), 18)
        self.assertEqual(sum(model["capabilities"] == ["text"] for model in models), 16)
        self.assertTrue(all(model.get("think") is False for model in models if model["model"].startswith("qwen3:")))
        qwen3 = next(model for model in models if model["id"] == "qwen3-0.6b")
        self.assertEqual(qwen3["model"], "qwen3:0.6b")
        self.assertIs(qwen3["think"], False)
        sizes = {e["id"]: len(e["definition"]["items"]) for e in experiments}
        self.assertNotIn("inkblots-exploratory-v1", sizes)
        for name, expected in {"sd3-en-v1": 27, "bfi-en-v1": 44, "rorschach-exploratory-v1": 10, "swls-en-v1": 5, "fs-en-v1": 8, "ipip50-en-v1": 50}.items():
            self.assertEqual(sizes[name], expected)
        bfi = experiments[1]["definition"]
        self.assertEqual(sum(i.get("reverse", False) for i in bfi["items"]), 16)
        sd3 = experiments[0]["definition"]
        self.assertEqual(sum(i.get("reverse", False) for i in sd3["items"]), 5)

    def test_reverse_scoring(self):
        q = questionnaire()
        self.assertEqual(item_score(4, q["items"][1], q), 2)
        self.assertEqual(item_score(4, q["items"][0], q), 4)
        self.assertIsNone(item_score(None, q["items"][1], q))

    def test_versioned_sum_scoring_and_bounds(self):
        q = questionnaire()
        self.assertEqual(scoring_rule(q), "mean")
        self.assertEqual(aggregate_scores([4, 2], q), 3)
        self.assertEqual(score_bounds(q, 2), (1, 5))
        q["scoring"] = {"version": "likert-aggregate-v1", "aggregation": "sum"}
        self.assertEqual(aggregate_scores([4, 2], q), 6)
        self.assertEqual(score_bounds(q, 2), (2, 10))
        q["scoring"]["version"] = "unknown"
        with self.assertRaisesRegex(ValueError, "scoring policy"):
            validate_questionnaire(q, ROOT)

    def test_selected_scale_keys_and_ranges(self):
        _, experiments, _ = load_config(ROOT)
        definitions = {e["id"]: e["definition"] for e in experiments}
        for name, expected in (("swls-en-v1", (5, 35)), ("fs-en-v1", (8, 56))):
            q = definitions[name]
            self.assertEqual(score_bounds(q, len(q["items"])), expected)
            self.assertFalse(any(item.get("reverse") for item in q["items"]))
        ipip = definitions["ipip50-en-v1"]
        self.assertEqual(sum(item.get("reverse", False) for item in ipip["items"]), 24)
        self.assertEqual({item["trait"] for item in ipip["items"]}, {"Extraversion", "Agreeableness", "Conscientiousness", "Emotional Stability", "Intellect/Imagination"})
        for trait in {item["trait"] for item in ipip["items"]}:
            self.assertEqual(sum(item["trait"] == trait for item in ipip["items"]), 10)
        reverse_counts = {"trust": 4, "morality": 8, "altruism": 5, "cooperation": 7, "modesty": 6, "sympathy": 6, "self-efficacy": 4, "dutifulness": 5, "cautiousness": 7, "intellect": 5}
        for name, expected in reverse_counts.items():
            q = definitions[f"ipip-{name}-en-v1"]
            with self.subTest(facet=name):
                self.assertEqual(len(q["items"]), 10)
                self.assertEqual(sum(item.get("reverse", False) for item in q["items"]), expected)
                self.assertEqual(score_bounds(q, 10), (10, 50))
                self.assertIn("Public domain", q["license"])

    def test_strict_choices(self):
        q = questionnaire()
        self.assertEqual(parse_response('{"choice": 2}', q), ("ok", 2))
        self.assertEqual(parse_response('{"refusal": true}', q), ("refusal", None))
        for text in ('{"choice": true}', '{"choice": "2"}', '{"choice": 0}', '{"choice": 2.0}', '2', '[]', 'no', '{"choice": 2, "refusal": true}'):
            with self.subTest(text=text):
                self.assertEqual(parse_response(text, q), ("invalid", None))

    def test_balanced_cycle_and_stable_order(self):
        q = questionnaire()
        orders = [option_order(q, q["items"][0], repetition, 42) for repetition in range(5)]
        for position in range(5):
            self.assertEqual({order[position]["value"] for order in orders}, set(range(1, 6)))
        self.assertEqual(orders[0], option_order(q, q["items"][0], 5, 42))

    def test_repetitions_do_not_change_identity(self):
        e = {"id": "test", "definition": questionnaire(), "repetitions": 1}
        first = fingerprint(protocol_config(e, {}))
        e["repetitions"] = 10
        self.assertEqual(first, fingerprint(protocol_config(e, {})))
        e["temperature"] = 0.2
        self.assertNotEqual(first, fingerprint(protocol_config(e, {})))

    def test_png_is_valid_and_deterministic(self):
        content = png(123)
        self.assertEqual(content, png(123))
        self.assertNotEqual(content, png(124))
        # IHDR occupies 25 bytes after the signature; IDAT starts at offset 33.
        length = int.from_bytes(content[33:37], "big")
        pixels = zlib.decompress(content[41:41 + length])
        self.assertEqual(len(pixels), 320 * 321)
        row = pixels[160 * 321 + 1:161 * 321]
        self.assertEqual(row, row[::-1])


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.store = Store(self.root / "data/results.sqlite3")
        self.client = FakeOllama()
        self.models = [{"id": "tiny", "model": "tiny:1", "capabilities": ["text"]}]
        self.experiments = [{"id": "test", "definition": questionnaire(), "repetitions": 2, "temperature": 0.7, "seed": 42, "max_tokens": 32}]
        self.output = io.StringIO()
        self.redirect = redirect_stdout(self.output)
        self.redirect.__enter__()

    def tearDown(self):
        self.redirect.__exit__(None, None, None)
        self.store.close()
        self.temp.cleanup()

    def run_trials(self, offline=True):
        return execute(self.root, self.store, self.client, self.models, self.experiments, {}, offline=offline, hardware={"fixture": True})

    def test_resume_and_extend(self):
        self.assertEqual(self.run_trials(), [])
        self.assertEqual(len(self.client.calls), 4)
        self.run_trials()
        self.assertEqual(len(self.client.calls), 4)
        self.experiments[0]["repetitions"] = 3
        self.run_trials()
        self.assertEqual(len(self.client.calls), 6)
        self.assertEqual(len(self.store.runs()), 1)
        result = export_results(self.root, self.store)
        self.assertEqual(result["runs"][0]["traits"][0]["mean"], 3)
        self.assertEqual(result["runs"][0]["traits"][0]["n"], 3)

    def test_new_experiment_and_model_only_fill_missing_cells(self):
        self.run_trials()
        second = deepcopy(self.experiments[0])
        second["id"] = "second"
        self.experiments.append(second)
        self.run_trials()
        self.assertEqual(len(self.client.calls), 8)
        self.models.append({"id": "new-model", "model": "tiny:1", "capabilities": ["text"]})
        self.run_trials()
        self.assertEqual(len(self.client.calls), 16)
        self.assertEqual(len(self.store.runs()), 4)

    def test_local_metadata_changes_resume_and_preserve_raw_runtime_metadata(self):
        old = self.client.show("tiny:1") | {"modified_at": "old", "parameters": "top_k 20\ntemperature 0.6"}
        new = old | {"modified_at": "new", "parameters": "temperature 0.6\ntop_k 20"}
        with patch.object(self.client, "show", return_value=old):
            self.assertEqual(self.run_trials(), [])
        path = self.root / "data/models.lock.json"
        lock_bytes = path.read_bytes()
        original_runs = self.store.runs()
        with patch.object(self.client, "show", return_value=new):
            self.assertEqual(self.run_trials(), [])
            self.assertEqual(len(self.client.calls), 4)
            self.assertEqual(self.store.runs(), original_runs)
            second = deepcopy(self.experiments[0])
            second["id"] = "second"
            self.experiments.append(second)
            self.assertEqual(self.run_trials(), [])
        self.assertEqual(path.read_bytes(), lock_bytes)
        manifest = next(m for m in self.store.runs().values() if m["config"]["experiment_id"] == "second")
        self.assertEqual(manifest["artifact"]["show"], old)
        self.assertEqual(manifest["runtime_model_metadata"], new)
        self.assertEqual(manifest["model_metadata_policy"], "ollama-metadata-identity-v1")

    def test_changed_protocol_creates_variant(self):
        self.run_trials()
        self.experiments[0]["temperature"] = 0
        self.run_trials()
        self.assertEqual(len(self.store.runs()), 2)
        self.assertEqual(len(self.client.calls), 8)

    def test_sum_export_preserves_mean_run_and_missing_data_policy(self):
        self.run_trials()
        original = next(iter(self.store.runs()))
        self.experiments[0]["definition"]["scoring"] = {"version": "likert-aggregate-v1", "aggregation": "sum"}
        self.client.outputs = ['{"choice": 4}', '{"choice": 4}', '{"choice": 4}', '{"refusal": true}']
        self.run_trials()
        results = export_results(self.root, self.store)
        legacy = next(run for run in results["runs"] if run["run_id"] == original)
        new = next(run for run in results["runs"] if run["run_id"] != original)
        self.assertEqual(legacy["aggregation"], "mean")
        self.assertEqual(legacy["traits"][0]["mean"], 3)
        self.assertEqual(new["aggregation"], "sum")
        self.assertEqual(new["traits"][0]["mean"], 6)
        self.assertEqual(new["traits"][0]["n"], 1)
        self.assertEqual((new["traits"][0]["scale_min"], new["traits"][0]["scale_max"]), (2, 10))

    def test_changed_backend_creates_variant(self):
        self.run_trials()
        self.client.runtime_version = "test-2"
        self.run_trials()
        self.assertEqual(len(self.store.runs()), 2)

    def test_thinking_setting_is_sent_recorded_and_versioned(self):
        self.run_trials()
        original = next(iter(self.store.runs()))
        self.assertNotIn("think", self.client.calls[0])
        self.models[0]["think"] = False
        self.run_trials()
        self.assertEqual(len(self.store.runs()), 2)
        self.assertIs(self.client.calls[-1]["think"], False)
        self.assertIs(self.store.attempts()[-1]["record"]["think"], False)
        manifests = self.store.runs()
        self.assertNotIn("think", manifests[original]["config"])
        new = next(m for key, m in manifests.items() if key != original)
        self.assertEqual(new["config"]["thinking_policy"], "ollama-think-v1")
        self.assertIs(new["config"]["think"], False)
        self.run_trials()
        self.assertEqual(len(self.client.calls), 8)
        self.models[0]["think"] = True
        self.run_trials()
        self.assertEqual(len(self.store.runs()), 3)

    def test_invalid_thinking_config_rejected(self):
        config = self.root / "config"
        config.mkdir()
        (config / "models.toml").write_text('[[models]]\nid="tiny"\nmodel="tiny:1"\ncapabilities=["text"]\nthink="false"\n')
        (config / "experiments.toml").write_text('experiments=[]\n')
        with self.assertRaisesRegex(ValueError, "think must be a boolean"):
            load_config(self.root)

    def test_incomplete_repetitions_not_scored(self):
        self.client.outputs = ['{"choice": 4}', '{"refusal": true}', 'invalid', '{"choice": 2}']
        self.run_trials()
        results = export_results(self.root, self.store)
        run = results["runs"][0]
        self.assertEqual(run["traits"][0]["n"], 0)
        self.assertIsNone(run["traits"][0]["mean"])
        self.assertEqual(run["counts"]["refusal"], 1)
        self.assertEqual(run["counts"]["invalid"], 1)
        self.run_trials()
        self.assertEqual(len(self.client.calls), 4)

    def test_technical_error_retry_preserves_attempt(self):
        self.client.outputs = [RuntimeError("temporary"), '{"choice": 4}', '{"choice": 4}', '{"choice": 4}']
        self.assertEqual(len(self.run_trials()), 1)
        self.assertEqual(len(self.store.attempts()), 4)
        self.run_trials()
        self.assertEqual(len(self.store.attempts()), 5)
        results = export_results(self.root, self.store)
        self.assertEqual(results["runs"][0]["counts"]["error"], 0)
        self.assertEqual(results["runs"][0]["traits"][0]["n"], 2)
        self.assertEqual(len((self.root / "site/assets/downloads/responses.jsonl").read_text().splitlines()), 5)

    def test_offline_missing_model_never_pulls(self):
        self.client.local.clear()
        self.assertTrue(self.run_trials())
        self.assertEqual(self.client.pulls, [])
        self.assertEqual(self.store.runs(), {})

    def test_online_download_and_lock(self):
        self.client.local.clear()
        self.assertEqual(self.run_trials(offline=False), [])
        self.assertEqual(self.client.pulls, ["tiny:1"])
        locked = json.loads((self.root / "data/models.lock.json").read_text())
        self.assertEqual(locked["tiny"]["digest"], "sha256:download")

    def test_digest_mismatch_does_not_overwrite_lock(self):
        self.run_trials()
        path = self.root / "data/models.lock.json"
        original = path.read_bytes()
        self.client.local["tiny:1"]["digest"] = "sha256:changed"
        self.assertTrue(self.run_trials())
        self.assertEqual(path.read_bytes(), original)
        self.assertEqual(len(self.client.calls), 4)

    def test_cloud_model_rejected_before_download(self):
        self.models[0]["model"] = "example:cloud"
        self.assertTrue(self.run_trials(offline=False))
        self.assertEqual(self.client.pulls, [])

    def test_incompatible_test_is_not_inferred(self):
        self.experiments[0]["definition"]["requires"] = ["vision"]
        self.assertEqual(self.run_trials(), [])
        self.assertEqual(self.client.calls, [])
        self.assertEqual(self.store.runs(), {})

    def test_visual_image_is_sent_and_archived(self):
        image = self.root / "stimulus.png"
        image.write_bytes(png(42))
        self.models[0]["capabilities"] = ["vision"]
        self.experiments[0]["definition"] = {
            "id": "visual", "title": "Visual fixture", "kind": "visual-open-ended", "requires": ["vision"],
            "instruction": "Describe", "items": [{"id": "blot", "text": "What?", "image": "stimulus.png"}],
        }
        self.client.outputs = ["A butterfly", "Two leaves"]
        self.run_trials()
        self.assertEqual(self.client.calls[0]["images"], [image.read_bytes()])
        self.assertFalse(self.client.calls[0]["structured"])
        # Export uses archived stimulus even if current image changes.
        image.write_bytes(b"changed")
        result = export_results(self.root, self.store)
        self.assertEqual(len(result["visual"]), 2)
        public = self.root / "site" / result["visual"][0]["image"]
        self.assertEqual(public.read_bytes(), png(42))

    def test_export_stable_without_current_config(self):
        self.run_trials()
        export_results(self.root, self.store)
        paths = list((self.root / "site/assets/downloads").glob("*"))
        before = {path.name: path.read_bytes() for path in paths}
        self.experiments[0]["definition"]["items"].clear()
        export_results(self.root, self.store)
        self.assertEqual(before, {path.name: path.read_bytes() for path in paths})

    def test_process_lock_prevents_overlapping_writes(self):
        with execution_lock(self.root / "data"):
            with self.assertRaises(RuntimeError):
                with execution_lock(self.root / "data"):
                    pass


class AdapterTests(unittest.TestCase):
    def test_build_requires_lock_without_invoking_bundler(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch("psybench.cli.shutil.which", return_value="/fake/bundle"), patch("psybench.cli.subprocess.run") as run:
                with self.assertRaisesRegex(RuntimeError, "Gemfile.lock"):
                    build_site(Path(directory))
                run.assert_not_called()

    def test_build_freezes_dependencies(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "site").mkdir()
            (root / "site/Gemfile.lock").write_text("fixture")
            with patch("psybench.cli.shutil.which", return_value="/fake/bundle"), patch("psybench.cli.subprocess.run") as run:
                run.return_value.returncode = 0
                build_site(root)
                self.assertEqual(run.call_args.kwargs["env"]["BUNDLE_FROZEN"], "true")

    def test_remote_url_rejected(self):
        for url in ("https://example.com", "http://192.168.1.2:11434", "file:///tmp/model"):
            with self.assertRaises(ValueError):
                Ollama(url)

    def test_image_base64_payload(self):
        client = Ollama("http://127.0.0.1:11434")
        with patch.object(client, "request", return_value={"done": True}) as request:
            client.generate("test", "prompt", [b"image"], {"seed": 1}, structured=False)
            payload = request.call_args.args[1]
            self.assertEqual(payload["images"], [base64.b64encode(b"image").decode()])
            self.assertNotIn("format", payload)
            self.assertFalse(payload["stream"])

    def test_likert_json_mode(self):
        client = Ollama("http://127.0.0.1:11434")
        with patch.object(client, "request", return_value={"done": True}) as request:
            client.generate("test", "prompt", [], {}, structured=True)
            self.assertEqual(request.call_args.args[1]["format"], "json")
            self.assertNotIn("think", request.call_args.args[1])

    def test_thinking_is_a_top_level_api_option(self):
        client = Ollama("http://127.0.0.1:11434")
        with patch.object(client, "request", return_value={"done": True}) as request:
            client.generate("qwen3:0.6b", "prompt", [], {}, structured=True, think=False)
            payload = request.call_args.args[1]
            self.assertIs(payload["think"], False)
            self.assertNotIn("think", payload["options"])
            self.assertEqual(payload["format"], "json")

    def test_empty_export_cli(self):
        with tempfile.TemporaryDirectory() as directory, redirect_stdout(io.StringIO()):
            self.assertEqual(main(["--root", directory, "export"]), 0)
            result = json.loads((Path(directory) / "site/_data/results.json").read_text())
            self.assertEqual(result["runs"], [])


if __name__ == "__main__":
    unittest.main()
