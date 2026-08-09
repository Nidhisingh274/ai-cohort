# Vector Query Test — Day 9

## Step 3: Collection Count Verification

After batch-upserting all knowledge_base.jsonl chunks (with their Day 7
embeddings) into the Chroma `coverage_kb` collection, I verified the
index size using `collection.count()`.

- Chunks in knowledge_base.jsonl: **6**
- Chroma collection.count(): **6**
- Result: ✅ Match confirmed — all chunks were successfully upserted with
  no records lost or duplicated.

## Step 4-5: Raw Similarity Query Test

**Test question:** "Is physical therapy covered under the Silver plan?"

Query run with `collection.query(query_embeddings=[...], n_results=5)`
(no metadata filter).

### Results (ranked by distance, lower = more similar)

| Rank | Chunk ID | Plan Type | Section | Distance | Text (preview) |
|---|---|---|---|---|---|
| 1 | chunk_0002 | Silver HMO | coverage | 1.1661 | "Silver HMO: $300/month premium, $1500 deductible, 20% copay..." |
| 2 | chunk_0004 | all | coverage | 1.2349 | "Summary of Benefits and Coverage... Plan: Gold PPO..." |
| 3 | chunk_0003 | Bronze HMO | coverage | 1.2618 | "Bronze HMO: $150/month premium, $1000 deductible, 30% copay..." |
| 4 | chunk_0001 | Gold PPO | coverage | 1.3394 | "Gold PPO: $500/month premium, $2000 deductible, 10% copay..." |
| 5 | chunk_0006 | all | enrollment | 1.5468 | "ENFOLLMENTFORM... Member Name: John Doe..." |

### Are the results relevant?

Partially. The top result (chunk_0002) correctly identifies the Silver
HMO plan chunk as the closest match, which shows the embedding model
correctly associated "Silver plan" in the question with the "Silver HMO"
chunk. However, none of the chunks actually mention "physical therapy"
specifically, since our sample benefits data only contains high-level
plan info (premium, deductible, copay) - not a detailed list of covered
services. So while the *plan* was correctly identified, the *specific
service* (physical therapy) could not be answered from this data.

### Does it reflect Silver-plan-specific coverage (not another plan)?

The #1 result is Silver-plan-specific (chunk_0002). However, because this
was an **unfiltered** query, results #2-5 pull in Gold PPO, Bronze HMO,
and enrollment data - which are not relevant to a Silver-plan-specific
question. This shows the limitation of raw (unfiltered) similarity
search: it returns the closest matches across the *entire* knowledge
base, even if they belong to a different plan.

### Retrieval misses noted

- No chunk contains information about "physical therapy" or a detailed
  list of covered/excluded services - this is a gap in our sample data,
  not a retrieval bug.
- Without filtering, 4 out of 5 results are not Silver-plan-specific,
  which would be misleading if shown directly to a user asking a
  Silver-plan question.

## Step 6: Metadata-Filtered Query Test

Same question, same embedding, but with a metadata filter:

```python
collection.query(
    query_embeddings=[query_vector],
    n_results=5,
    where={"plan_type": "Silver HMO"}
)
```

### Results

| Rank | Chunk ID | Plan Type | Section | Distance | Text (preview) |
|---|---|---|---|---|---|
| 1 | chunk_0002 | Silver HMO | coverage | 1.1661 | "Silver HMO: $300/month premium, $1500 deductible, 20% copay..." |

Only **1 result** was returned (even though n_results=5 was requested),
because only one chunk in the knowledge base has `plan_type: "Silver
HMO"`. This is expected behavior, not an error.

### Filtered vs Unfiltered Comparison

| | Unfiltered | Filtered (plan_type=Silver HMO) |
|---|---|---|
| Results returned | 5 | 1 |
| Plans represented | Silver, Gold, Bronze, "all" | Silver HMO only |
| Top result | chunk_0002 (Silver HMO) | chunk_0002 (Silver HMO) |

### Confirmation

✅ Metadata filtering successfully scoped results to a single plan
(Silver HMO only). This confirms that in a real chatbot, filtering by
`plan_type` before running similarity search would prevent a member on
one plan from seeing another plan's coverage details mixed into their
answer - which is critical for both accuracy and (in a real production
system) data-isolation requirements.

## Note on Naming

The knowledge base stores plan types using their full name (e.g. "Silver
HMO", "Gold PPO", "Bronze HMO") rather than just the tier name ("Silver",
"Gold", "Bronze"). The filter therefore used the exact value
`"Silver HMO"` to match. 