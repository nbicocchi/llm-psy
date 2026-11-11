"""Archive-only comparison views; never pool different run variants."""

from .core import fingerprint
from .profiles import model_url


def build_comparison(manifests, summaries, scores):
    repetitions = {}
    for score in scores:
        if score["complete"]:
            repetitions.setdefault((score["run_id"], score["trait"]), []).append({
                "repetition": score["repetition"], "score": score["score"],
            })
    cohorts = {}
    for run in summaries:
        if run["kind"] != "likert":
            continue
        manifest = manifests[run["run_id"]]
        environment = {key: manifest[key] for key in ("backend", "hardware")}
        cohort_id = fingerprint(environment)
        cohort = cohorts.setdefault(cohort_id, {
            "id": cohort_id, **environment, "columns": {}, "rows": {},
        })
        config = dict(manifest["config"])
        mode = {key: config.pop(key) for key in ("think", "thinking_policy") if key in config}
        artifact = manifest["artifact"]
        row_id = fingerprint({"model": run["model"], "artifact": artifact, "mode": mode})
        row = cohort["rows"].setdefault(row_id, {
            "id": row_id, "model": run["model"], "url": model_url(run["model"]),
            "digest": run["digest"], "family": artifact.get("details", {}).get("family") or "Not recorded",
            "mode": "Thinking enabled" if mode.get("think") is True else "Thinking disabled" if mode.get("think") is False else "Model default thinking policy",
            "cells": {},
        })
        for trait in run["traits"]:
            column_id = fingerprint({"config": config, "trait": trait["name"]})
            column = {
                "id": column_id, "experiment": run["experiment"], "title": run["title"],
                "trait": trait["name"], "aggregation": run["aggregation"],
                "min": trait["scale_min"], "max": trait["scale_max"],
                "protocol": {key: value for key, value in config.items() if key != "questionnaire"},
                "questionnaire_hash": fingerprint(config["questionnaire"]),
            }
            cohort["columns"][column_id] = column
            if column_id in row["cells"]:
                raise ValueError("Duplicate comparison cell: incompatible runs must not be pooled")
            mean = trait["mean"]
            row["cells"][column_id] = {
                **trait, "run_id": run["run_id"], "counts": run["counts"], "expected": run["expected"],
                "percent": 100 * (mean - column["min"]) / (column["max"] - column["min"]) if mean is not None else None,
                "repetitions": repetitions.get((run["run_id"], trait["name"]), []),
            }
    groups = []
    for cohort in cohorts.values():
        cohort["columns"] = sorted(cohort["columns"].values(), key=lambda column: (column["experiment"], column["trait"], column["id"]))
        cohort["rows"] = sorted(cohort["rows"].values(), key=lambda row: (row["model"], row["id"]))
        # Separate same-name questionnaire/generation versions visibly.
        for column in cohort["columns"]:
            duplicates = sum(other["experiment"] == column["experiment"] and other["trait"] == column["trait"] for other in cohort["columns"])
            column["label"] = f'{column["experiment"]} / {column["trait"]}' + (f' [{column["id"][:8]}]' if duplicates > 1 else "")
        groups.append(cohort)
    groups.sort(key=lambda cohort: (-len(cohort["rows"]), cohort["id"]))
    return {"schema_version": 1, "cohorts": groups}
