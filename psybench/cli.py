import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys

from .catalog import export_catalog
from .core import load_config
from .export import export_results
from .ollama import Ollama
from .publication import install_publication, prepare_publication
from .runner import execute, execution_lock
from .store import Store


def build_site(root, public=False):
    if not shutil.which("bundle"):
        raise RuntimeError("Bundler not found. Install Ruby/Bundler and run `bundle install` in site/, or use --no-build")
    if not (root / "site/Gemfile.lock").is_file():
        raise RuntimeError("Missing site/Gemfile.lock. Run `bundle install` in site/ once, or use --no-build")
    if public:
        install_publication(root)
    # Historical exports remain config-independent; this separate catalog
    # describes currently configured tests, including those not yet run.
    if (root / "config/experiments.toml").is_file():
        export_catalog(root)
    # Frozen mode prevents Bundler from resolving/fetching a missing lock during
    # an otherwise offline build. Dependency preparation is always explicit.
    environment = dict(os.environ, BUNDLE_FROZEN="true")
    command = ["bundle", "exec", "jekyll", "build"]
    if public:
        command += ["--config", "_config.yml,_config.public.yml"]
    result = subprocess.run(command, cwd=root / "site", env=environment)
    if result.returncode:
        raise RuntimeError("Jekyll build failed. Results are saved; after fixing dependencies, run `python3 -m psybench build`")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Incremental local model questionnaire experiments")
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="Project root (default: current directory)")
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run", help="Download missing models, run missing trials, export and build Jekyll")
    run.add_argument("--offline", action="store_true", help="Forbid model downloads")
    run.add_argument("--model", action="append", help="Model ID; repeat to select multiple")
    run.add_argument("--experiment", action="append", help="Experiment ID; repeat to select multiple")
    run.add_argument("--no-build", action="store_true", help="Export Jekyll data but skip the Ruby build")
    commands.add_parser("validate", help="Validate all configuration and local stimuli without connecting to Ollama")
    commands.add_parser("export", help="Regenerate CSV/JSON from SQLite, without Ollama or config")
    build = commands.add_parser("build", help="Build Jekyll from previously exported data")
    build.add_argument("--public", action="store_true", help="Use the committed public snapshot, without SQLite or Ollama")
    commands.add_parser("prepare-publication", help="Export the archive and create a redacted snapshot for explicit publication")
    args = parser.parse_args(argv)
    root = args.root.resolve()
    try:
        if args.command == "build":
            build_site(root, public=args.public)
            return 0
        if args.command == "validate":
            models, experiments, _ = load_config(root)
            print(f"Valid: {len(models)} models, {len(experiments)} experiments")
            return 0
        with execution_lock(root / "data"):
            store = Store(root / "data/results.sqlite3")
            try:
                failures = []
                if args.command == "run":
                    models, experiments, runtime = load_config(root)
                    for name, entries, requested in (("model", models, args.model), ("experiment", experiments, args.experiment)):
                        unknown = set(requested or []) - {e["id"] for e in entries}
                        if unknown:
                            raise ValueError(f"Unknown {name} IDs: {', '.join(sorted(unknown))}")
                    models = [m for m in models if not args.model or m["id"] in args.model]
                    experiments = [e for e in experiments if not args.experiment or e["id"] in args.experiment]
                    client = Ollama(runtime.get("url", "http://127.0.0.1:11434"), runtime.get("timeout", 600))
                    failures = execute(root, store, client, models, experiments, runtime, args.offline)
                export_results(root, store)
                if args.command == "prepare-publication":
                    prepare_publication(root)
                if args.command == "run" and not args.no_build:
                    build_site(root)
                if failures:
                    print(f"Completed with {len(failures)} errors. Completed observations are preserved; rerun to retry technical errors.", file=sys.stderr)
                    return 1
            finally:
                store.close()
        return 0
    except (OSError, RuntimeError, ValueError, KeyError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nInterrupted. Completed trials are saved; rerun the same command to resume.", file=sys.stderr)
        return 130
