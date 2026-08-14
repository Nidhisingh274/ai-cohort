# Fine-Tuning Prep Notes — Day 14

## Step 1: Recurring Issues from Day 10-13 Logs

Reviewing `retrieval_test_results.md` (Day 10), `rag_qa_results.md`
(Day 11), `prompt_variants.md` (Day 12), and `tool_call_log.md`
(Day 13), three recurring issues were identified:

### Issue 1: Inconsistent Answer Formatting
**Example:** Day 11, Test 7 ("What's the monthly premium for Silver
HMO?") returned just `"300"` instead of a full, well-formed sentence
like the other answers.

**Can fine-tuning fix this?** ✅ Yes. This is a pure style/consistency
issue - the model has the correct fact, it just doesn't consistently
format the response. Fine-tuning on examples that always answer in full
sentences would directly address this.

### Issue 2: Inconsistent / Missing Disclaimer Usage
**Example:** Across Day 11-12 logs, some answers included "This is not
medical advice" while others (even when discussing coverage
uncertainty) did not consistently include it.

**Can fine-tuning fix this?** ✅ Yes. This is exactly the kind of
behavioral consistency fine-tuning is good at - training on examples
that always include the disclaimer when appropriate would make this
consistent without needing to repeat it in every prompt.

### Issue 3: Fact Hallucination When Context Is Missing
**Example:** Day 12, Variant B and C both invented an unsupported legal
claim about the Affordable Care Act when asked about pre-existing
condition exclusions - information that was not present anywhere in
the retrieved context.

**Can fine-tuning fix this?** ⚠️ Only partially, and not reliably. This
is fundamentally a **retrieval/grounding problem**, not a style
problem. Fine-tuning can teach the model to *prefer* saying "I don't
know" in ambiguous situations, but it cannot fix the underlying issue
that the knowledge base itself lacks the relevant information (e.g. no
exclusions section in our sample data - see Day 9-10 findings). No
amount of fine-tuning gives the model facts it was never shown. The
real fix is improving retrieval and the underlying knowledge base
content, not fine-tuning tone.

## Fine-Tuning vs Retrieval - Summary

| Issue Type | Fixed by Fine-Tuning? | Fixed by Better Retrieval/Data? |
|---|---|---|
| Inconsistent formatting/tone | Yes | No |
| Missing disclaimer | Yes | No |
| Wrong/invented facts | No (only reduces likelihood) | Yes (root cause fix) |
| Missing data in knowledge base | No | Yes |

**Key takeaway:** Fine-tuning is the right tool for making the model
*consistently sound* like a warm, compliant coverage assistant every
time - tone, formatting, disclaimer habits, and correct use of
insurance jargon. It is the wrong tool for fixing missing or incorrect
*facts* - that requires improving what data is retrieved and given to
the model in the first place (Day 9-10's retrieval engine and
knowledge base), not retraining the model itself.

## Dataset Summary

- **Full curated dataset:** `fine_tune_dataset.jsonl` - 30 examples
- **Training split:** `fine_tune_train.jsonl` - 25 examples
- **Held-out test split:** `fine_tune_test.jsonl` - 5 examples (not
  used in training; reserved for Day 15 before/after comparison)
- **Format:** OpenAI-compatible `messages` schema (system/user/assistant
  roles per record)
- **Design principles applied to every example:**
  - Consistent warm-but-professional tone
  - Plain-language definitions of insurance jargon on first use (e.g.
    "A deductible is the amount you pay before insurance starts
    covering costs")
  - Standard disclaimer ("This is not medical advice...") included
    whenever the answer involves uncertain or missing coverage details
  - Every record validated to confirm correct JSON structure and the
    3-message (system/user/assistant) schema before saving