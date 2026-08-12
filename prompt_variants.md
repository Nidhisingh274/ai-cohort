# Prompt Variants — Day 12

Five system-prompt variants were drafted, then run against the same 5
test questions using the production RAG pipeline (`retrieve` + Groq
llama-3.1-8b-instant). Each variant was scored 1-5 on accuracy, tone,
conciseness, and compliance.

## Test Questions (same 5 for all variants)

1. What's my deductible on the Gold plan?
2. What is my copay?
3. Is physical therapy covered under the Silver plan?
4. Status of claim C1001
5. Are pre-existing conditions excluded?

---

## Variant A — Strict / Formal

**Sample answers:** "Your annual deductible on plan P101 Gold PPO is
$2000." / "Pending" / refused politely and consistently when data was
missing.

**Scores:** Accuracy 4, Tone 2, Conciseness 5, Compliance 5 — **Total: 16**

Extremely safe and terse, but the tone is robotic (e.g. answering
"Pending" with no context) and it refuses even reasonably-inferable
questions.

---

## Variant B — Warm / Empathetic

**Sample answer (Q5):** "...I'm confident that you won't be denied
coverage or charged higher premiums due to a pre-existing condition."

**Scores:** Accuracy 2, Tone 5, Conciseness 1, Compliance 2 — **Total: 10**

**Critical issue found:** On Q5, this variant hallucinated a legal claim
about the Affordable Care Act that was NOT present anywhere in the
retrieved context. The warm, "helpful" framing pushed the model to
invent an answer rather than admit it didn't know - a serious problem
for a health coverage bot. Also very verbose.

---

## Variant C — Few-shot

**Sample answers:** Matched the example style well for Q1, Q2, Q4.
Q5 repeated the same ACA hallucination issue seen in Variant B.

**Scores:** Accuracy 3, Tone 4, Conciseness 4, Compliance 2 — **Total: 13**

The few-shot examples improved format consistency, but did not prevent
the same ungrounded-claim problem on Q5.

---

## Variant D — Chain-of-Thought

**Sample answers:** "$2,000.00" / correctly asked for clarification on
Q2 / correctly declined Q3 and Q5 without inventing facts.

**Scores:** Accuracy 4, Tone 3, Conciseness 5, Compliance 4 — **Total: 16**

The explicit "check the section, confirm it actually answers" step
appears to have prevented the hallucination seen in B and C - it stayed
grounded on Q5. Slightly terse tone (e.g. bare numbers with no context).

---

## Variant E — Hybrid (winner)

**Sample answers:** Correctly answered Q1 and Q4, asked for
clarification on Q2 (rather than guessing), correctly declined Q3 and
Q5 without inventing any legal or medical claims.

**Scores:** Accuracy 5, Tone 4, Conciseness 4, Compliance 5 — **Total: 18**

**Best overall.** Combines Variant A's strict grounding + Variant D's
internal verification step (which prevented hallucination) with
Variant B's warmer phrasing - without inheriting B/C's tendency to
overstate. It also correctly asked for clarification instead of
guessing on ambiguous questions (Q2), and included the standard closing
disclaimer.

---

## Final Comparison Table

| Variant | Accuracy | Tone | Conciseness | Compliance | Total |
|---|---|---|---|---|---|
| A - Strict | 4 | 2 | 5 | 5 | 16 |
| B - Empathetic | 2 | 5 | 1 | 2 | 10 |
| C - Few-shot | 3 | 4 | 4 | 2 | 13 |
| D - Chain-of-Thought | 4 | 3 | 5 | 4 | 16 |
| **E - Hybrid** | **5** | **4** | **4** | **5** | **18** |

## Chosen / Production Prompt

**Variant E (Hybrid)** is selected as the production system prompt for
`rag_chatbot.py`. It scored highest overall, and - most importantly -
was one of only two variants (with D) that avoided inventing an
ungrounded legal claim on the "pre-existing conditions" question. Given
this is a health coverage assistant, avoiding hallucinated claims is
weighted as the top priority, even above tone or conciseness.

## Key Takeaway

The most surprising finding was that a warmer, more "helpful" tone
(Variants B and C) correlated with a higher risk of hallucination - the
model appeared to prioritize sounding helpful over staying strictly
grounded. Adding an explicit internal verification step (as in D and E)
appears to be a more reliable way to prevent overstated answers than
tone alone. This reinforces why compliance was weighted heavily in
choosing the final winner.