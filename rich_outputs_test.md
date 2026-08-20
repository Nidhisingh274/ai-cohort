# Rich Outputs Test — Day 19

Testing citations, claim-status cards, and coverage-summary cards
rendered in the Streamlit chat UI (`app.py`), across a single 3-message
conversation.

## Test 1: Policy Citations

**Question:** "Is physical therapy covered under the Silver plan?"

**Expected:** Since this is an unstructured (policy-text) question, the
answer should be accompanied by an expandable "Policy sources" section
listing the vector-search chunk IDs used.

**Result:** ✅ Correctly rendered. The answer ("I don't have that
information in your plan documents. Please contact member support for
help.") was followed by an expandable "📎 Policy sources" section
listing 5 chunk IDs: `chunk_0002`, `chunk_0004`, `chunk_0003`,
`chunk_0001`, `chunk_0006`.

## Test 2: Claim Status Card

**Question:** "Status of claim C1001"

**Expected:** Since this is a claim-related structured question, the
answer should be followed by a `ClaimStatusCard` rendered as a bordered
card with claim_id, status, amount, and date.

**Result:** ✅ Correctly rendered. A bordered card titled "📋 Claim
Status: C1001" appeared, showing Status: Pending, Amount: $250.00, and
Date filed: 2023-04-01 00:00:00 - all sourced from the actual SQL row
in `coverage.db`.

## Test 3: Coverage Summary Card

**Question:** "What's my deductible on the Gold plan?"

**Expected:** Since this is a plan-related structured question, the
answer should be followed by a `CoverageSummaryCard` rendered as a
bordered card with plan_name, deductible, copay, and covered status.

**Result:** ✅ Correctly rendered. A bordered card titled "🏥 Coverage
Summary: Gold PPO" appeared, showing Deductible: $2,000.00, Copay:
10.0%, and Covered: ✅ Yes.

## Markdown Rendering (Step 5)

Confirmed that `st.chat_message` correctly renders `st.markdown()`
content (bold text in card headers, e.g. `**📋 Claim Status: C1001**`),
and `st.metric()` / `st.columns()` render properly formatted numeric
values and layout inside `st.container(border=True)`.

## Bug Found and Fixed During Testing

Initially, citations and cards only appeared for the most recently sent
message - previous turns in the conversation reverted to plain text on
each Streamlit rerun. This was because `st.session_state.messages` only
stored `role` and `content`, while citations/cards were only rendered
inline for the current turn, not persisted.

**Fix:** Citations and card data are now saved into
`st.session_state.messages` alongside each assistant response (as
serialized dicts via `.model_dump()`), and the message-history render
loop was updated to re-render citations/cards for every past message,
not just the newest one. Confirmed fixed - all 3 turns in the
conversation now correctly show their citations/cards simultaneously
(see screenshot from the 3-question test above).

## Summary

| Test | Feature | Result |
|---|---|---|
| 1 | Policy citations (expandable) | ✅ Correct |
| 2 | ClaimStatusCard | ✅ Correct |
| 3 | CoverageSummaryCard | ✅ Correct |
| - | Markdown rendering (bold, metrics, columns) | ✅ Correct |
| - | Persistence across reruns | ✅ Fixed and confirmed |