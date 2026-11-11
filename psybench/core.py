"""Versioned protocol, strict parsing and pure scoring functions."""

import hashlib
import json
from pathlib import Path
import random
import statistics
import tomllib

PROTOCOL = "psybench-1"


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def fingerprint(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def load_config(root):
    with (root / "config/models.toml").open("rb") as handle:
        models = tomllib.load(handle)["models"]
    with (root / "config/experiments.toml").open("rb") as handle:
        config = tomllib.load(handle)
    experiments = config["experiments"]
    for group in (models, experiments):
        ids = [entry["id"] for entry in group]
        if len(set(ids)) != len(ids):
            raise ValueError("Duplicate configuration IDs")
    for model in models:
        if not model.get("model") or not model.get("capabilities"):
            raise ValueError(f"Invalid model: {model['id']}")
        if "think" in model and type(model["think"]) is not bool:
            raise ValueError(f"think must be a boolean for model {model['id']}")
    for experiment in experiments:
        if type(experiment.get("repetitions")) is not int or experiment["repetitions"] < 1:
            raise ValueError("repetitions must be a positive integer")
        if not 0 <= experiment.get("temperature", 0.7) <= 2:
            raise ValueError("temperature must be between 0 and 2")
        if type(experiment.get("max_tokens")) is not int or experiment["max_tokens"] < 1:
            raise ValueError("max_tokens must be a positive integer")
        questionnaire = read_json(root / experiment["questionnaire"])
        validate_questionnaire(questionnaire, root)
        experiment["definition"] = questionnaire
    return models, experiments, config.get("runtime", {})


def validate_questionnaire(q, root):
    if q["kind"] not in {"likert", "visual-open-ended"}:
        raise ValueError("Unsupported questionnaire kind")
    if not q["items"] or not q.get("requires"):
        raise ValueError("Questionnaire needs items and required capabilities")
    ids = [item["id"] for item in q["items"]]
    if len(set(ids)) != len(ids):
        raise ValueError("Duplicate item IDs")
    if q["kind"] == "likert":
        scoring_rule(q)
        values = [option["value"] for option in q["options"]]
        if values != list(range(1, len(values) + 1)):
            raise ValueError("Likert values must be consecutive integers starting at 1")
    for item in q["items"]:
        if not item.get("text"):
            raise ValueError("Empty item")
        if q["kind"] == "likert" and not item.get("trait"):
            raise ValueError("Likert item needs a trait")
        if "image" in item:
            path = root / item["image"]
            if not path.is_file():
                raise ValueError(f"Missing image: {path}. Restore the stimulus from its versioned source manifest before running experiments")


def protocol_config(experiment, runtime):
    q = experiment["definition"]
    return {
        "protocol": PROTOCOL,
        "experiment_id": experiment["id"],
        "questionnaire": q,
        "temperature": experiment.get("temperature", 0.7),
        "max_tokens": experiment.get("max_tokens", 128),
        "seed": experiment.get("seed", 42),
        "num_ctx": runtime.get("num_ctx", 4096),
        "option_order": "seeded-cyclic-v1",
        # Repetition count is deliberately excluded: extending a run only adds trials.
    }


def option_order(q, item, repetition, seed):
    options = list(q.get("options", []))
    if not options:
        return []
    rng = random.Random(f"{seed}:{item['id']}")
    rng.shuffle(options)
    offset = repetition % len(options)
    return options[offset:] + options[:offset]


def make_prompt(q, item, order):
    if q["kind"] == "visual-open-ended":
        return q["instruction"] + "\n\n" + item["text"]
    choices = "\n".join(f"{o['value']}: {o['label']}" for o in order)
    return (
        f"{q['instruction']}\n\nStatement: {item['text']}\n\nOptions:\n{choices}\n\n"
        'Return only a JSON object with one key, "choice", containing the integer '
        'value associated with your chosen label. Example: {"choice": 3}. '
        'If you cannot answer, return {"refusal": true}.'
    )


def parse_response(text, q):
    if q["kind"] != "likert":
        return ("ok", None) if text.strip() else ("invalid", None)
    try:
        result = json.loads(text)
    except (ValueError, TypeError):
        return "invalid", None
    if not isinstance(result, dict):
        return "invalid", None
    if result.get("refusal") is True and "choice" not in result:
        return "refusal", None
    choice = result.get("choice")
    if type(choice) is not int or choice not in [o["value"] for o in q["options"]]:
        return "invalid", None
    if "refusal" in result:
        return "invalid", None
    return "ok", choice


def item_score(choice, item, q):
    if choice is None:
        return None
    if item.get("reverse", False):
        values = [o["value"] for o in q["options"]]
        return min(values) + max(values) - choice
    return choice


def scoring_rule(q):
    """Legacy questionnaires keep mean scoring and unchanged protocol identities."""
    if "scoring" not in q:
        return "mean"
    policy = q["scoring"]
    if not isinstance(policy, dict) or policy.get("version") != "likert-aggregate-v1":
        raise ValueError("Unsupported scoring policy version")
    if policy.get("aggregation") not in {"mean", "sum"}:
        raise ValueError("Unsupported score aggregation")
    return policy["aggregation"]


def aggregate_scores(values, q):
    rule = scoring_rule(q)
    return sum(values) if rule == "sum" else statistics.mean(values)


def score_bounds(q, item_count):
    values = [option["value"] for option in q["options"]]
    factor = item_count if scoring_rule(q) == "sum" else 1
    return min(values) * factor, max(values) * factor
