"""Rebuild all public artifacts solely from the saved archive, never inference."""

import csv
import json
from pathlib import Path
import shutil
import statistics

from .core import aggregate_scores, item_score, score_bounds, scoring_rule
from .comparison import build_comparison
from .runner import write_json


def export_results(root, store):
    # A normal archive export restores the local, non-public data mode.
    for publication_marker in (root / "site/_data/publication.json", root / "site/assets/downloads/publication.json"):
        if publication_marker.exists():
            publication_marker.unlink()
    runs = store.runs()
    targets = store.targets()
    attempts = store.attempts()
    # Errors remain in raw exports. A later successful retry supersedes an error,
    # but invalid/refusal responses are terminal observations, never resampled.
    latest = {}
    for attempt in attempts:
        latest[attempt["trial_id"]] = attempt
    trials = list(latest.values())
    site = root / "site"
    downloads = site / "assets/downloads"
    downloads.mkdir(parents=True, exist_ok=True)
    with (downloads / "responses.jsonl").open("w", encoding="utf-8") as handle:
        for attempt in attempts:
            handle.write(json.dumps(attempt, ensure_ascii=False, sort_keys=True) + "\n")
    write_json(downloads / "manifests.json", runs)
    write_json(downloads / "targets.json", targets)
    summaries = []
    scores = []
    visual = []
    for run_id, manifest in sorted(runs.items()):
        q = manifest["config"]["questionnaire"]
        selected = [t for t in trials if t["run_id"] == run_id]
        repetitions = targets[run_id]
        base = {
            "run_id": run_id, "model": manifest["model_id"],
            "experiment": manifest["config"]["experiment_id"],
            "digest": manifest["artifact"]["digest"],
            "backend_version": manifest["backend"]["version"],
            "kind": q["kind"], "title": q["title"],
        }
        counts = {status: sum(t["status"] == status for t in selected) for status in ("ok", "invalid", "refusal", "error")}
        summary = base | {"expected": repetitions * len(q["items"]), "counts": counts, "traits": []}
        if q["kind"] == "likert":
            summary["aggregation"] = scoring_rule(q)
            traits = sorted({item["trait"] for item in q["items"]})
            for trait in traits:
                items = [item for item in q["items"] if item["trait"] == trait]
                ids = {item["id"] for item in items}
                complete_scores = []
                for repetition in range(repetitions):
                    valid = [t for t in selected if t["repetition"] == repetition and t["item_id"] in ids and t["status"] == "ok"]
                    complete = len(valid) == len(items)
                    by_id = {item["id"]: item for item in items}
                    value = aggregate_scores([item_score(t["record"]["choice"], by_id[t["item_id"]], q) for t in valid], q) if complete else None
                    scores.append(base | {"trait": trait, "repetition": repetition + 1, "score": value, "aggregation": scoring_rule(q), "valid_items": len(valid), "expected_items": len(items), "complete": complete})
                    if complete:
                        complete_scores.append(value)
                minimum, maximum = score_bounds(q, len(items))
                summary["traits"].append({
                    "name": trait,
                    "mean": statistics.mean(complete_scores) if complete_scores else None,
                    "sd": statistics.stdev(complete_scores) if len(complete_scores) > 1 else None,
                    "n": len(complete_scores), "planned": repetitions,
                    "scale_min": minimum,
                    "scale_max": maximum,
                })
        else:
            items_by_id = {item["id"]: item for item in q["items"]}
            for trial in selected:
                item = items_by_id[trial["item_id"]]
                image = item.get("image")
                public_image = None
                if image:
                    expected_hash = manifest["image_hashes"][trial["item_id"]]
                    # The immutable stimulus copy is made during execution.
                    source = root / "data/stimuli" / (expected_hash + Path(image).suffix)
                    if source.exists():
                        public_image = "assets/stimuli/" + source.name
                        destination = site / public_image
                        destination.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copyfile(source, destination)
                visual.append(base | {"item": trial["item_id"], "repetition": trial["repetition"] + 1, "image": public_image, "image_sha256": manifest["image_hashes"].get(trial["item_id"]), "prompt": trial["record"]["prompt"], "status": trial["status"], "response": trial["record"].get("response", {}).get("response", ""), "error": trial["record"].get("error")})
        summaries.append(summary)
    columns = ["run_id", "model", "experiment", "digest", "backend_version", "kind", "title", "trait", "repetition", "score", "aggregation", "valid_items", "expected_items", "complete"]
    with (downloads / "scores.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(scores)
    results = {"schema_version": 1, "runs": summaries, "visual": visual}
    write_json(site / "_data/results.json", results)
    write_json(downloads / "results.json", results)
    write_json(site / "_data/comparison.json", build_comparison(runs, summaries, scores))
    print(f"Exported {len(runs)} runs, {len(attempts)} attempts → {site}")
    return results
