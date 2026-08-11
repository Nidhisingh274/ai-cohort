# RAG Q&A Results — Day 11

Full RAG pipeline (`retrieve_and_answer`) run against the same 10 test
questions used in the Day 10 baseline, using Groq (llama-3.1-8b-instant)
via the OpenAI-compatible SDK, with a grounding system prompt.

## Test 1

**Question:** "What's my deductible on the Gold plan?"
**Classification:** structured
**Answer:** "Your deductible on the Gold plan is 2000 dollars."

**vs Day 10 baseline:** Day 10 returned a raw SQL dict
(`{'annual_deductible': 2000, ...}`). Day 11 turns this into a clean,
well-formed sentence a member could actually read. **Improvement: Yes.**

## Test 2

**Question:** "What is my copay?"
**Classification:** structured
**Answer:** "I don't know the context for your question, including your
plan ID, premium, deductible and other relevant details. To find out
your copay, please contact our support."

**vs Day 10 baseline:** Day 10 fell back to returning all 3 plans
(ambiguous, no clear answer). Day 11's LLM correctly recognized the
ambiguity (no plan specified) and, following the grounding prompt,
declined to guess and pointed the member to support instead of picking
a random plan. **Improvement: Yes — this is a better, safer outcome than
silently returning the wrong plan's copay.**

## Test 3

**Question:** "Is physical therapy covered under the Silver plan?"
**Classification:** unstructured
**Answer:** "I don't know. The provided context does not mention the
Silver plan's coverage specifics, including preventive care or other
services. To know its coverage details, I suggest the member contact
support."

**vs Day 10 baseline:** Day 10 returned the Silver HMO chunk as the
closest match, but it didn't actually answer the question. Day 11's LLM
correctly recognized that the retrieved context does NOT contain the
answer, and said so honestly instead of guessing. **This is exactly the
grounding behavior the mission asked for — no overstated coverage.**

## Test 4

**Question:** "Status of claim C1001"
**Classification:** structured
**Answer:** "The status of claim C1001 is Pending."

**vs Day 10 baseline:** Day 10 returned the raw claim row. Day 11 turns
it into a direct, clear sentence. **Improvement: Yes.**

## Test 5

**Question:** "How do I file a claim?"
**Classification:** unstructured
**Answer:** "According to the Claims Process Guide, here's the
step-by-step process: 1. Submit Your Claim: Claims must be submitted
within 90 days of the service date. Include your member ID (M1001) and
procedure details. You can start by following Step 1 in the Claims
Process Guide."

**vs Day 10 baseline:** Day 10 returned the raw claims-process chunk.
Day 11 summarizes it into an actionable, readable answer.
**Improvement: Yes.**

## Test 6

**Question:** "Is maternity care covered on the Bronze plan?"
**Classification:** unstructured
**Answer:** "I don't know. The context does not mention whether
maternity care is covered, and the details mentioned for the Bronze HMO
only include premium, deductible, copay, and network."

**vs Day 10 baseline:** Same as Test 3 - the LLM correctly declined to
answer rather than overstating coverage that isn't confirmed in our
sample data. **Improvement: Yes (honest, grounded response).**

## Test 7

**Question:** "What's the monthly premium for Silver HMO?"
**Classification:** structured
**Answer:** "300"

**vs Day 10 baseline:** Day 10 returned the raw SQL row. Day 11's answer
is correct but minimal - just the number, without units ("$300/month")
or a full sentence. **Improvement: Partial** - accurate, but less
well-formed than Test 1's answer. A stricter prompt could ask for
complete sentences every time.

## Test 8

**Question:** "Are pre-existing conditions excluded?"
**Classification:** unstructured
**Answer:** "I don't know and suggest the member contact support for
clarification, as the context doesn't explicitly mention exclusions for
pre-existing conditions."

**vs Day 10 baseline:** Day 10 scored this "poor" (no exclusions section
in our data). Day 11 handles the same data gap gracefully by admitting
it doesn't know, rather than guessing. **Improvement: Yes.**

## Test 9 (Mixed)

**Question:** "What's my copay on the Gold plan and is dental covered?"
**Classification:** both
**Answer:** "Based on the provided Structured Data (SQL), the monthly
premium of the Gold PPO plan is $500, but we don't know the copay. But
according to the Policy Text (Vector Search): [Gold PPO | coverage] Gold
PPO: $500/month premium, $2000 deductible, 10% copay... Given this
information, your copay on the Gold plan is 10%. Unfortunately, I don't
know whether your plan covers dental services, as dental coverage is not
specified in the provided policy text."

**vs Day 10 baseline:** Day 10 just showed two separate raw blocks (SQL
+ vector chunks) side by side. Day 11 synthesizes both sources into one
coherent answer, correctly extracts the copay (10%), and honestly flags
that dental coverage isn't confirmed in the data. **Improvement: Yes -
this is the clearest demonstration of true RAG synthesis across sources.**

## Test 10 (Mixed)

**Question:** "How much is the Bronze plan deductible and what does it cover?"
**Classification:** both
**Answer:** "The Bronze plan's annual deductible is $1000. Its coverage
includes network: Bronze (HMO), but the structured data (SQL) and policy
text (Vector Search) do not contain information about what specific
benefits are covered by the Bronze plan."

**vs Day 10 baseline:** Same pattern as Test 9 - combines SQL and vector
results into one answer, and is honest about what isn't known.
**Improvement: Yes.**

## Summary

| Metric | Day 10 (retrieval only) | Day 11 (full RAG) |
|---|---|---|
| Format | Raw dicts / text chunks | Natural language sentences |
| Handles missing data | Returns closest-but-wrong chunk | Explicitly says "I don't know" |
| Mixed-source questions | Two separate raw blocks | Synthesized into one answer |
| Overstates coverage? | N/A (no generation) | No - grounding prompt held |

**Key findings:**
- The grounding prompt successfully prevented the LLM from inventing
  answers not present in the retrieved context (Tests 2, 3, 6, 8) - this
  is critical for a health coverage chatbot, where a wrong "yes it's
  covered" answer could have real financial consequences for a member.
- Mixed ("both") questions showed the clearest improvement over Day 10 -
  the LLM successfully merged SQL and vector context into a single,
  readable answer (Tests 9, 10).
- One minor gap: Test 7's answer ("300") was correct but too terse -
  a stricter prompt instruction (e.g. "always answer in a full sentence
  with units") could improve consistency in Day 12+ prompt engineering.
- The underlying data gaps noted on Day 9-10 (no exclusions, no detailed
  service-level coverage) still limit what the system can answer -
  Day 11 doesn't fix bad/missing data, but it does prevent the LLM from
  papering over those gaps with made-up answers.