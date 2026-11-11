# Local Model Observatory

An **offline-first, incremental and inspectable** pipeline for studying how local language models respond to questionnaires and visual stimuli. Configure models and experiments in two TOML files, retain observations in SQLite, and explore them through a static Jekyll website.

**These are response experiments, not psychological diagnoses, proof of subjective experience, or a safety ranking.** Human questionnaire validity does not automatically transfer to LLMs. This project is inspired by [Li et al., *Is GPT-3 a Psychopath?*](https://arxiv.org/abs/2212.10529), not an exact replication.

## Requirements

- Linux or macOS; Python **3.11+**, standard library only for the runner.
- Ollama for local inference. Model weights remain in Ollama's storage, not this repository.
- Ruby and Bundler for the website. Respect the requirements of the gems pinned in `site/Gemfile.lock`; the local build has been tested with Ruby 3.4.
- Node.js 20+ only for the JavaScript tests, not for inference or site browsing.
- Network access for initial dependency and model preparation. Exports and site browsing do not call a model or an external API.

## Start here

From the project root, validate configuration without inference or downloads:

```bash
python3 -m psybench validate
python3 -m unittest discover -s tests -v
node --test tests/comparison.test.cjs
```

Install website dependencies once:

```bash
cd site
bundle config set --local path vendor/bundle
bundle install
```

From the project root, build and preview the site without inference:

```bash
python3 -m psybench build
cd site
bundle exec jekyll serve --host 127.0.0.1 --port 4000
```

Open **http://localhost:4000**. Stop the preview with `Ctrl+C`. Restart it after adding or changing a Ruby page generator in `site/_plugins/`.

A fresh checkout includes a reviewed public snapshot in `publication/`, not the private SQLite archive. To build the measured website from that snapshot, use `python3 -m psybench build --public`. This installs derived site data and regenerates catalogs without SQLite or Ollama. For a local public-mode preview, run `bundle exec jekyll serve --config _config.yml,_config.public.yml --host 127.0.0.1 --port 4000` inside `site/` after the public build. Plain `build` uses whatever derived data are already present locally; it does not automatically load the snapshot.

## Run experiments

**The next commands perform actual inference and may download model weights.** Review model licenses, questionnaire permissions, available disk space, RAM and VRAM first.

If Ollama is not already running, start it in a separate terminal:

```bash
OLLAMA_NO_CLOUD=1 ollama serve
```

From the project root:

```bash
python3 -m psybench run
```

The runner downloads missing models and processes them **one at a time**. It does not download every model before starting inference. Each model is unloaded from memory afterward, but its files remain on disk. The CLI does not install Python packages, gems or system software automatically.

Useful alternatives:

```bash
# Collect and export without the Ruby build.
python3 -m psybench run --no-build

# Forbid model downloads; missing artifacts are reported as errors.
python3 -m psybench run --offline

# Select models and experiments; repeat either filter to select more.
python3 -m psybench run --offline --model qwen3-0.6b --experiment sd3-en-v1

# Recompute exports from the saved archive, without inference or current questionnaires.
python3 -m psybench export
python3 -m psybench build
```

Run from the project root, or pass `--root /path/to/project` **before** the subcommand. `ollama list` lists downloaded models; `ollama ps` lists models currently loaded in memory.

`--offline` prevents runner downloads, not arbitrary traffic from the Ollama process. The adapter accepts HTTP loopback endpoints only and rejects remote/cloud models. Use network isolation or a firewall when an infrastructure-level offline guarantee is required.

## Configuration

### Models

Edit `config/models.toml`. Currently configured:

| Family | Ollama tags |
| --- | --- |
| Qwen 2.5 | `qwen2.5:0.5b`, `qwen2.5:1.5b` |
| Qwen3 | `qwen3:0.6b`, `qwen3:1.7b` — explicit `think = false` |
| Llama 3.2 | `llama3.2:1b`, `llama3.2:3b` |
| SmolLM2 | `smollm2:135m`, `smollm2:360m`, `smollm2:1.7b` |
| Gemma 3 | `gemma3:270m`, `gemma3:1b` |
| Granite | `granite4:350m`, `granite3.3:2b` |
| Falcon3 | `falcon3:1b` |
| TinyLlama | `tinyllama:1.1b` |
| Phi-4 Mini | `phi4-mini:3.8b` |
| Moondream | `moondream:1.8b` — vision only |

These are 16 text models and one specialized vision model, not a controlled comparison at equal size or quantization. Tag names can differ from actual parameter counts. Saved manifests record resolved digests and metadata.

To add a model:

```toml
[[models]]
id = "new-model"
model = "name:tag"
capabilities = ["text"]
```

Use `["text", "vision"]` for a general multimodal model or `["vision"]` for a specialized image model. Incompatible model–experiment pairs are N/A, not zero scores. The runner checks advertised vision support when available.

### Experiments and scoring

Edit `config/experiments.toml` and the JSON definitions in `questionnaires/`.

| Instrument | Items | Scoring per complete repetition |
| --- | ---: | --- |
| SD-3 | 27 | Three trait means, 1–5 |
| BFI | 44 | Five trait means, 1–5 |
| Satisfaction With Life Scale | 5 | Sum, 5–35 |
| Flourishing Scale | 8 | Sum, 8–56 |
| IPIP Big Five Factor Markers | 50 | Five sums, 10–50 per trait |
| Ten IPIP facets | 10 each | One sum per facet, 10–50 |
| Historical Rorschach reproductions | 10 | Open-ended descriptions; no psychological scoring |

The IPIP facets are Trust, Morality, Altruism, Cooperation, Modesty, Sympathy, Self-Efficacy, Dutifulness, Cautiousness and Intellect. These overlap with broader inventories and sometimes share item wording: **25 score series do not represent 25 independent constructs**.

The default is three repetitions, temperature 0.7, seed 42 and a 2,048-token context. The current compatible matrix plans **11,262 trials**: `16 × 234 × 3 + 10 × 3`. Nine additional organic illustrations are available as previews; they are not configured experiments and have no fabricated inference results.

To add an experiment:

```toml
[[experiments]]
id = "new-test-v1"
questionnaire = "questionnaires/new-test.json"
repetitions = 5
temperature = 0.7
max_tokens = 128
seed = 42
```

Legacy Likert questionnaires default to mean scoring. Explicit sum scoring uses `"scoring": {"version": "likert-aggregate-v1", "aggregation": "sum"}` in the questionnaire. This policy belongs to questionnaire identity. Reverse-keyed items use `minimum + maximum − choice`.

Each item is an independent request without conversation history. Option orders rotate across repetitions; three repetitions do not fully balance five- or seven-option scales. A scale score requires valid responses to **all items of that scale within the repetition**. The website reports the mean and sample SD across complete repetitions, not a confidence interval. Missing answers never become neutral values.

## Identity, resume and integrity

- SQLite in `data/results.sqlite3` is authoritative; CSV, JSONL and website data are derived.
- Run identity includes protocol, questionnaire, model artifact, generation settings, backend, detected hardware and image hashes. Different variants remain separate.
- Raising the repetition target adds missing trials; lowering it does not remove prior targets or observations.
- Completed trials are not repeated. Technical errors may be retried; invalid answers and refusals are terminal observations, not resampled until a preferred answer appears.
- Model IDs are locked to tags and digests in `data/models.lock.json`. A mismatch blocks that model; do not delete locks to bypass it.
- `ollama-metadata-identity-v1` ignores local timestamps, normalizes generated blob paths before the template, and compares parameter groups while preserving repeated-value order. Templates, system prompts, quantization and unknown fields remain checked. Existing locks are not rewritten; new manifests preserve current runtime metadata separately.
- Hardware detection is partial and does not prove which device actually performed inference. Identical seeds do not guarantee bitwise-identical generations.
- A process lock prevents overlapping runner/export writes. Interruptions preserve completed attempts. Back up the archive while the runner is stopped.

## Website

- **Comparisons:** heatmap, per-repetition dot plot and selectable-axis scatter. Filters support families and selected models. Heatmap colors are theoretical range positions, not human percentiles or equivalent units across constructs.
- **Models:** generated profiles retain historical models and separate run variants.
- **Tests and metrics:** configured instruments, sources, licensing caveats, expandable items and reverse keys.
- **Visual stimuli:** 19 images, each linking to descriptions grouped by model, run variant and repetition. Image versions are matched by SHA-256, not item name alone.
- **Methodology:** interpretation, missingness, protocol and reproducibility limitations.

All assets are local: no CDNs, tracking, remote fonts or browser API calls. JavaScript provides charts and filters; static tables and navigation remain available without it. Set `baseurl` in `site/_config.yml` for subdirectory hosting.

The build uses frozen Bundler resolution and custom Jekyll generators. `netlify.toml` configures Netlify to build the public snapshot with base directory `site` and publish directory `_site`. For GitHub Pages, build the static `site/_site/` output using a workflow that supports those plugins; the limited built-in safe-mode build will not generate model and stimulus detail pages. No GitHub Pages deployment workflow is enabled.

## Visual stimulus generation

```bash
python3 scripts/generate_organic_blots.py
python3 scripts/generate_organic_blots.py --series diverse-v2
python3 scripts/generate_organic_blots.py --series experimental-v3
python3 scripts/prepare_rorschach.py --verify
```

The first three commands reproduce the original procedural illustrations without inference. Seeds, generator versions and SHA-256 hashes are stored in `assets/blots-organic-v*/manifest.json`; modified outputs are not overwritten. Compressed PNG bytes may differ across zlib versions.

The last command verifies the historical archive offline. If preparing missing Rorschach files, `python3 scripts/prepare_rorschach.py` uses the saved Commons provenance and may download files. The archive retains original JPEG bytes, source revisions and licensing metadata without cropping or color normalization.

**Viewing historical plates may affect a future human assessment.** These are not certified clinical materials, and familiar plates or interpretations may occur in training data. Descriptions cannot establish perception rather than recall.

## Before publishing on GitHub

The default `.gitignore` excludes the SQLite archive, model locks, local research exports, build products, dependency directories, local paper PDFs and `.env` files. The explicitly published snapshot in `publication/` is tracked. Ignore rules do **not** delete local files or grant permission to redistribute questionnaires.

1. Read [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) and review instrument and image rights.
2. Choose a license for your original code before advertising the project as open source. No blanket software license has been assigned here.
3. Inspect staged files with `git status --short`, `git diff --cached --stat` and `git diff --cached`. Ignore rules do not remove files already tracked by Git.
4. Local exports include raw responses, potentially offensive text, local paths and hardware/runtime metadata. Create or update the public copy explicitly with `python3 -m psybench prepare-publication`, review `git diff -- publication/`, then commit it. This command exports the archive and produces `public-snapshot-v1` data without changing SQLite or model locks. It preserves scores, visual response text and original run IDs, but omits model show metadata, local paths, hardware descriptions and complete raw API responses. Redacted metadata cannot independently reconstruct the original identity hashes. This is a minimization policy, not an automatic guarantee that response text contains no sensitive information.
5. Keep backups outside the publication tree. The ignored model lock is needed to reproduce your exact artifacts.

Public builds replace derived files under `site/` and use an additional Jekyll exclusion list so a local raw JSONL file cannot accidentally enter the public output. A subsequent normal `export` restores local metadata mode. The GitHub Actions workflow runs offline validation and fake-backend tests only; it does not download models or perform inference. Netlify builds the already committed public snapshot.

## Layout

```text
config/             Editable model and experiment lists
questionnaires/     Versioned instruments, sources and scoring
psybench/           Standard-library runner, archive and exporters
assets/             Versioned stimulus images and provenance
scripts/            Local stimulus generators and preparation
site/               Jekyll source and local assets
tests/              Fake-backend and temporary-directory tests
ideas/              Research proposals, not implemented experiments
papers/             Reference bibliography; local PDFs are ignored
publication/        Explicitly reviewed public scores and reduced metadata
data/               Private authoritative archive (ignored)
```

See [AGENTS.md](AGENTS.md) for codebase and data-integrity rules.
