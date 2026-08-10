# Retrieval Engine Test Results — Day 10

Test harness run against `retrieval_engine.py` using 10 varied questions,
covering structured, unstructured, and mixed ("both") classifications.

## Test 1

**Question:** "What's my deductible on the Gold plan?"
**Classification:** structured
**Retrieved context:** SQL row for Gold PPO — `annual_deductible: 2000`
**Score:** ✅ Good — correctly identified plan from question text and
returned exact deductible value.

## Test 2

**Question:** "What is my copay?"
**Classification:** structured
**Retrieved context:** No specific plan mentioned in the question, so
`sql_lookup` fell back to returning all 3 plans (Gold, Silver, Bronze).
**Score:** ⚠️ Partial — technically returned relevant data (copay values
exist in the result), but without knowing which member/plan is asking,
the answer is ambiguous. In a real system, this would need a logged-in
member's plan_id to disambiguate rather than falling back to "all plans."

## Test 3

**Question:** "Is physical therapy covered under the Silver plan?"
**Classification:** unstructured
**Retrieved context:** Top result was the Silver HMO coverage chunk,
followed by general benefits summary.
**Score:** ⚠️ Partial — correctly retrieved Silver-plan-relevant content,
but our sample knowledge base doesn't contain a specific "physical
therapy" line item, so the retrieved text can't fully answer the
question (same data gap noted on Day 9).

## Test 4

**Question:** "Status of claim C1001"
**Classification:** structured
**Retrieved context:** SQL row for claim C1001 — `status: Pending`
**Score:** ✅ Good — regex correctly extracted the claim ID and returned
the exact claim record.

## Test 5

**Question:** "How do I file a claim?"
**Classification:** unstructured
**Retrieved context:** Top result was the Claims Process Guide chunk,
explaining the submission steps.
**Score:** ✅ Good — directly relevant chunk retrieved as the top result.

## Test 6

**Question:** "Is maternity care covered on the Bronze plan?"
**Classification:** unstructured
**Retrieved context:** Top result was the Bronze HMO coverage chunk.
**Score:** ⚠️ Partial — correct plan identified, but (same as Test 3) no
specific "maternity care" clause exists in our sample data, so the
retrieved chunk is relevant but not a direct answer.

## Test 7

**Question:** "What's the monthly premium for Silver HMO?"
**Classification:** structured
**Retrieved context:** SQL row for Silver HMO — `monthly_premium: 300`
**Score:** ✅ Good — exact plan matched, exact value returned.

## Test 8

**Question:** "Are pre-existing conditions excluded?"
**Classification:** unstructured
**Retrieved context:** Returned general plan coverage chunks (Bronze,
Silver), but no chunk specifically discusses exclusions.
**Score:** ❌ Poor — our knowledge base has no "exclusions" section
(a known gap noted since Day 6), so this question cannot be meaningfully
answered from the current data. Retrieval returned the closest available
chunks, but they don't address the actual question.

## Test 9 (Mixed)

**Question:** "What's my copay on the Gold plan and is dental covered?"
**Classification:** both
**Retrieved context:** SQL row for Gold PPO (`copay_pct: 10`) PLUS vector
search results about Gold plan coverage.
**Score:** ✅ Good — correctly routed to both sources and merged the SQL
copay value with relevant coverage text in one context block.

## Test 10 (Mixed)

**Question:** "How much is the Bronze plan deductible and what does it cover?"
**Classification:** both
**Retrieved context:** SQL row for Bronze HMO (`annual_deductible: 1000`)
PLUS vector search results about Bronze plan coverage.
**Score:** ✅ Good — correctly routed to both sources; deductible value
exact, coverage summary relevant (though general, since no detailed
covered-services list exists in the sample data).

## Summary

| Score | Count |
|---|---|
| Good | 6 |
| Partial | 3 |
| Poor | 1 |

**Key observations:**
- Structured lookups (exact plan/claim match) performed reliably — 100%
  good when a plan name or claim ID was explicitly mentioned.
- The classifier correctly distinguished structured, unstructured, and
  mixed ("both") questions across all 10 tests.
- The main limitation is data coverage, not retrieval logic: our sample
  knowledge base lacks detailed service-level coverage info (e.g.
  physical therapy, maternity, exclusions), so some unstructured queries
  return relevant-but-incomplete context. This is a good baseline to
  improve in Day 11+ (e.g. by expanding the knowledge base or adding
  re-ranking to surface the most useful chunk first).
- Test 2 highlights a routing gap: questions without an explicit plan
  name fall back to returning all plans rather than asking for
  clarification or using member context - a good candidate for
  improvement in later phases.