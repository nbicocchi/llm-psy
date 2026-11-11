"""Explicit public snapshots, separate from authoritative local research data."""

from copy import deepcopy
import shutil

from .core import fingerprint, read_json
from .runner import write_json


POLICY = "public-snapshot-v1"


def public_hardware(hardware):
    # Preserve separation without publishing the machine description.
    return {"environment_id": fingerprint(hardware), "details": "Withheld in public snapshot"}


def prepare_publication(root):
    downloads = root / "site/assets/downloads"
    manifests = read_json(downloads / "manifests.json")
    results = read_json(root / "site/_data/results.json")
    comparison = read_json(root / "site/_data/comparison.json")
    public_manifests = {}
    images = {}
    for filename in ("assets/rorschach/manifest.json", "assets/blots-organic-v1/manifest.json",
                     "assets/blots-organic-v2/manifest.json", "assets/blots-organic-v3/manifest.json"):
        path = root / filename
        if path.exists():
            for image in read_json(path)["stimuli"]:
                images[image["sha256"]] = image["file"]
    for run_id, manifest in manifests.items():
        artifact = manifest["artifact"]
        details = artifact.get("details", {})
        public_manifests[run_id] = {
            "run_id": run_id, "model_id": manifest["model_id"], "config": manifest["config"],
            "artifact": {"name": artifact["name"], "digest": artifact["digest"],
                         "details": {key: details[key] for key in ("family", "parameter_size", "quantization_level", "format") if key in details}},
            "backend": manifest["backend"], "hardware": public_hardware(manifest["hardware"]),
            "image_hashes": manifest["image_hashes"],
            "publication": {"policy": POLICY, "identity_note": "Original run ID; redacted metadata cannot independently reproduce its identity hash."},
        }
    results = deepcopy(results)
    for response in results.get("visual", []):
        digest = manifests[response["run_id"]]["image_hashes"][response["item"]]
        if digest not in images:
            raise ValueError(f"No publishable source image for {digest}; review the archived stimulus before publication")
        response["image"] = images[digest]
    comparison = deepcopy(comparison)
    for cohort in comparison["cohorts"]:
        cohort["hardware"] = public_hardware(cohort["hardware"])
    destination = root / "publication"
    write_json(destination / "results.json", results)
    write_json(destination / "comparison.json", comparison)
    write_json(destination / "manifests.json", public_manifests)
    for name in ("scores.csv", "targets.json"):
        shutil.copyfile(downloads / name, destination / name)
    write_json(destination / "publication.json", {
        "policy": POLICY, "raw_responses_available": False, "run_count": len(manifests),
        "notice": "Scores, visual response text and original run IDs are preserved. Hardware details, local model paths, model show metadata, token contexts and complete raw API exports are not published. Public metadata are not the original identity payload. Research outputs may contain offensive content.",
    })
    print(f"Prepared public snapshot: {len(manifests)} runs. Review publication/ before committing.")


def install_publication(root):
    source = root / "publication"
    mapping = {
        "results.json": ("site/_data/results.json", "site/assets/downloads/results.json"),
        "comparison.json": ("site/_data/comparison.json",),
        "manifests.json": ("site/assets/downloads/manifests.json",),
        "scores.csv": ("site/assets/downloads/scores.csv",),
        "targets.json": ("site/assets/downloads/targets.json",),
        "publication.json": ("site/_data/publication.json", "site/assets/downloads/publication.json"),
    }
    # Validate all inputs before replacing any derived outputs.
    for name in mapping:
        if not (source / name).is_file():
            raise ValueError(f"Missing public snapshot file: publication/{name}")
    for name, targets in mapping.items():
        for target in targets:
            destination = root / target
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source / name, destination)
