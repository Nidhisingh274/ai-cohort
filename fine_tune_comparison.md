# Fine-Tune Comparison — Day 15

Base model (`distilgpt2`) vs LoRA fine-tuned version, evaluated on the
5 held-out test questions from `fine_tune_test.jsonl` (Day 14). Fine-tuned
using PEFT/LoRA on Google Colab (free T4 GPU), 25 training examples,
3 epochs.

## Training Details

- **Base model:** `distilgpt2` (82,060,032 total parameters)
- **Method:** LoRA (rank=8, alpha=16, target module: `c_attn`)
- **Trainable parameters:** 147,456 (0.18% of total) - this is the core
  LoRA advantage: only a tiny fraction of the model was actually trained
- **Training loss:** stayed roughly flat across steps (4.31 → 4.34 →
  4.32 → 4.31) rather than decreasing meaningfully - a sign that 25
  examples / 3 epochs was not enough for the model to substantially
  adapt

## Side-by-Side Comparison (5 Held-Out Questions)

### Test 1: "Can I switch plans mid-year?"

| | Tone | Correctness | Disclaimer | Terminology |
|---|---|---|---|---|
| Base | 1 | 1 | 0 | 1 |
| Fine-tuned | 1 | 1 | 0 | 2 |

Base looped an unrelated phrase ("Can I stay at home?"). Fine-tuned at
least referenced "plan" repeatedly, but neither produced a coherent,
usable answer.

### Test 2: "What's covered under preventive care?"

| | Tone | Correctness | Disclaimer | Terminology |
|---|---|---|---|---|
| Base | 1 | 1 | 0 | 1 |
| Fine-tuned | 1 | 1 | 0 | 2 |

Base simply echoed the question. Fine-tuned used more insurance-adjacent
language ("health-care provider's plan") but the answer was still
incoherent and not actually responsive.

### Test 3: "Is my claim C1004 approved?"

| | Tone | Correctness | Disclaimer | Terminology |
|---|---|---|---|---|
| Base | 1 | 1 | 0 | 2 |
| Fine-tuned | 1 | 1 | 0 | 1 |

Neither model retrieved the actual claim status (expected - this tiny
model has no access to `coverage.db`, unlike our RAG pipeline). Notably,
the fine-tuned model started asking the member about their own medical
conditions - the opposite of the "no medical advice" behavior we
trained toward. This is a concerning regression, likely due to the
small/noisy training signal.

### Test 4: "What happens after I meet my deductible?"

| | Tone | Correctness | Disclaimer | Terminology |
|---|---|---|---|---|
| Base | 1 | 1 | 0 | 2 |
| Fine-tuned | 1 | 1 | 0 | 2 |

Both models looped the question back rather than answering it. No
meaningful difference between base and fine-tuned here.

### Test 5: "Do I need a referral to see a specialist?"

| | Tone | Correctness | Disclaimer | Terminology |
|---|---|---|---|---|
| Base | 1 | 1 | 0 | 2 |
| Fine-tuned | 1 | 1 | 0 | 2 |

Identical repetitive-loop behavior in both models. No improvement from
fine-tuning on this question.

## Score Totals (out of 20 per model, across 5 questions × 4 dimensions)

| Model | Tone | Correctness | Disclaimer | Terminology | Total |
|---|---|---|---|---|---|
| Base | 5 | 5 | 0 | 8 | 18 |
| Fine-tuned | 5 | 5 | 0 | 9 | 19 |

## Conclusion

**Did fine-tuning meaningfully improve consistency? No - not at this
scale.** The fine-tuned model showed a marginal uptick in
insurance-related terminology usage, but neither model produced a
single coherent, correct, disclaimer-including answer across all 5
test questions. Both models suffered from the same core failure modes:
repetitive looping and lack of grounded, factual responses. Concerningly,
the fine-tuned model on Test 3 began asking about the member's medical
history - behavior we explicitly wanted to avoid, suggesting the small
training set was not enough to reliably instill the target behavior and
may have introduced noise instead.

**Would more prompt / retrieval tuning have gotten better results for
less effort? Yes, clearly.** This is directly demonstrated by comparing
these results to our Day 11-13 outputs: using the same grounding prompt
and disclaimer language, but paired with (a) real retrieval from
`coverage.db` and the Chroma knowledge base, and (b) a capable
production model (Groq's `llama-3.1-8b-instant`), we consistently got
correct, well-formed, disclaimer-compliant answers (see
`rag_qa_results.md`). That approach required zero model training - just
good prompting and retrieval engineering.

**Root cause of the gap:** This experiment used a very small base model
(82M parameters, far smaller than production LLMs) and a very small
dataset (25 examples, 3 epochs) - appropriate for demonstrating LoRA
mechanics cheaply and quickly, but not enough to produce
production-quality behavior. A real production fine-tune would need a
much larger base model and thousands of curated examples to have a
realistic chance of matching prompt-engineered RAG performance.

**Overall takeaway:** For this coverage chatbot, prompting + retrieval
(Days 9-13) remains the more effective and far more efficient path to
consistent, correct, compliant answers. Fine-tuning could still be
valuable at a larger scale (bigger base model, much larger curated
dataset) specifically for enforcing tone/disclaimer consistency once
the retrieval and prompting foundation is solid - but it is not a
replacement for good grounding, and this experiment confirms it should
not be reached for first.