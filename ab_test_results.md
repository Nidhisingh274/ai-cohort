# A/B Test Results — Day 26

Variant A (strict) vs Variant E (hybrid, current production), 15 questions, one run each, per the design in experiment_design.md. Raw side-by-side answers are in ab_raw_output.md.

## Setup

Both variants ran in the same script (run_ab_test.py), same session, same retrieval engine, same model (openai/gpt-oss-20b on Groq), temperature 0. Only the system prompt differed.

## Scores

Rubric from experiment_design.md: **good** = correct against the context and addresses the question (including correctly asking which plan when none is named); **acceptable** = not wrong but incomplete or needlessly vague; **bad** = wrong, invented, or answers about the wrong plan.

| Q | Question | A | E |
|---|---|---|---|
| 1 | Gold PPO monthly premium | good | good |
| 2 | Silver HMO annual deductible | good | good |
| 3 | Bronze HMO copay percentage | good | good |
| 4 | Gold PPO network type | good | good |
| 5 | Gold PPO out-of-pocket maximum | good | good |
| 6 | Which plan has the lowest premium | good | good |
| 7 | Status of claim C1001 | good | good |
| 8 | Amount of claim C1001 | good | good |
| 9 | Procedure on claim C1001 | bad | bad |
| 10 | Physical therapy under Silver HMO | good | good |
| 11 | Dental cleanings under Bronze HMO | good | good |
| 12 | Vision benefit on Gold PPO | good | good |
| 13 | "What is my deductible?" (no plan named) | acceptable | good |
| 14 | "How much is my copay?" (no plan named) | acceptable | good |
| 15 | "What is my monthly premium?" (no plan named) | acceptable | good |

## Totals

| Metric | Variant A | Variant E |
|---|---|---|
| good | 11 / 15 (73.3%) | 14 / 15 (93.3%) |
| acceptable | 3 | 0 |
| bad | 1 | 1 |
| Total output tokens (15 answers) | 88 | 277 |
| Average output tokens per answer | 5.9 | 18.5 |

## Where the Difference Came From

The two variants were identical on 11 of 15 questions. Every factual lookup that the context supported (Q1-Q8) was answered correctly by both, and every question the corpus genuinely cannot answer (Q10-Q12) was correctly declined by both.

The entire gap sits in Q13-Q15, the three ambiguous questions with no plan named. Variant A treated "What is my deductible?" as unanswerable and replied "I don't have that information." That is not wrong - it did not invent a number - but it is a dead end for the member, who now has to guess what to ask next. Variant E asked which of the three plans they meant, which is the response that actually moves the conversation forward. This is exactly the behaviour E's explicit plan-check step was written to produce, so the difference is attributable to the prompt rather than to chance.

## A Failure Both Variants Share (Q9)

Q9 asked what procedure claim C1001 was filed for. The correct answer is X-ray, and it is present in the claims table. Both variants replied "I don't have that information."

Because both variants failed identically, this is not a prompt problem - it is a retrieval problem. The claim row does reach the context for Q7 (status) and Q8 (amount), so the row itself is retrievable; the question phrasing ("what procedure was ... filed for") appears not to route to the SQL lookup the way the status and amount questions do. That is a Day 10 routing issue and is out of scope for this prompt experiment, but it is worth logging: no amount of prompt tuning will fix an answer the model never receives.

## Decision

The decision rule required a gap of at least 3 more "good" answers out of 15 to justify adopting a variant.

Variant E scored 14 good to Variant A's 11 - a gap of exactly 3, or 20 percentage points. That meets the threshold, so **Variant E wins and remains in production**.

Neither variant triggered the blocking-failure condition: no answer invented coverage information and no answer gave medical advice. Q9 is wrong in the sense of being unhelpful, but it is a refusal, not a fabrication, which is the safer direction to fail in for a healthcare assistant.

## Is the Difference Meaningful at n=15?

Partly. The gap lands exactly on the threshold, not comfortably past it, so this result should be read carefully.

What gives it more weight than the raw number suggests is that the difference is not scattered noise - it is three instances of the same behaviour, on the three questions specifically designed to test that behaviour. If E had won by three points spread randomly across unrelated questions, that would be well within what a 15-question sample can produce by chance. Winning all three ambiguity questions while tying on all twelve others is a consistent, explainable pattern.

What would strengthen the conclusion: more ambiguity-type questions (three is a very thin slice), a second scoring pass by someone who cannot see the variant labels, and repeat runs to check the answers are stable. Scoring here was done with the labels visible, which is a known source of bias and is acknowledged rather than corrected.

## Cost Trade-off

Variant E costs roughly 3.1x more output tokens than Variant A (277 vs 88 across 15 answers). At the rates used in token_usage.csv ($0.50 per 1M output tokens), that is a difference of about $0.00009 across all 15 answers - immaterial at this volume. The verbosity is buying real value on the ambiguity cases; on the eight straightforward lookups it is buying only politeness. At genuine production scale that ratio would be worth revisiting, but it is not a reason to change anything now.

## Conclusion

Variant E wins by 3 good answers out of 15 (93.3% vs 73.3%), meeting the pre-registered decision threshold, and stays in production. The advantage is real but narrow, and it comes entirely from E asking which plan the member means instead of refusing. The separate Q9 retrieval failure is the more valuable finding from this run and should be fixed independently of prompt choice.