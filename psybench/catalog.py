"""Website catalog of configured experiments, including those not yet run."""

from .core import load_config, score_bounds, scoring_rule
from .profiles import export_profiles
from .stimuli import export_stimuli
from .runner import write_json


def export_catalog(root):
    models, experiments, _ = load_config(root)
    entries = []
    total_trials = 0
    score_series = 0
    for experiment in experiments:
        q = experiment["definition"]
        traits = []
        if q["kind"] == "likert":
            for name in sorted({item["trait"] for item in q["items"]}):
                items = [item for item in q["items"] if item["trait"] == name]
                low, high = score_bounds(q, len(items))
                traits.append({"name": name, "items": len(items), "min": low, "max": high})
        compatible = [model["id"] for model in models if set(q["requires"]) <= set(model["capabilities"])]
        total_trials += len(compatible) * len(q["items"]) * experiment["repetitions"]
        score_series += len(traits)
        entries.append({
            "id": experiment["id"], "title": q["title"], "kind": q["kind"],
            "items": len(q["items"]), "requires": q["requires"],
            "instruction": q["instruction"], "options": q.get("options", []),
            "item_definitions": [dict(item) for item in q["items"]],
            "repetitions": experiment["repetitions"], "traits": traits,
            "aggregation": scoring_rule(q) if q["kind"] == "likert" else None,
            "models": compatible, "source": q.get("source", ""),
            "source_url": q.get("source_url"), "license": q.get("license", "See the source and methodology; review rights before reuse."),
            "permission_url": q.get("permission_url"), "limitations": q.get("limitations"),
        })
    catalog = {
        "models": models, "experiments": entries, "score_series": score_series,
        "planned_trials": total_trials,
        "text_tests": sum(q["kind"] == "likert" for q in entries),
        "visual_tests": sum(q["kind"] == "visual-open-ended" for q in entries),
    }
    write_json(root / "site/_data/catalog.json", catalog)
    write_json(root / "site/_data/model_profiles.json", export_profiles(root, models, experiments))
    write_json(root / "site/_data/stimuli.json", export_stimuli(root))
    return catalog
