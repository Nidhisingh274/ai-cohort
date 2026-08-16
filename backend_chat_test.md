# Backend Chat Test — Day 16

Testing the /chat and /history/{session_id} endpoints in coverage-chatbot-api/main.py, using PowerShell's curl (Invoke-WebRequest) against the local server at http://127.0.0.1:8000.

## Test Setup

Server started by running these two commands in the coverage-chatbot-api folder:
cd coverage-chatbot-api
uvicorn main:app --reload

All 3 messages below were sent with the same session_id: "test123" to simulate a continuous conversation.

## Message 1

**Request:**
curl -UseBasicParsing -Method POST http://127.0.0.1:8000/chat -ContentType "application/json" -Body '{"session_id": "test123", "member_id": "M1001", "message": "What is my deductible on the Gold plan?"}'

**Response:**
{"session_id":"test123","member_id":"M1001","answer":"Your deductible on the Gold PPO plan is $2,000 per year.","classification":"structured"}

**Result:** Correct answer, structured classification, ~4.6s response time (logged server-side).

## Message 2

**Request:**
curl -UseBasicParsing -Method POST http://127.0.0.1:8000/chat -ContentType "application/json" -Body '{"session_id": "test123", "member_id": "M1001", "message": "What is my copay?"}'

**Response:**
{"session_id":"test123","member_id":"M1001","answer":"I don't have that information. Please tell me which plan you're referring to (Gold PPO, Silver HMO, or Bronze HMO).","classification":"structured"}

**Result:** Correctly asked for clarification instead of guessing, since no plan was specified in the question (consistent with the Day 12 winning prompt behavior).

## Message 3

**Request:**
curl -UseBasicParsing -Method POST http://127.0.0.1:8000/chat -ContentType "application/json" -Body '{"session_id": "test123", "member_id": "M1001", "message": "Status of claim C1001"}'

**Response:**
{"session_id":"test123","member_id":"M1001","answer":"The status of claim C1001 is Pending.","classification":"structured"}

**Result:** Correct claim status returned.

## History Check

**Request:**
curl -UseBasicParsing http://127.0.0.1:8000/history/test123

**Response (summary):** Returned all 6 entries (3 user messages + 3 assistant responses) for session_id: "test123", each with a role, content, and timestamp - confirming the session store correctly accumulates conversation turns across multiple /chat calls.

## Error Handling Verification

During development, a bug was encountered where retrieval_engine.py tried to open coverage.db using a relative path, which failed with sqlite3.OperationalError: no such table: plans when the server was run from the coverage-chatbot-api/ subfolder (since coverage.db actually lives in the parent folder).

Importantly, this was not a server crash - the try/except block around the retrieve/generate call caught the error, logged it server-side with a timestamp, and returned a graceful JSON error message to the client instead:
{"error": "Something went wrong while generating a response. Please try again.", "session_id": "test123"}

This confirmed the error-handling requirement (Step 6) works correctly even under a real failure, not just a simulated one. The root cause was then fixed by resolving coverage.db's path relative to retrieval_engine.py's own location rather than the current working directory.

## Summary

| Test | Endpoint | Result |
|---|---|---|
| Message 1 | POST /chat | Correct |
| Message 2 | POST /chat | Correct (asked for clarification) |
| Message 3 | POST /chat | Correct |
| History | GET /history/test123 | All 3 turns present |
| Error handling | POST /chat (during DB path bug) | Gracefully handled, no crash |