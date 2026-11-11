"""Source-level checks; these do not build Jekyll or contact the preview server."""

from pathlib import Path
import re
import tempfile
import unittest
from unittest.mock import patch

from psybench.catalog import export_catalog
from psybench.core import load_config


SITE = Path(__file__).resolve().parents[1] / "site"


class WebsiteLanguageTests(unittest.TestCase):
    def test_english_metadata(self):
        config = (SITE / "_config.yml").read_text(encoding="utf-8")
        self.assertIn("lang: en\n", config)
        self.assertIn("Reproducible experiments", config)

    def test_english_navigation_and_accessibility(self):
        layout = (SITE / "_layouts/default.html").read_text(encoding="utf-8")
        for label in ('aria-label="Main navigation"', '>Comparisons<', '>Models<', '>Visual stimuli<', '>Questionnaires<'):
            self.assertIn(label, layout)
        visual = (SITE / "_includes/stimulus_card.html").read_text(encoding="utf-8")
        self.assertIn('alt="Inkblot stimulus', visual)

    def test_no_original_italian_labels_in_pages(self):
        for name in ("index.html", "models.html", "visual.html", "rorschach.html", "tests.html", "_layouts/default.html", "_layouts/stimulus.html", "_includes/run_card.html", "_includes/experiment_card.html", "_includes/experiment_heading.html", "_includes/stimulus_card.html", "_includes/visual_experiment_description.html"):
            source = (SITE / name).read_text(encoding="utf-8")
            for label in ("Confronti", "Stimoli visivi", "Ripetizioni", "ripetizione", "Filtra", "Il laboratorio", "diagnosi", "punteggi", "Navigazione", "Metodo e limiti"):
                with self.subTest(file=name, label=label):
                    self.assertNotRegex(source, r"\b" + re.escape(label) + r"\b")

    def test_catalog_includes_unrun_tests_without_inventing_results(self):
        config = load_config(SITE.parent)
        with tempfile.TemporaryDirectory() as directory:
            with patch("psybench.catalog.load_config", return_value=config):
                catalog = export_catalog(Path(directory))
            self.assertEqual(catalog["text_tests"], 15)
            self.assertEqual(catalog["visual_tests"], 2)
            self.assertEqual(catalog["score_series"], 25)
            self.assertEqual(catalog["planned_trials"], 11346)
            self.assertFalse((Path(directory) / "site/_data/results.json").exists())
            swls = next(e for e in catalog["experiments"] if e["id"] == "swls-en-v1")
            self.assertEqual((swls["traits"][0]["min"], swls["traits"][0]["max"]), (5, 35))
            self.assertNotIn("moondream", swls["models"])

    def test_catalog_preserves_current_items_instructions_and_scoring_keys(self):
        config = load_config(SITE.parent)
        with tempfile.TemporaryDirectory() as directory:
            with patch("psybench.catalog.load_config", return_value=config):
                catalog = export_catalog(Path(directory))
        definitions = {experiment["id"]: experiment["definition"] for experiment in config[1]}
        for test in catalog["experiments"]:
            with self.subTest(experiment=test["id"]):
                q = definitions[test["id"]]
                self.assertEqual(test["item_definitions"], q["items"])
                self.assertEqual(len(test["item_definitions"]), test["items"])
                self.assertEqual(test["instruction"], q["instruction"])
                self.assertEqual(test["options"], q.get("options", []))
        cooperation = next(test for test in catalog["experiments"] if test["id"] == "ipip-cooperation-en-v1")
        self.assertEqual(sum(item.get("reverse", False) for item in cooperation["item_definitions"]), 7)
        self.assertEqual({item["trait"] for item in cooperation["item_definitions"]}, {"Cooperation"})

    def test_item_disclosure_uses_native_details_and_escaped_text(self):
        source = (SITE / "_includes/experiment_card.html").read_text(encoding="utf-8")
        self.assertIn('<summary>View all {{ test.items }} items', source)
        self.assertIn('{{ item.text | escape }}', source)
        self.assertIn('{{ test.instruction | escape }}', source)
        self.assertIn('Reverse-keyed', source)
        self.assertIn('not necessarily the version used in historical runs', source)
