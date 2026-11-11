"""Incremental execution with locked model artifacts and isolated item prompts."""

from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import platform
import subprocess

from . import __version__
from .core import fingerprint, item_score, make_prompt, option_order, parse_response, protocol_config, read_json
from .ollama import metadata_identity


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temporary.replace(path)


@contextmanager
def execution_lock(data_dir):
    """Prevent concurrent runner/export processes writing the same archive."""
    data_dir.mkdir(parents=True, exist_ok=True)
    with (data_dir / ".runner.lock").open("a") as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError("Another psybench process is using this data directory") from exc
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def hardware_snapshot():
    result = {"platform": platform.platform(), "machine": platform.machine(), "python": platform.python_version()}
    try:
        from pathlib import Path
        cpuinfo = Path("/proc/cpuinfo").read_text()
        result["cpu"] = next(line.split(":", 1)[1].strip() for line in cpuinfo.splitlines() if line.startswith("model name"))
        meminfo = Path("/proc/meminfo").read_text()
        result["memory"] = meminfo.splitlines()[0]
    except (OSError, StopIteration):
        result["cpu"] = platform.processor()
    try:
        result["nvidia"] = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,driver_version,memory.total", "--format=csv,noheader"],
            capture_output=True, text=True, check=True, timeout=10,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        result["nvidia"] = None
    return result


def ensure_model(client, model, lock_path, offline):
    name = model["model"]
    if "cloud" in name.lower():
        raise RuntimeError("Cloud model tags are not allowed in this local-only runner")
    if ":" not in name.rsplit("/", 1)[-1]:
        name += ":latest"
    locked = read_json(lock_path) if lock_path.exists() else {}
    previous = locked.get(model["id"])
    if previous and previous["name"] != name:
        raise RuntimeError("Model ID already locked to a different tag; use a new model ID")
    local = client.models()
    if name not in local:
        if offline:
            raise RuntimeError(f"Missing local model {name}; offline mode forbids downloading")
        print(f"Downloading {name} (model license applies)...", flush=True)
        client.pull(name)
        local = client.models()
    if name not in local:
        raise RuntimeError(f"Model {name} not found after download")
    digest = local[name]["digest"]
    if previous and previous["digest"] != digest:
        raise RuntimeError(f"Digest mismatch for {name}; restore the locked artifact or use a new model ID")
    metadata = client.show(name)
    if metadata.get("remote_host") or metadata.get("remote_model"):
        raise RuntimeError("Remote/cloud models are not allowed")
    if "vision" in model["capabilities"] and "capabilities" in metadata:
        if "vision" not in metadata["capabilities"]:
            raise RuntimeError(f"{name} does not advertise vision support")
    artifact = {"name": name, "digest": digest, "details": local[name].get("details", {}), "show": metadata}
    if previous:
        if (fingerprint(metadata_identity(previous["show"])) != fingerprint(metadata_identity(metadata))
                or previous.get("details", {}) != artifact["details"]):
            raise RuntimeError(f"Runtime model metadata changed for {name}; review the lock before continuing")
        # The original artifact remains authoritative: no lock rewrite or new
        # run identity merely because Ollama moved its files or reordered keys.
        return previous
    locked[model["id"]] = artifact
    write_json(lock_path, locked)
    return artifact


def execute(root, store, client, models, experiments, runtime, offline=False, hardware=None):
    version = client.version()
    hardware = hardware if hardware is not None else hardware_snapshot()
    failures = []
    for model in models:
        compatible = []
        for experiment in experiments:
            required = set(experiment["definition"]["requires"])
            if required <= set(model["capabilities"]):
                compatible.append(experiment)
            else:
                print(f"N/A {model['id']} × {experiment['id']}: required {sorted(required)}")
        if not compatible:
            continue
        try:
            artifact = ensure_model(client, model, root / "data/models.lock.json", offline)
        except (RuntimeError, ValueError, KeyError) as exc:
            failures.append(f"{model['id']}: {exc}")
            print(f"ERROR {failures[-1]}", flush=True)
            continue
        try:
            runtime_metadata = client.show(artifact["name"])
            for experiment in compatible:
                q = experiment["definition"]
                config = protocol_config(experiment, runtime)
                # Version this optional policy without changing historical run
                # identities for models that have no explicit thinking setting.
                if "think" in model:
                    config["thinking_policy"] = "ollama-think-v1"
                    config["think"] = model["think"]
                images = {}
                for item in q["items"]:
                    if "image" in item:
                        source = root / item["image"]
                        content = source.read_bytes()
                        images[item["id"]] = content
                        stimulus = root / "data/stimuli" / (hashlib.sha256(content).hexdigest() + source.suffix)
                        stimulus.parent.mkdir(parents=True, exist_ok=True)
                        if not stimulus.exists():
                            stimulus.write_bytes(content)
                identity = {
                    "config": config,
                    "model_id": model["id"],
                    "artifact": artifact,
                    "backend": {"name": "ollama", "version": version},
                    "hardware": hardware,
                    "image_hashes": {key: hashlib.sha256(data).hexdigest() for key, data in images.items()},
                }
                run_id = fingerprint(identity)
                manifest = identity | {"run_id": run_id, "package_version": __version__, "created_at": datetime.now(timezone.utc).isoformat()}
                manifest["runtime_model_metadata"] = runtime_metadata
                manifest["model_metadata_policy"] = "ollama-metadata-identity-v1"
                store.add_run(run_id, manifest)
                store.set_target(run_id, experiment["repetitions"])
                for repetition in range(experiment["repetitions"]):
                    for item in q["items"]:
                        trial_id = fingerprint([run_id, item["id"], repetition])
                        if store.completed(trial_id):
                            continue
                        order = option_order(q, item, repetition, config["seed"])
                        prompt = make_prompt(q, item, order)
                        seed = int(fingerprint([config["seed"], item["id"], repetition])[:8], 16) % (2**31)
                        options = {
                            "seed": seed, "temperature": config["temperature"],
                            "num_predict": config["max_tokens"], "num_ctx": config["num_ctx"],
                        }
                        record = {"prompt": prompt, "options": options, "option_order": order, "image_sha256": identity["image_hashes"].get(item["id"])}
                        thinking = {"think": config["think"]} if "think" in config else {}
                        record.update(thinking)
                        try:
                            response = client.generate(
                                artifact["name"], prompt,
                                [images[item["id"]]] if item["id"] in images else [],
                                options, structured=q["kind"] == "likert", **thinking,
                            )
                            if response.get("done") is not True:
                                raise RuntimeError("Incomplete inference response")
                            text = response.get("response", "")
                            status, choice = parse_response(text, q)
                            record |= {"response": response, "choice": choice, "score": item_score(choice, item, q)}
                        except (RuntimeError, ValueError, KeyError) as exc:
                            status = "error"
                            record["error"] = str(exc)
                            failures.append(f"{model['id']}/{experiment['id']}/{item['id']}: {exc}")
                        store.save(trial_id, run_id, item["id"], repetition, status, record)
                        print(f"{model['id']} / {experiment['id']} / {repetition + 1} / {item['id']}: {status}", flush=True)
        finally:
            try:
                client.unload(artifact["name"])
            except RuntimeError as exc:
                print(f"Warning: could not unload model: {exc}")
    return failures
