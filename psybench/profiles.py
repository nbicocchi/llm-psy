"""Model pages derived from configuration and immutable recorded manifests."""

import hashlib
import re

from .core import fingerprint, read_json


def model_slug(model_id):
    if re.fullmatch(r"[a-z0-9]+(?:[._-][a-z0-9]+)*", model_id):
        return model_id
    readable = re.sub(r"[^a-z0-9]+", "-", model_id.lower()).strip("-")[:60] or "model"
    return readable + "--" + hashlib.sha256(model_id.encode()).hexdigest()[:12]


def model_url(model_id):
    return f"/models/#{model_slug(model_id)}"


def build_profiles(models, experiments, results, manifests):
    configured = {model["id"]: model for model in models}
    ids = sorted(set(configured) | {run["model"] for run in results.get("runs", [])})
    profiles = []
    for model_id in ids:
        config = configured.get(model_id)
        runs = [run for run in results.get("runs", []) if run["model"] == model_id]
        visual = [row for row in results.get("visual", []) if row["model"] == model_id]
        counts = {status: sum(run["counts"].get(status, 0) for run in runs) for status in ("ok", "invalid", "refusal", "error")}
        expected = sum(run["expected"] for run in runs)
        artifacts = {}
        for run in runs:
            manifest = manifests.get(run["run_id"], {})
            artifact = manifest.get("artifact", {})
            details = artifact.get("details", {})
            digest = run["digest"]
            if digest not in artifacts:
                artifacts[digest] = {
                    "digest": digest, "tag": artifact.get("name"),
                    "parameters": details.get("parameter_size"),
                    "quantization": details.get("quantization_level"),
                    "family": details.get("family"), "format": details.get("format"),
                    "backend_versions": [],
                }
            version = run.get("backend_version")
            if version and version not in artifacts[digest]["backend_versions"]:
                artifacts[digest]["backend_versions"].append(version)
        coverage = []
        if config:
            for experiment in experiments:
                q = experiment["definition"]
                compatible = set(q["requires"]) <= set(config["capabilities"])
                historical = [run for run in runs if run["experiment"] == experiment["id"]]
                known = [run for run in historical if "questionnaire" in manifests.get(run["run_id"], {}).get("config", {})]
                matching = [run for run in known if fingerprint(manifests[run["run_id"]]["config"]["questionnaire"]) == fingerprint(q)]
                # "Recorded" only asserts questionnaire-version coverage, not
                # complete trials or matching runtime/generation settings.
                if not compatible:
                    status = "Not applicable"
                elif matching:
                    status = "Recorded"
                elif historical and len(known) != len(historical):
                    status = "Version not verified"
                else:
                    status = "Other versions only" if historical else "Not run"
                coverage.append({
                    "id": experiment["id"], "title": q["title"], "status": status,
                    "matching_runs": len(matching), "historical_runs": len(historical),
                    "planned_trials": len(q["items"]) * experiment["repetitions"] if compatible else None,
                })
        profiles.append({
            "id": model_id, "slug": model_slug(model_id), "url": model_url(model_id),
            "configured": config is not None,
            "tag": config.get("model") if config else None,
            "capabilities": config.get("capabilities", []) if config else [],
            "think": config.get("think") if config else None,
            "runs": runs, "visual": visual, "counts": counts,
            "expected": expected,
            "pending": max(0, expected - sum(counts.values())),
            "recorded_experiments": len({run["experiment"] for run in runs}),
            "artifacts": list(artifacts.values()), "coverage": coverage,
        })
    return {"schema_version": 1, "models": profiles}


def export_profiles(root, models, experiments):
    result_path = root / "site/_data/results.json"
    manifest_path = root / "site/assets/downloads/manifests.json"
    results = read_json(result_path) if result_path.exists() else {}
    manifests = read_json(manifest_path) if manifest_path.exists() else {}
    return build_profiles(models, experiments, results, manifests)
