import hashlib
import json
from pathlib import Path
import struct
import tempfile
import unittest
import zlib

from scripts.generate_organic_blots import organic_png, write_if_unchanged


ROOT = Path(__file__).resolve().parents[1]


class OrganicBlotTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Generate in memory only; never write test stimuli into the archive.
        cls.content = organic_png(314159, "vermilion")

    def test_png_dimensions_color_and_fold_symmetry(self):
        self.assertEqual(self.content[:8], b"\x89PNG\r\n\x1a\n")
        width, height, depth, color, _, _, _ = struct.unpack(">IIBBBBB", self.content[16:29])
        self.assertEqual((width, height, depth, color), (640, 640, 8, 2))
        length = int.from_bytes(self.content[33:37], "big")
        pixels = zlib.decompress(self.content[41:41 + length])
        self.assertEqual(len(pixels), 640 * (640 * 3 + 1))
        row = pixels[320 * 1921 + 1:321 * 1921]
        colors = [row[index:index + 3] for index in range(0, len(row), 3)]
        self.assertEqual(colors, colors[::-1])
        self.assertGreater(len(set(colors)), 50)
        self.assertTrue(any(red > green * 1.3 for red, green, blue in colors))

    def test_seeded_output_matches_versioned_fixture(self):
        # Cross-zlib byte equality is not promised; compare decoded pixels too.
        manifest = json.loads((ROOT / "assets/blots-organic-v1/manifest.json").read_text())
        entry = manifest["stimuli"][1]
        saved = (ROOT / entry["file"]).read_bytes()
        self.assertEqual(hashlib.sha256(saved).hexdigest(), entry["sha256"])
        def decode(content):
            length = int.from_bytes(content[33:37], "big")
            return zlib.decompress(content[41:41 + length])
        self.assertEqual(decode(saved), decode(self.content))
        self.assertEqual(saved, (ROOT / "site" / entry["url"].lstrip('/')).read_bytes())

    def test_modified_outputs_are_not_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "fixture.png"
            write_if_unchanged(path, b"original")
            write_if_unchanged(path, b"original")
            with self.assertRaisesRegex(RuntimeError, "Refusing to overwrite"):
                write_if_unchanged(path, b"changed")
            self.assertEqual(path.read_bytes(), b"original")

    def test_unknown_styles_are_rejected(self):
        with self.assertRaises(ValueError):
            organic_png(1, "unknown")
        with self.assertRaises(ValueError):
            organic_png(1, layout="unknown")

    def test_new_series_has_distinct_compositions_and_verified_public_copies(self):
        manifest = json.loads((ROOT / "assets/blots-organic-v2/manifest.json").read_text())
        self.assertEqual(manifest["generator"], "folded-ink-diverse-v2")
        self.assertEqual({entry["layout"] for entry in manifest["stimuli"]}, {"wide", "vertical", "islands"})
        shapes = {}
        for entry in manifest["stimuli"]:
            content = (ROOT / entry["file"]).read_bytes()
            self.assertEqual(hashlib.sha256(content).hexdigest(), entry["sha256"])
            self.assertEqual(content, (ROOT / "site" / entry["url"].lstrip('/')).read_bytes())
            length = int.from_bytes(content[33:37], "big")
            pixels = zlib.decompress(content[41:41 + length])
            occupied = []
            for y in range(640):
                for x in range(640):
                    offset = y * 1921 + 1 + x * 3
                    if min(pixels[offset:offset + 3]) < 210:
                        occupied.append((x, y))
            width = max(x for x, y in occupied) - min(x for x, y in occupied) + 1
            height = max(y for x, y in occupied) - min(y for x, y in occupied) + 1
            shapes[entry["layout"]] = (width, height, len(occupied))
        self.assertGreater(shapes["wide"][0] / shapes["wide"][1], 1.5)
        self.assertLess(shapes["vertical"][0] / shapes["vertical"][1], .55)
        self.assertLess(shapes["islands"][2], shapes["wide"][2])

    def test_third_series_is_separate_and_has_three_new_layouts(self):
        manifest = json.loads((ROOT / "assets/blots-organic-v3/manifest.json").read_text())
        self.assertEqual(manifest["generator"], "folded-ink-experimental-v3")
        self.assertEqual({entry["layout"] for entry in manifest["stimuli"]}, {"arch", "crescent", "branches"})
        self.assertEqual([entry["id"] for entry in manifest["stimuli"]], ["organic-007", "organic-008", "organic-009"])
        for entry in manifest["stimuli"]:
            content = (ROOT / entry["file"]).read_bytes()
            self.assertEqual(hashlib.sha256(content).hexdigest(), entry["sha256"])
            self.assertEqual(content, (ROOT / "site" / entry["url"].lstrip('/')).read_bytes())
