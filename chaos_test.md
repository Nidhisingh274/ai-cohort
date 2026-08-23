# Chaos Test — Day 24

## What Was Built

The Day 22 multi-agent workflow (Router + Coverage Specialist + Claims Specialist, wired with LangGraph) was updated to call the Day 23 MCP tools, use the Day 20 conversation memory, and wrap every tool call in a resilience layer: a 10-second timeout, at most one retry, and a canned member-facing fallback.

## Resilience Configuration

TOOL_TIMEOUT = 10 seconds, applied via asyncio.wait_for(asyncio.to_thread(func, *args), timeout=TOOL_TIMEOUT)
MAX_RETRIES = 1 (each tool gets at most 2 attempts: the initial call plus one retry)
FALLBACK_MESSAGE = "I'm having trouble accessing that right now, please contact member support."

Every tool call goes through resilient_tool_call(), which catches asyncio.TimeoutError and any other exception, retries once, then returns the canned fallback string instead of raising. The member never sees a raw 500, a stack trace, or an exception message.

## How the MCP Tools Are Called - Measured, Not Assumed

Both call paths were implemented and then benchmarked with test_mcp_protocol.py before deciding which to use in production:

get_claim_status over the full MCP protocol (spawn mcp_server.py via StdioServerParameters, complete the ClientSession.initialize() handshake, invoke with session.call_tool()): measured at 2.2 seconds per call - comfortably inside the 10-second budget. This is the path used in production, so the claims specialist genuinely talks to the Day 23 server over MCP.

check_coverage over the full MCP protocol: measured at 302+ seconds per call (test timed out at a deliberately generous 300s limit). Each protocol call spawns a fresh subprocess, which reloads the all-MiniLM-L6-v2 sentence-transformers model from scratch; on this machine (8GB RAM, CPU-only, no GPU) that alone takes 4-5 minutes. That is roughly 30x over the mission's 10-second budget, so every call would time out, exhaust its retry, and fall back - the coverage specialist would never return a real answer. This tool therefore uses a direct in-process import of the same @mcp.tool()-decorated function, which runs the identical tool code and pays the model-load cost once per process (~15s first call, instant afterwards).

Both mechanisms live in multi_agent.py: call_mcp_tool_over_protocol() implements the protocol path, and the direct import sits alongside it.

## Normal Run (before chaos)

Three sequential questions were sent through the workflow sharing one session_id:

Turn 1: "I'm on the Silver HMO plan." -> routed to coverage specialist, which acknowledged plan P102.

Turn 2: "What's my deductible?" -> routed to coverage specialist. The router log shows plan=silver, confirming Day 20 memory correctly recalled the plan from Turn 1 even though this question never repeats the plan name. check_coverage was invoked and returned the Silver HMO structured data (P102, $300/month premium, $1500 annual deductible, 20% copay) plus relevant policy chunks from vector_lookup(). Final answer: "Your annual deductible for the Silver HMO plan (plan P102) is $1,500."

Turn 3: "What's the status of claim C1001?" -> routed to claims specialist. get_claim_status was invoked over the MCP protocol and returned the exact claim row; the agent formatted it into a readable answer.

Both tools logged [TOOL OK] ... succeeded on attempt 1 in this run.

## Retry Observed in an Earlier Run

In an earlier run (before the model was warm in that process), the resilience layer caught a real transient failure with no chaos injection:

[TOOL TIMEOUT] check_coverage attempt 1/2 exceeded 10s
[TOOL OK] check_coverage succeeded on attempt 2

The first attempt exceeded the 10-second budget while the embedding model loaded for the first time. The single retry then succeeded against a warm model, and the member received the correct, complete answer with no fallback needed - exactly the behaviour the retry exists to provide for transient failures.

## Chaos Test: Breaking get_claim_status

chaos_test.py replaces multi_agent._get_claim_status_via_protocol with a stub that unconditionally raises RuntimeError("Simulated tool failure (chaos test)"), then rebinds the claims specialist's tool wrapper so the agent calls the broken version.

Observed output:

[TOOL ERROR] get_claim_status attempt 1/2 failed: RuntimeError: Simulated tool failure (chaos test)
[TOOL ERROR] get_claim_status attempt 2/2 failed: RuntimeError: Simulated tool failure (chaos test)
[FALLBACK] get_claim_status failed after 2 attempts - returning canned support message

The tool returned the canned fallback string to the agent, which turned it into a member-appropriate reply:

"I'm sorry, but I'm currently unable to retrieve the status for claim C1001. Please contact member support for the most up-to-date information. If there's anything else I can help you with - such as general claim questions, coverage details, or how to file a claim - just let me know!"

Confirmed: the workflow did not crash, no exception or stack trace reached the member, no raw 500 was produced, and the reply degraded gracefully to a support hand-off. Both attempts (initial plus one retry) are visible in the log, confirming MAX_RETRIES = 1 behaves as specified.

## Restoring the Tool

The chaos script restores the original function and re-runs the same question:

[TOOL OK] get_claim_status succeeded on attempt 1

Result returned to the member: Claim C1001 - Status Pending, Procedure X-ray, Claim amount $250, Filed on 2023-04-01 - an exact match to the Day 4 claims.csv source data. Everything passes again after the fix.

## Summary

| Scenario | Attempts | Outcome |
|---|---|---|
| check_coverage, cold start (real transient failure) | 2 (timeout, then success) | Correct answer, retry saved it |
| check_coverage, warm | 1 | Correct answer |
| get_claim_status over MCP protocol, healthy | 1 | Correct answer (2.2s) |
| get_claim_status, chaos-broken | 2 (both failed) | Canned fallback, no crash |
| get_claim_status, restored | 1 | Correct answer |

The resilience layer was exercised in all three of its modes: a clean success, a transient failure rescued by the single retry, and a hard failure degraded to the canned support fallback. In no case did an exception, stack trace, or raw 500 reach the member.