# Rich Outputs Test — Day 19

Testing citations, claim-status cards, and coverage-summary cards in the Coverage Chatbot.
Plan selected in sidebar: **Gold PPO**

---

## Test 1 — Policy Citations

**Question:** Is physical therapy covered under the Silver plan?

**Expected:** Answer should show an expandable "📄 Policy sources" section with the retrieved chunk IDs.

**Result:** ✅ Pass
- Answer: "I don't have that information in your plan documents. Please contact member support for help."
- Policy sources shown: chunk_0001, chunk_0002, chunk_0003, chunk_0004, chunk_0006
- Note: answer is a graceful fallback because the question asked about the Silver plan while Gold PPO was selected — retrieval still worked correctly.

---

## Test 2 — Claim Status Card

**Question:** Status of claim C1001

**Expected:** Answer should render a `ClaimStatusCard` with claim_id, status, amount, and date.

**Result:** ✅ Pass
- Answer: "The status of claim C1001 is Pending."
- Card rendered: Claim Status: C1001 — Status: Pending, Amount: $250.00, Date filed: 2023-04-01

---

## Test 3 — Coverage Summary Card

**Question:** What's my deductible on the Gold plan?

**Expected:** Answer should render a `CoverageSummaryCard` with plan_name, deductible, copay, and covered status.

**Result:** ✅ Pass
- Answer: "Your deductible on the Gold PPO plan is $2,000 per year."
- Card rendered: Coverage Summary: Gold PPO — Deductible: $2,000.00, Copay: 10.0%, Covered: Yes

---

## Persistence Check (bonus)

Verified that after asking Q2 and Q3, Q1's citations and Q2's card **still remained visible** in the chat history (not just the latest message) — confirmed via `st.session_state.messages` storing `citations`, `claim_card`, and `coverage_card` alongside `content`, and the history-render loop displaying them.

**Result:** ✅ Pass

---

## Summary

All 3 required response types tested and confirmed working: policy citations, claim-status card, coverage-summary card. History persistence across reruns also confirmed.