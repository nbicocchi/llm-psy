"""Conservative metadata compatibility without touching historical locks."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock

from psybench.ollama import metadata_identity
from psybench.runner import ensure_model


class ModelMetadataTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "models.lock.json"
        self.model = {"id": "fixture", "model": "fixture:1", "capabilities": ["text"]}
        self.metadata = {
            "modified_at": "old", "template": "original", "system": "original system",
            "modelfile": 'FROM /old/blobs/sha256-' + 'a' * 64 + '\nTEMPLATE """original"""\n',
            "parameters": 'temperature 0.6\nstop "first"\nstop "second"',
            "capabilities": ["completion"], "model_info": {"parameters": 100},
        }
        self.artifact = {"name": "fixture:1", "digest": "locked", "details": {"quantization_level": "Q4"}, "show": deepcopy(self.metadata)}
        self.path.write_text(json.dumps({"fixture": self.artifact}))
        self.original = self.path.read_bytes()
        self.client = Mock()
        self.client.models.return_value = {"fixture:1": {"digest": "locked", "details": {"quantization_level": "Q4"}}}
        self.client.show.return_value = self.metadata

    def check(self):
        return ensure_model(self.client, self.model, self.path, offline=True)

    def test_local_changes_preserve_artifact_and_lock_bytes(self):
        self.metadata["modified_at"] = "new"
        self.metadata["modelfile"] = self.metadata["modelfile"].replace('/old/blobs/', '/new/blobs/')
        self.metadata["parameters"] = 'stop     "first"\nstop "second"\ntemperature 0.6'
        self.assertEqual(self.check(), self.artifact)
        self.assertEqual(self.path.read_bytes(), self.original)
        self.client.pull.assert_not_called()

    def test_meaningful_and_unknown_changes_fail_closed(self):
        for key, value in (("template", "changed"), ("system", "changed"),
                           ("parameters", 'temperature 0.9\nstop "first"\nstop "second"'),
                           ("capabilities", ["completion", "vision"]),
                           ("model_info", {"parameters": 200}), ("unknown", True)):
            with self.subTest(key=key):
                changed = deepcopy(self.metadata)
                changed[key] = value
                self.client.show.return_value = changed
                with self.assertRaisesRegex(RuntimeError, "metadata changed"):
                    self.check()
                self.assertEqual(self.path.read_bytes(), self.original)

    def test_blob_hash_and_template_paths_remain_significant(self):
        for old, new in (("a" * 64, "b" * 64), ('original', 'FROM /new/blobs/sha256-' + 'a' * 64)):
            changed = deepcopy(self.metadata)
            changed["modelfile"] = changed["modelfile"].replace(old, new)
            self.assertNotEqual(metadata_identity(changed), metadata_identity(self.metadata))

    def test_repeated_parameter_order_is_preserved(self):
        changed = deepcopy(self.metadata)
        changed["parameters"] = 'temperature 0.6\nstop "second"\nstop "first"'
        self.assertNotEqual(metadata_identity(changed), metadata_identity(self.metadata))

    def test_modelfile_parameter_reordering_preserves_lock(self):
        original = 'TEMPLATE "Question: {{ .Prompt }}\nAnswer:"\nPARAMETER stop first\nPARAMETER stop second\nPARAMETER temperature 0\nLICENSE "license"\n'
        saved = deepcopy(self.artifact)
        saved["show"]["modelfile"] = original
        self.path.write_text(json.dumps({"fixture": saved}))
        before = self.path.read_bytes()
        self.metadata["modelfile"] = original.replace('PARAMETER temperature 0\n', '').replace('PARAMETER stop first', 'PARAMETER temperature 0\nPARAMETER stop first')
        self.assertEqual(self.check(), saved)
        self.assertEqual(self.path.read_bytes(), before)
        for old, new in (("temperature 0", "temperature 1"),
                         ("stop first\nPARAMETER stop second", "stop second\nPARAMETER stop first"),
                         ("Question:", "Changed:")):
            with self.subTest(change=new):
                self.client.show.return_value = {**self.metadata, "modelfile": self.metadata["modelfile"].replace(old, new)}
                with self.assertRaisesRegex(RuntimeError, "metadata changed"):
                    self.check()

    def test_parameter_lines_inside_template_remain_significant(self):
        for quote in ('"', '"""'):
            original = f'TEMPLATE {quote}prompt\nPARAMETER temperature 0\nPARAMETER stop first\n{quote}\n'
            changed = original.replace('PARAMETER temperature 0\nPARAMETER stop first', 'PARAMETER stop first\nPARAMETER temperature 0')
            self.assertNotEqual(metadata_identity({"modelfile": original}),
                                metadata_identity({"modelfile": changed}))

    def test_digest_and_quantization_changes_remain_blocked(self):
        for field, value in (("digest", "different"), ("details", {"quantization_level": "Q8"})):
            with self.subTest(field=field):
                local = deepcopy(self.client.models.return_value)
                local["fixture:1"][field] = value
                self.client.models.return_value = local
                with self.assertRaises(RuntimeError):
                    self.check()
                self.assertEqual(self.path.read_bytes(), self.original)
                self.client.models.return_value = {"fixture:1": {"digest": "locked", "details": {"quantization_level": "Q4"}}}

    def test_normalization_does_not_mutate_raw_metadata(self):
        original = deepcopy(self.metadata)
        metadata_identity(self.metadata)
        self.assertEqual(self.metadata, original)
