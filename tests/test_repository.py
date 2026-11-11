"""Publication defaults and README consistency; no research data are modified."""

from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from psybench.core import load_config


ROOT = Path(__file__).resolve().parents[1]


class RepositoryTests(unittest.TestCase):
    def test_readme_lists_all_current_model_tags(self):
        models, _, _ = load_config(ROOT)
        readme = (ROOT / "README.md").read_text()
        for model in models:
            with self.subTest(model=model["id"]):
                self.assertIn(f'`{model["model"]}`', readme)

    def test_readme_trial_count_matches_configuration(self):
        models, experiments, _ = load_config(ROOT)
        total = sum(len(experiment["definition"]["items"]) * experiment["repetitions"]
                    for model in models for experiment in experiments
                    if set(experiment["definition"]["requires"]) <= set(model["capabilities"]))
        self.assertIn(f"**{total:,} trials**", (ROOT / "README.md").read_text())

    @unittest.skipUnless(shutil.which("git"), "Git is needed to verify ignore semantics")
    def test_private_and_derived_files_are_ignored_but_sources_are_not(self):
        private = [
            "data/results.sqlite3", "data/models.lock.json", "data/stimuli/example.jpg",
            "site/assets/downloads/responses.jsonl", "site/assets/downloads/manifests.json",
            "site/assets/stimuli/example.jpg", "site/_data/results.json", "site/_data/comparison.json",
            "site/_data/model_profiles.json", "site/_data/catalog.json", "site/_data/stimuli.json",
            "site/_data/publication.json",
            "site/_site/index.html", "site/.jekyll-metadata", "site/vendor/bundle/file.rb",
            "site/.bundle/config", "papers/reference.pdf", ".env", ".env.local", "psybench/__pycache__/core.pyc",
        ]
        sources = [
            "README.md", "THIRD_PARTY_NOTICES.md", "papers/README.md", "config/models.toml",
            "questionnaires/bfi.json", "psybench/core.py", "site/Gemfile.lock", ".env.example",
            "assets/rorschach/manifest.json", "site/assets/rorschach/plate-01.jpg",
            "site/_data/rorschach.json",
            ".github/workflows/checks.yml",
            "publication/results.json", "publication/manifests.json", "netlify.toml",
        ]
        with tempfile.TemporaryDirectory() as directory:
            subprocess.run(["git", "init", "--quiet", directory], check=True, capture_output=True)
            shutil.copyfile(ROOT / ".gitignore", Path(directory) / ".gitignore")
            result = subprocess.run(
                ["git", "-C", directory, "-c", "core.excludesFile=/dev/null", "check-ignore", "--stdin"],
                input="\n".join(private + sources) + "\n", capture_output=True, text=True, check=True,
            )
            self.assertEqual(set(result.stdout.splitlines()), set(private))
