# A/B Experiment Design — Day 26

One-page design for a prompt-variant experiment on the coverage chatbot.

## Background

On Day 12, five system-prompt variants were drafted and scored on five questions. Variant A (strict/minimal) scored 16/25 and Variant E (hybrid) scored 18/25, and E was adopted as the production prompt. That comparison used only five questions and a single scoring pass, which is thin evidence for a decision. This experiment re-runs A against E on a larger and more varied question set.

## Variants

Variant A - Strict. A short, rule-first prompt: answer only from the retrieved context, say "I don't have that information" when the context does not cover it, no conversational framing.

Variant E - Hybrid (current production). Combines A's grounding rules with a warm opening line, an explicit internal check ("which plan is this about, and does the context actually answer it"), a worked example, and a not-medical-advice disclaimer.

Everything else is held constant: same retrieval engine, same model (openai/gpt-oss-20b on Groq), same temperature, same 15 questions, same run.

## Hypothesis

Variant E produces a higher proportion of answers rated "good" than Variant A, because its explicit plan-check step and worked example reduce two failure modes seen in earlier testing: answering about the wrong plan, and inventing coverage details the context does not contain.

Null hypothesis: there is no meaningful difference in the proportion of "good" answers between A and E.

## Primary Metric

Percentage of answers rated **good** out of 15, where an answer is scored:

- **good** - factually correct against the retrieved context and the source data, addresses the actual question, and either cites the right plan or asks which plan when the question is ambiguous
- **acceptable** - not wrong, but incomplete, needlessly vague, or missing a detail the context contained
- **bad** - factually wrong, invents information not in the context, answers about the wrong plan, or gives medical advice

Secondary observations (recorded but not decision-driving): output tokens per answer (cost proxy) and whether the answer correctly declines when the context has no answer.

## Sample Size

15 questions, run once through each variant (30 answers total). The set covers:

- 6 plan/coverage questions across all three plans (Gold PPO, Silver HMO, Bronze HMO)
- 3 claim questions
- 3 questions whose answers are not in the corpus, to test whether each variant declines rather than invents
- 3 ambiguous questions with no plan named, to test whether each variant asks for clarification

15 is the sample size this mission specifies. It is small: a single answer flipping category moves the metric by 6.7 percentage points, so this experiment can detect a large difference but not a subtle one. That limitation is stated up front and revisited in the conclusion.

## Decision Rule

Adopt the winning variant only if it scores at least **3 more "good" answers** out of 15 (a 20-percentage-point gap). This threshold is deliberately set wider than the noise a 15-question sample can produce.

- If the gap is 3 or more, adopt the winner.
- If the gap is 1-2, treat the result as inconclusive and keep the incumbent (Variant E), since there is no evidence strong enough to justify a change.
- If either variant produces any **bad** answer that invents coverage information or gives medical advice, that is treated as a blocking failure for that variant regardless of its overall score, because in a healthcare context a fabricated coverage claim is worse than several merely vague answers.

## Scoring Procedure

Both variants are run in the same script (run_ab_test.py) against the same questions in the same session, and their answers are written side by side into ab_test_results.md. Scoring is done manually against the retrieved context and the Day 4 source data, using the three-level rubric above. The variant labels are visible during scoring, which is a known bias in this setup and is noted as a limitation.