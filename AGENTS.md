# Working on Local Model Observatory

## Scope and architecture

- Python 3.11+ standard library only for the runner. Entry point: `python3 -m psybench`.
- `config/models.toml` and `config/experiments.toml` are the researcher's entry points.
- Ollama is the only implemented inference adapter. Keep its HTTP details in `psybench/ollama.py`.
- SQLite in `data/` is authoritative; CSV, JSONL and `site/_data/results.json` are derived.
- `site/` is Jekyll with local assets only: no CDN, tracking, remote fonts or runtime API calls.
- All website content must be in English, including metadata, navigation, accessibility labels and empty states. Preserve raw research responses unchanged.
- Runtime support currently targets Linux/macOS (`fcntl` process lock).

## Commands

```bash
python3 scripts/generate_organic_blots.py
python3 -m psybench validate
python3 -m unittest discover -s tests -v
python3 -m psybench run --offline --no-build
python3 -m psybench export
# Within site/, after Ruby dependencies have been installed:
bundle exec jekyll build
```

Do not run actual inference, download models, install dependencies or publish results without explicit user authorization for that step. Tests use fake backends and temporary directories, not the researcher's Ollama instance. Never create invented benchmark results in the real archive or published site data.

## Data integrity

- Never delete, overwrite or reset researcher results, model locks or modified stimuli.
- Attempts are append-only. Technical errors may be retried; refusals and invalid answers are terminal observations.
- Preserve prompts, raw responses, options, image hashes and runtime/model metadata.
- Do not change scoring or prompt semantics without bumping `PROTOCOL` (or a dedicated versioned policy) and adding tests. Historical run configurations must remain interpretable.
- Repetition count is not protocol identity: increasing it adds missing trials.
- Model digests must be checked against the lock, including in offline mode. Do not silently update locks on mismatch.
- Incompatible model/test pairs are N/A, not zero scores. Missing answers never become neutral answers.
- Export must use stored manifests, not current questionnaires, so historical runs stay reproducible.
- Do not pool different runtime/protocol/model variants under one score.
- Legacy Likert questionnaires use mean scoring; new explicit `likert-aggregate-v1` policies support mean or sum and belong to questionnaire identity. Keep displayed score ranges and CSV aggregation labels correct.
- The website catalog is derived from current configuration separately from historical results. Configured tests without inference must not be presented as measured results.

## Scientific interpretation

These are questionnaire-response experiments, not clinical diagnoses or proof of machine personality, well-being, deception or safety. Keep coverage and complete-repetition counts visible. Original synthetic inkblots have no validated psychological scoring. Questionnaire sources and licensing caveats must remain documented. Do not claim an exact replication of the paper: this protocol uses JSON choices and cyclic option orders.

## Verification

Add regression tests for identity/resume behavior, reverse scoring, incomplete runs, errors, lock mismatches, image delivery and exports. Keep test-generated data outside `data/` and `site/_data/`. If Ruby/Ollama is unavailable, state clearly which checks were not performed.
