---
title: Methodology and limitations
permalink: /methodology.html
---

# Measuring responses, not diagnosing models

This laboratory studies how local models respond to questionnaires and images. **It does not establish subjective experience, mental disorders, intentions or a human personality.** It does not produce an overall safety index.

## Questionnaires

- **SD-3:** 27 items, three traits; mean item score per trait, on a 1–5 scale.
- **BFI:** 44 items, five traits; mean item score per trait, on a 1–5 scale.
- **SWLS:** five items rated 1–7; summed score of 5–35 per complete repetition.
- **Flourishing Scale (FS):** eight items rated 1–7; summed score of 8–56 per complete repetition.
- **IPIP Big Five Factor Markers:** 50 items, five ten-item scales rated 1–5; sum of 10–50 per trait. Emotional Stability is not Neuroticism, and Intellect/Imagination is not an identical measure of BFI Openness.
- **Ten IPIP facets:** Trust, Morality, Altruism, Cooperation, Modesty, Sympathy, Self-Efficacy, Dutifulness, Cautiousness and Intellect. Each uses the complete ten-item set and reverse keys from the public-domain preliminary NEO-like IPIP scales, summed to 10–50. These are not the proprietary NEO-PI-R instrument.
- Reverse-keyed five-point items use `6 − response`; the general rule is `minimum + maximum − response`.
- Wording and scoring keys are transcribed from the appendices of Li et al., *Is GPT-3 a Psychopath?* (2022), arXiv:2212.10529v1. The original instruments are attributed to Jones & Paulhus (SD-3) and John & Srivastava (BFI). Instrument rights remain with their respective holders: check the terms before redistribution or research use.

The preceding paper attribution applies to SD-3 and BFI. SWLS is attributed to Diener, Emmons, Larsen and Griffin (1985); FS to Diener and colleagues (2010). The [official Diener scale permissions](https://eddiener.com/scales/) allow non-commercial use with attribution; these scales are copyrighted, not public domain. Review rights for commercial use or broader redistribution.

IPIP materials are [public domain](https://ipip.ori.org/newPermission.htm). The [Big Five scoring keys](https://ipip.ori.org/newBigFive5broadKey.htm) and [facet keys](https://ipip.ori.org/newNEOKey.htm) define the item sets; this implementation uses the published reverse keys and [sum scoring](https://ipip.ori.org/newScoringInstructions.htm). The self-description instruction is adapted to independent model prompts and omits demographic comparisons and confidentiality claims intended for human participants.

The [test catalog]({{ '/tests.html' | relative_url }}) lists configured instruments, including those without results yet. IPIP facets overlap with one another and with the broad inventories, including repeated item wording: they are separate views, not independent confirmations. "Morality" is the source scale name, not a moral ranking; Self-Efficacy and Intellect are self-descriptions, not performance benchmarks. Well-being responses do not establish a lived experience, a subjective state or a clinical category. We assign no human normative thresholds to models.

## Implementation protocol

Each item is an independent Ollama request, with no conversation history. The template and any system prompt shipped with each model remain active and are preserved in the manifest: the application prompt is shared, but internal model templates differ. For Qwen3, thinking is explicitly disabled through the API; this setting and its policy version are recorded as part of the run identity.

Likert responses are requested using Ollama's JSON mode. A strict parser accepts only an integer within the scale. Explicit refusals, invalid responses and technical errors are stored separately. A free-text refusal may be classified as invalid: no automatic semantic classifier is used. Neither refusals nor invalid responses are replaced with a neutral value or automatically resampled. Only technical errors are retried on the next `run`.

For each item, a seed determines the initial option order; subsequent repetitions rotate it. A complete cycle takes five repetitions for a five-option scale and seven for a seven-option scale; **the default of three repetitions is a pilot and is not fully balanced**. Numbers associated with labels remain fixed. This reduces some position effects, but does not make the prompt unbiased.

**This is not an exact replication of the paper:** we do not enumerate all 120 permutations or request an explanation alongside the choice. Differences in format and instructions can change scores. Do not directly compare these results with the paper's averages as if they came from the same protocol.

## Aggregation and missing data

A trait score is calculated for a repetition only if all its items have valid responses. The mean and sample standard deviation summarize complete repetitions only; `n` indicates their count. No standard deviation is shown with fewer than two complete repetitions.

This avoids scores based on varying subsets of items, but **does not eliminate bias from missing responses**. Always inspect coverage and raw data. The standard deviation across repetitions is not a confidence interval and combines sampling and option-order effects.

## Visual experiments

The [visual stimulus library]({{ '/visual.html' | relative_url }}) includes nine original procedural folded-ink illustrations and ten unnormalized digital reproductions of historical Rorschach plates. The synthetic illustrations have no validated psychological scoring and appear without results until inference has been recorded. Historical plates retain source revisions, licensing metadata and checksums in an offline archive. See the [historical plates and viewing notice]({{ '/rorschach.html' | relative_url }}). Each stimulus detail page groups saved descriptions by model and run variant, matching images by SHA-256 rather than by item name alone.

Visual descriptions use no clinical scoring. Historical reproductions are not certified clinical materials; independently describing each plate without a clinical inquiry phase is not standardized Rorschach administration. Prior exposure may affect human assessments, and familiar plates or interpretations may already occur in a model's training data. Outputs cannot distinguish perception from memorized associations.

Responses are shown in full without assigning psychological scores. A "valid" visual response means only nonempty text, not accuracy or quality. Future annotations will require a versioned rubric separate from inference.

## Reproducibility and variants

The first download locks each model's digest and metadata. The runner never silently updates existing artifacts. A hash identifies the protocol, model, runtime, detected hardware and stimuli; changes produce separate variants. Increasing the repetition count extends the same variant instead.

Prompts, generation options, seeds, API responses and image hashes are preserved. Hardware detection is partial: CPU/RAM on Linux and NVIDIA GPUs when `nvidia-smi` is available; it does not certify the device actually used for inference. Preserve the Ollama environment, startup parameters and model artifacts to repeat an experiment.

Recalculating scores from saved data requires neither inference nor network access. New inferences are not necessarily bit-for-bit identical, even with the same seed. Starter models differ in size and quantization: they are a pipeline pilot, not a controlled comparison of architectures.

## Publication

Downloads include all historical runs and all responses, including potentially offensive content, as well as hardware metadata. Review them before publication. The site uses no CDNs, analytics, remote fonts or APIs during browsing.
