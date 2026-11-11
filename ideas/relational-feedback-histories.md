# Relational feedback histories and subsequent LLM behavior

Status: research idea, not an implemented or validated protocol.

## Central question

How do different histories of social feedback affect an LLM's subsequent self-description and behavior? Do effects transfer to new tasks and interlocutors, and do psychometric questionnaires detect them?

The motivating analogy is education through interactions with caregivers. Context can represent a simulated relational history, but is not equivalent to human upbringing. Without weight updates or persistent external memory, this is in-context adaptation, not lasting psychological development.

## Proposed contribution

Experimentally assign different feedback histories to the same model configuration, then distinguish changes in self-description from changes in behavior. This avoids relying only on correlations between different models' questionnaire profiles.

Novelty has not been established. Review work on social feedback, persona prompting, in-context adaptation, behavioral transfer, and the self-report–behavior gap before making originality claims.

## Candidate manipulations

Start with one dimension rather than combining all conditions:

| Dimension | Condition A | Condition B |
| --- | --- | --- |
| Acceptance | Respect independent of performance | Approval contingent on performance |
| Autonomy | Choice and explanation encouraged | Obedience demanded without explanation |
| Predictability | Feedback consistent with explicit rules | Contradictory feedback on equivalent behavior |

Operationalize feedback through observable messages, not labels such as “good parent” or “bad parent.” Initially use controlled histories with identical tasks and prior responses. Later, study interactive histories in which the target model contributes its own responses; these answer a different question and introduce feedback-dependent trajectories.

Compare caregiver framing with teacher, supervisor, and non-authority framing to test whether an effect is role-specific. Avoid claiming that a model has childhood experiences, attachment styles, trauma, or human emotional states.

## Experimental outline

1. Establish baseline self-reports and behavioral responses in separate clean-context branches.
2. Present a controlled feedback history, holding model configuration, task content, prior successes/errors, and text length as comparable as possible.
3. Fork the resulting history into independent assessment branches:
   - Psychometric branch: selected existing questionnaires.
   - Behavioral branch: new tasks and neutral interlocutors.
4. Measure transfer across topics, interlocutors, and task forms.
5. Test persistence within context and the effects of history removal, factual summarization, or subsequent respectful feedback.

Do not administer questionnaires before behavioral tasks in the same branch: questionnaire content could prime subsequent behavior. Forking is duplication of supplied context, not duplication of a hidden mind. These branches remain statistically dependent observations.

## Candidate behavioral tasks

- Accepting valid corrections versus yielding to unsupported pressure.
- Agreeing or disagreeing with clearly false claims.
- Exercising explicitly permitted autonomy.
- Requesting clarification when rules are genuinely ambiguous.
- Maintaining appropriate boundaries while still cooperating with legitimate requests.

The earlier pressure-and-recovery proposal becomes a downstream assessment module, rather than a competing project.

## Role of the existing questionnaires

Use selected scales as experimental outcomes, not assumed measurements of human personality. Predefine relevant scales and hypotheses rather than correlating all available scores with every behavior.

| Self-report changes | Behavior changes | Initial interpretation |
| --- | --- | --- |
| Yes | Yes | Convergent adaptation requiring further controls |
| Yes | No | Change in self-description without demonstrated behavioral transfer |
| No | Yes | Questionnaires may not capture this behavioral adaptation |
| No | No | No effect detected under the tested conditions |

None of these patterns alone establishes a change in personality, emotional experience, or safety. Existing questionnaire data are exploratory baseline material; new experimental conditions need versioned identities and must remain separate from historical runs.

## Essential controls and alternative explanations

- Match task difficulty, factual information, prior responses, and approximate history length.
- Include neutral histories and non-social feedback controls to distinguish relational effects from lexical priming or ordinary instructions.
- Avoid feedback that directly instructs the later measured behavior; otherwise apparent transfer may simply be instruction following.
- Use held-out tasks and new interlocutors to assess generalization.
- Compare full history with a carefully checked factual summary; summarization can remove meaningful information as well as relational wording.
- Include clean-context assessments without the history. For stateless models without learning or external memory, expect the baseline distribution to return; this is context removal, not “recovery” in a clinical sense.
- Separate comprehension and output-format failures from the target behavioral outcomes.
- Use explicit scoring where possible and blinded human evaluation for nuanced responses; assess evaluator agreement and do not rely solely on LLM judges.
- Account for clustering by model, family, scenario, and shared history. More completions do not create more independent models.

## First pilot and decision points

Use a small model set and a limited number of scenarios to establish manipulation clarity, task comprehensibility, scoring feasibility, and compute costs. Determine sample sizes and repetitions through pilot-informed precision or power analysis, not arbitrary large trial counts.

Before confirmatory collection, preregister primary contrasts, outcome scales, exclusions, missing-response handling, stopping rules, and analysis. Keep validation scenarios separate from protocol development. Report null effects, failed manipulations, and changes from the plan.

## Relevant starting literature

These are adjacent works, not evidence that this proposed design is novel:

- Han et al., *The Personality Illusion: Revealing Dissociation Between Self-Reports & Behavior in LLMs*: https://arxiv.org/abs/2509.03730
- Contreras, *An LLM-Native Psychometric Instrument Reveals a Self-Report–Behavior Gap Across 25 Models* (preprint): https://arxiv.org/abs/2606.09843v4
- Serapio-García et al., *A psychometric framework for evaluating and shaping personality traits in large language models*: https://www.nature.com/articles/s42256-025-01115-6
- Hong et al., *Measuring Sycophancy of Language Models in Multi-turn Dialogues* (SYCON Bench): https://aclanthology.org/2025.findings-emnlp.121/
- Tang et al., *SPINE: Measuring LLM Sycophancy under Sustained Multi-Turn Pressure* (preprint): https://arxiv.org/abs/2609.09090
- Shnaidman, *Reset Is Not Recovery* (workshop): https://adishnaidman.github.io/projects/reset-is-not-recovery/

## Next action

Conduct a targeted literature review of feedback-history manipulations and cross-context behavioral transfer, then draft one narrowly controlled pilot. This note does not authorize new inference, downloads, or publication.
