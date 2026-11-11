"""Image-centered catalog joined to saved visual responses by image hash."""

import hashlib
from .core import read_json
from .profiles import model_slug, model_url


def build_stimuli(root, results, manifests):
    entries = {}

    def add(stimulus):
        digest = stimulus["sha256"]
        if digest in entries:
            return entries[digest]
        stimulus = dict(stimulus)
        stimulus["slug"] = model_slug(stimulus["id"]) + "-" + digest[:12]
        stimulus["url"] = "/stimuli/" + stimulus["slug"] + "/"
        stimulus["models"] = {}
        entries[digest] = stimulus
        return stimulus

    for relative, historical in (
        ("assets/blots-organic-v1/manifest.json", False),
        ("assets/blots-organic-v2/manifest.json", False),
        ("assets/blots-organic-v3/manifest.json", False),
        ("assets/rorschach/manifest.json", True),
    ):
        path = root / relative
        if not path.exists():
            continue
        document = read_json(path)
        for item in document["stimuli"]:
            source = root / item["file"]
            if hashlib.sha256(source.read_bytes()).hexdigest() != item["sha256"]:
                raise ValueError(f"Stimulus hash mismatch: {item['file']}")
            add({
                "id": item["id"], "title": f"Rorschach plate {item['plate']}" if historical else item["title"],
                "sha256": item["sha256"], "image": "/" + item["file"],
                "width": item.get("width", document.get("width")), "height": item.get("height", document.get("height")),
                "historical": historical, "series": "Historical Rorschach plates" if historical else document["generator"],
                "source_revision": item.get("source_revision"), "license": item.get("license"),
                "seed": item.get("seed"), "generator": document.get("generator"), "configured": True,
            })

    summaries = {run["run_id"]: run for run in results.get("runs", [])}
    for response in results.get("visual", []):
        manifest = manifests[response["run_id"]]
        digest = manifest["image_hashes"][response["item"]]
        if digest not in entries:
            # Historical versions stay separate even when an item ID is reused.
            add({"id": response["item"], "title": response["item"], "sha256": digest,
                 "image": "/" + response["image"] if response.get("image") else None,
                 "historical": False, "series": "Archived stimulus version", "configured": False})
        stimulus = entries[digest]
        model = stimulus["models"].setdefault(response["model"], {
            "id": response["model"], "url": model_url(response["model"]), "variants": {},
        })
        summary = summaries[response["run_id"]]
        variant = model["variants"].setdefault(response["run_id"], {
            "run_id": response["run_id"], "experiment": response["experiment"],
            "digest": manifest["artifact"]["digest"], "backend": manifest["backend"],
            "hardware": manifest["hardware"], "responses": [],
            "planned": summary["expected"] // len(manifest["config"]["questionnaire"]["items"]),
        })
        variant["responses"].append(dict(response))

    stimuli = []
    for stimulus in entries.values():
        models = []
        for model in stimulus["models"].values():
            variants = []
            for variant in model["variants"].values():
                variant["responses"].sort(key=lambda response: response["repetition"])
                variant["valid"] = sum(response["status"] == "ok" for response in variant["responses"])
                variants.append(variant)
            model["variants"] = sorted(variants, key=lambda variant: variant["run_id"])
            models.append(model)
        stimulus["models"] = sorted(models, key=lambda model: model["id"])
        stimulus["observations"] = sum(len(variant["responses"]) for model in models for variant in model["variants"])
        stimulus["model_count"] = len(models)
        stimuli.append(stimulus)
    stimuli.sort(key=lambda stimulus: (stimulus["historical"], stimulus["id"], stimulus["sha256"]))
    return {"schema_version": 1, "stimuli": stimuli}


def export_stimuli(root):
    results = root / "site/_data/results.json"
    manifests = root / "site/assets/downloads/manifests.json"
    return build_stimuli(root, read_json(results) if results.exists() else {}, read_json(manifests) if manifests.exists() else {})
