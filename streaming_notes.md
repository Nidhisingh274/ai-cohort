# Streaming Notes — Day 18

## Implementation Summary

The /chat endpoint in coverage-chatbot-api/main.py was updated to stream tokens using FastAPI's StreamingResponse with media_type="text/event-stream" (Server-Sent Events). Instead of waiting for the full LLM response and returning it as one JSON object, the backend now yields each token as it's generated, formatted as an SSE data line (data: token followed by two newlines), and signals completion with data: [DONE] followed by two newlines.

On the frontend, app.py was updated to POST with stream=True and iterate over response.iter_lines(), appending each token to an st.empty() placeholder as it arrives - this is what creates the visible "typing" effect in the UI.

## Confirmed Typing UX

Testing confirmed the answer appears incrementally in the browser as tokens arrive from the backend, rather than waiting for the complete response. Because the model (openai/gpt-oss-20b via Groq) generates tokens very quickly, short answers can appear to render almost instantly to the human eye - but the underlying mechanism is confirmed to be token-by-token via the server logs (which show the stream starting and the timing per request) and via st.empty() being updated repeatedly inside the streaming loop, not written once at the end.

## Model Deprecation Issue Encountered (and Fixed)

During testing, the streaming endpoint initially failed with this error: openai.NotFoundError: Error code 404 - The model llama-3.1-8b-instant does not exist or you do not have access to it.

Investigation confirmed Groq deprecated llama-3.1-8b-instant (shutdown effective August 16, 2026), with Groq's own documentation recommending migration to openai/gpt-oss-20b as the direct replacement. MODEL_NAME was updated from llama-3.1-8b-instant to openai/gpt-oss-20b in rag_chatbot.py (the single source of truth for the model name, since main.py imports it from there rather than redefining it), which resolved the issue immediately - confirmed via a successful 200 OK response and a correctly streamed answer.

## Timeout / Dropped-Connection Handling

Two failure modes are handled explicitly on the frontend (app.py):

1. requests.exceptions.Timeout - if the backend doesn't respond within 30 seconds, the UI shows: "The response took too long and timed out. Please try again." instead of hanging indefinitely.

2. requests.exceptions.RequestException - covers broader connection failures (e.g. backend server not running, network drop), showing: "Error connecting to the backend... Please make sure the backend server is running."

On the backend (main.py), the entire streaming generator (event_generator()) is wrapped in try/except. If an error occurs mid-stream (e.g. the LLM API call fails, as happened with the model deprecation issue above), the backend yields a special data: [ERROR] line rather than crashing. The frontend detects this via token.startswith("[ERROR]") and displays the message directly to the user instead of showing a broken or partial response.

Design note: because streaming responses can't return an HTTP status code after the stream has already started (unlike the non-streaming Day 16 version, which could raise HTTPException(500) before any response body was sent), errors that occur during streaming are communicated via an in-band [ERROR] message in the SSE stream itself, which the frontend parses and displays. This is the standard pattern for SSE error handling, since the HTTP headers and status are already committed once the stream begins.

## Summary

| Requirement | Status |
|---|---|
| Backend streams via StreamingResponse | Done |
| media_type is text/event-stream | Done |
| SSE-formatted data lines yielded | Done |
| Frontend uses stream=True | Done |
| Frontend iterates response.iter_lines() | Done |
| Visible typing effect confirmed | Done |
| Pre-first-token loading spinner | Done (st.spinner) |
| Timeout handling | Done |
| Mid-stream error handling | Done |