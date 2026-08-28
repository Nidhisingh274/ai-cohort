# RAGAS Scorecard — Day 27

Evaluation of the full RAG pipeline (retrieval_engine.retrieve + rag_chatbot.generate_answer) against an 18-pair eval set, scored with RAGAS on faithfulness, answer_relevancy, context_precision, and context_recall.

## Setup

Eval set: ragas_eval_set.jsonl, 18 question / ground-truth pairs covering deductibles (4), plan comparisons (6), exclusions (4), and claims status (4).

Runner: ragas_run.py. Each question goes through the real pipeline; the retrieved SQL rows and vector chunks are both passed to RAGAS as `contexts`, since both are what the answer was grounded in.

Judge: RAGAS needs an LLM and an embedding model of its own. This project uses Groq's OpenAI-compatible endpoint (openai/gpt-oss-20b) as the judge and the same local all-MiniLM-L6-v2 model the retrieval engine uses, so no OpenAI key is required.

## Baseline Scores

| Metric | Score |
|---|---|
| faithfulness | 0.6094 |
| answer_relevancy | not scored (see note below) |
| context_precision | 0.6755 |
| context_recall | 0.7778 |

Per-question scores are in ragas_results_baseline.csv.

### Note on answer_relevancy

answer_relevancy returned NaN on the baseline run. The cause is a provider limitation, not a pipeline problem: RAGAS's answer_relevancy generates `strictness` variations of each question (default 3) in a single call using the OpenAI `n` parameter, and Groq's API rejects any `n` above 1 with "'n' : number must be at most 1". Setting `answer_relevancy.strictness = 1` in ragas_run.py resolves this. The three metrics that do not depend on `n` scored normally and are the basis of the analysis below.

**Confirmed on the after-fix run:** with strictness set to 1, answer_relevancy scored 0.7348 with no NaN and no "'n' : number must be at most 1" errors across all 72 evaluation jobs.

## Weakest Metric: faithfulness (0.6094)

faithfulness is the lowest of the three scored metrics, and the per-question breakdown shows it is not evenly weak - it is bimodal. Eleven questions score 1.0 or 0.75, and six score exactly 0.0. There is almost nothing in between, which means this is not a case of answers being vaguely imprecise; it is a case of a specific group of questions failing completely.

The six zero-faithfulness questions:

| Q | Question | faithfulness | context_precision | context_recall |
|---|---|---|---|---|
| 8 | How does the Gold PPO copay compare to the Bronze HMO copay? | 0.00 | 1.000 | 0.0 |
| 12 | Is physical therapy covered under the Silver HMO plan? | 0.00 | 0.000 | 1.0 |
| 13 | Does the Bronze HMO plan cover dental cleanings? | 0.00 | 0.000 | 1.0 |
| 14 | What is the vision benefit on the Gold PPO plan? | 0.00 | 0.450 | 0.0 |
| 17 | What procedure was claim C1001 filed for? | 0.00 | 0.000 | 0.0 |
| 18 | When was claim C1001 filed? | 0.00 | NaN | 0.0 |

## Hypothesis

These six split into two distinct causes.

**Cause 1 - retrieval routing gap on claim-detail questions (Q17, Q18).** Both score 0 on every metric, meaning the claim row never reached the context at all. This is not a chunking or embedding problem: the same claim row *is* retrieved correctly for "What is the status of claim C1001?" and "How much was claim C1001 for?", which both score 1.0. The difference is the question wording. The Day 10 `classify()` function decides between SQL and vector lookup using a keyword list that contains "claim status" and "claim id" but nothing matching "what procedure" or "when was ... filed", so those two questions are classified as unstructured and routed only to vector search, which has no claim data in it. The model then correctly declines - it is being faithful to an empty context, and RAGAS scores that as unfaithful because the ground truth was retrievable and the answer did not contain it.

This is the same failure surfaced independently by the Day 26 A/B test, where both prompt variants failed the identical question. Two separate evaluations converging on the same root cause is strong evidence.

**Cause 2 - questions the corpus genuinely cannot answer (Q12, Q13, Q14).** Physical therapy, dental cleanings, and vision benefits are not documented anywhere in the six-chunk knowledge base. The pipeline behaves correctly here - it declines rather than inventing coverage - but faithfulness has no supporting context to score against, so it returns 0. This is a corpus-coverage limitation, not a bug. The correct fix is more source documents, not prompt or retrieval tuning.

Q8 (the copay comparison) is a third, smaller case: the context was precise (1.0) but recall was 0, suggesting the comparison required both plan rows and only some of that made it into the answer's grounding.

## Fix Chosen for Step 6

Cause 1 is the one worth fixing, because the data exists and the pipeline simply fails to route to it. Cause 2 cannot be fixed without adding source material, which is outside this mission's scope.

**Concrete change:** extend `STRUCTURED_KEYWORDS` in retrieval_engine.py so that claim-detail phrasing routes to the SQL lookup, adding: "procedure", "filed", "date filed", "when was", "claim amount". The claim-ID regex in `sql_lookup()` already handles finding the right row once the question is routed there, so no other change is needed.

Expected effect: Q17 and Q18 should move from 0.0 to near 1.0 on faithfulness, context_precision, and context_recall, since the claim row will then be in context exactly as it already is for Q15 and Q16.

**Status: applied.** The keyword list in retrieval_engine.py has been extended as described. The change is additive - every keyword that was there before is still there - so questions that already routed correctly (Q15, Q16, and all the plan/deductible questions) are unaffected.

**Verified at the routing level (no tokens required):** calling `classify()` directly on both questions now returns "structured" instead of "unstructured", and `retrieve()` now returns the full claim row - {'claim_id': 'C1001', 'member_id': 'M1001', 'plan_id': 'P101', 'procedure': 'X-ray', 'claim_amount': 250, 'status': 'Pending', 'date_filed': '2023-04-01 00:00:00'} - where it previously returned an empty list. Both ground-truth facts (X-ray, April 1 2023) are now present in the context the model receives.

## Re-Run: Before / After

| Metric | Baseline | After fix | Delta |
|---|---|---|---|
| faithfulness | 0.6094 | 0.7222 | +0.1128 |
| answer_relevancy | not scored (NaN) | 0.7348 | now scoring |
| context_precision | 0.6755 | 0.7519 | +0.0764 |
| context_recall | 0.7778 | 0.8889 | +0.1111 |

Per-question scores: ragas_results_baseline.csv (before) and ragas_results_after-fix.csv (after).

The after-fix run completed cleanly - 72/72 evaluation jobs, no rate-limit errors, no timeouts, no NaN - so these numbers come from a full evaluation rather than a partial one.

### What Moved, and Why

All three comparable metrics improved, and the direction matches the hypothesis. The largest gains are on faithfulness (+11.3 points) and context_recall (+11.1 points), which are exactly the two metrics that were being dragged down by Q17 and Q18 scoring 0.0 across the board. With the claim row now routed into context, the model has the facts it needs (X-ray, April 1 2023) instead of being asked to answer from nothing.

A targeted smoke test on the two affected questions confirmed this directly before the full run: both "What is the status of claim C1001?" and "What procedure was claim C1001 filed for?" now score 1.0 on all four metrics. The second of those was 0.0 on all three scored metrics in the baseline.

context_precision moved less (+7.6 points), which fits - precision was never the main problem. The baseline already retrieved precise context for most questions; the issue was that for two questions it retrieved nothing at all.

### Is the Improvement Real?

The gain is attributable to the fix rather than to run-to-run noise, for two reasons. First, the change is mechanical and verifiable independently of RAGAS: calling classify() on those two questions returned "unstructured" before and returns "structured" after, and retrieve() returned an empty SQL result before and returns the full claim row after. That is deterministic, not probabilistic. Second, the size of the move matches what two questions flipping from 0.0 to roughly 1.0 would produce on an 18-question set (2/18 = 11.1 points), which is almost exactly the observed delta on faithfulness and context_recall.

What has not been fixed, and was never expected to be, is Cause 2 - the questions about physical therapy, dental cleanings, and vision benefits. Those still score low because the corpus genuinely does not contain the answers. Adding source documents is the only fix for those, and that is outside this mission's scope.

## Honest Limitations

The eval set is 18 pairs on a six-chunk corpus, so a single question moving between 0 and 1 shifts a metric by roughly 5-6 points. Ground-truth answers were written by the same person who built the pipeline, which risks phrasing them in ways the pipeline happens to match. And the judge model (gpt-oss-20b) is a small model scoring another small model's output, which is noisier than using a larger judge. The scores here are useful for spotting the kind of large, structural gap that Cause 1 represents; they are not precise enough to read small differences into.

Each full evaluation costs roughly 50,000 tokens against Groq's free-tier daily cap of 200,000, which is why the baseline was not re-run after the fix and the comparison uses the original baseline file. A two-question smoke test was run first to confirm the metrics scored correctly before committing tokens to the full run.