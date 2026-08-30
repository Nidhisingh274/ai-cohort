import sys
import os
import time
import csv
import hashlib
import sqlite3
import traceback
from collections import defaultdict, deque
from datetime import datetime
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import tiktoken

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from retrieval_engine import retrieve, DB_PATH
from rag_chatbot import generate_answer, client, MODEL_NAME
from redact_pii import redact_pii
from token_utils import count_tokens, count_message_tokens

# =====================
# Day 30: Langfuse tracing. Keys come from .env (LANGFUSE_PUBLIC_KEY,
# LANGFUSE_SECRET_KEY, LANGFUSE_HOST) and are never hardcoded. Every
# tracing call is wrapped in try/except: observability must never be able
# to break the chat itself.
#
# This uses the Langfuse v4 SDK, which is OpenTelemetry-based. Each LLM
# call becomes a generation observation created with
# start_observation(as_type="generation") and closed with end(). Latency is
# measured automatically between those two points; the full prompt, the
# response, token usage and estimated cost are attached to the span.
# Session and member IDs are carried in the span metadata.
# =====================
try:
    from langfuse import Langfuse
    langfuse = Langfuse()
    LANGFUSE_ENABLED = True
except Exception as e:
    print(f"[LANGFUSE] Tracing disabled: {e}")
    langfuse = None
    LANGFUSE_ENABLED = False

app = FastAPI()

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            timestamp TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()

init_db()


def save_turn(session_id, role, content):
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT INTO conversations (session_id, role, content, timestamp) VALUES (?, ?, ?, ?)",
        (session_id, role, content, datetime.now().isoformat())
    )
    conn.commit()
    conn.close()


def load_history(session_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.execute(
        "SELECT role, content, timestamp FROM conversations WHERE session_id = ? ORDER BY id ASC",
        (session_id,)
    )
    rows = cursor.fetchall()
    conn.close()
    return [{"role": r[0], "content": r[1], "timestamp": r[2]} for r in rows]


_encoding = tiktoken.get_encoding("cl100k_base")

def count_history_tokens(history):
    return sum(count_tokens(t["content"]) for t in history)


# =====================
# Day 26: usage + cost logging to CSV
# =====================
USAGE_CSV = os.path.join(ROOT, "token_usage.csv")
INPUT_COST_PER_1K = 0.0001
OUTPUT_COST_PER_1K = 0.0005


def estimate_cost(input_tokens, output_tokens):
    return round(
        (input_tokens / 1000) * INPUT_COST_PER_1K
        + (output_tokens / 1000) * OUTPUT_COST_PER_1K,
        8,
    )


def log_usage(session_id, input_tokens, output_tokens, cached=False):
    cost = estimate_cost(input_tokens, output_tokens)
    new_file = not os.path.exists(USAGE_CSV)
    try:
        with open(USAGE_CSV, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            if new_file:
                writer.writerow([
                    "session_id", "timestamp", "input_tokens",
                    "output_tokens", "estimated_cost", "cached",
                ])
            writer.writerow([
                session_id, datetime.now().isoformat(),
                input_tokens, output_tokens, cost, cached,
            ])
    except Exception as e:
        print(f"[USAGE] Could not write usage log: {e}")
    print(f"[USAGE] session={session_id} input_tokens={input_tokens} "
          f"output_tokens={output_tokens} estimated_cost=${cost:.8f} cached={cached}")
    return cost


# =====================
# Day 26: rate limiter
# =====================
RATE_LIMIT_PER_MINUTE = 10
RATE_WINDOW_SECONDS = 60
_request_times = defaultdict(deque)


def check_rate_limit(member_id):
    now = time.time()
    window = _request_times[member_id]

    while window and now - window[0] > RATE_WINDOW_SECONDS:
        window.popleft()

    if len(window) >= RATE_LIMIT_PER_MINUTE:
        print(f"[RATE LIMIT] member={member_id} exceeded "
              f"{RATE_LIMIT_PER_MINUTE} requests/minute")
        return False

    window.append(now)
    return True


# =====================
# Day 26: cache for general questions only
# =====================
_response_cache = {}

MEMBER_SPECIFIC_MARKERS = [
    "my claim", "my claims", "claim status", "status of claim",
    "my member", "member id", "my deductible", "my premium",
    "my copay", "my plan", "my coverage", "my out-of-pocket",
]


def is_cacheable(question):
    lowered = question.lower()

    import re
    if re.search(r"\b[CM]\d{4,}\b", question, re.IGNORECASE):
        return False

    for marker in MEMBER_SPECIFIC_MARKERS:
        if marker in lowered:
            return False

    return True


def cache_key(question):
    normalized = " ".join(question.lower().split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


KNOWN_PLANS = {
    "gold ppo": "P101",
    "silver hmo": "P102",
    "bronze hmo": "P103",
    "gold": "P101",
    "silver": "P102",
    "bronze": "P103",
}

def detect_plan(history):
    plan_id, plan_name = None, None
    for turn in history:
        content_lower = turn["content"].lower()
        for name, pid in KNOWN_PLANS.items():
            if name in content_lower:
                plan_id, plan_name = pid, name
    return plan_id, plan_name


def summarize_turns(turns):
    conversation_text = "\n".join([f"{t['role']}: {t['content']}" for t in turns])
    summary_prompt = f"""Summarize the following conversation between a member and a
health coverage assistant in 2-3 sentences. Preserve any specific plan
names, claim IDs, or key facts mentioned, since they may be needed
later in the conversation.

Conversation:
{conversation_text}

Summary:"""

    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[{"role": "user", "content": summary_prompt}]
    )
    return response.choices[0].message.content


MAX_RECENT_TURNS = 10
TOKEN_THRESHOLD = 2000


def build_effective_history(session_id):
    full_history = load_history(session_id)
    tokens_before = count_history_tokens(full_history)

    summarized = False
    if tokens_before > TOKEN_THRESHOLD and len(full_history) > MAX_RECENT_TURNS:
        older_turns = full_history[:-MAX_RECENT_TURNS]
        recent_turns = full_history[-MAX_RECENT_TURNS:]
        summary = summarize_turns(older_turns)
        effective_history = [
            {"role": "user", "content": f"[Earlier conversation summary]: {summary}"}
        ] + recent_turns
        summarized = True
    else:
        effective_history = full_history[-MAX_RECENT_TURNS:] if len(full_history) > MAX_RECENT_TURNS else full_history

    tokens_after = count_history_tokens(effective_history)
    return effective_history, tokens_before, tokens_after, summarized


@app.get("/health")
def health():
    return {"status": "ok"}


class ChatRequest(BaseModel):
    session_id: str
    member_id: str
    message: str


@app.post("/chat")
def chat(request: ChatRequest):
    start_time = time.time()

    if not check_rate_limit(request.member_id):
        raise HTTPException(
            status_code=429,
            detail="You've sent too many requests. Please wait a moment and try again.",
        )

    save_turn(request.session_id, "user", request.message)

    print(f"[CHAT] session={request.session_id} message={redact_pii(request.message)}")

    cacheable = is_cacheable(request.message)
    key = cache_key(request.message) if cacheable else None

    if cacheable and key in _response_cache:
        cached_answer = _response_cache[key]
        print(f"[CACHE HIT] session={request.session_id} question={redact_pii(request.message)}")
        save_turn(request.session_id, "assistant", cached_answer)
        log_usage(request.session_id, 0, 0, cached=True)

        def cached_generator():
            yield f"data: {cached_answer}\n\n"
            yield "data: [DONE]\n\n"

        return StreamingResponse(cached_generator(), media_type="text/event-stream")

    if cacheable:
        print(f"[CACHE MISS] session={request.session_id} question={redact_pii(request.message)}")
    else:
        print(f"[CACHE SKIP] member-specific question, not cached")

    def event_generator():
        full_answer = ""
        generation = None
        try:
            effective_history, tokens_before, tokens_after, summarized = build_effective_history(request.session_id)

            plan_id, plan_name = detect_plan(effective_history)

            retrieval_result = retrieve(request.message)
            context = retrieval_result["context"]

            plan_reminder = ""
            if plan_id:
                plan_reminder = f"\n\nNote: The member has been discussing the {plan_name.title()} plan (plan_id: {plan_id}) earlier in this conversation. If they don't repeat the plan name, assume they still mean this plan."

            system_prompt = f"""You are a warm, professional health coverage assistant. Members may be
stressed about medical costs, so answer clearly, kindly, and concisely.

Before answering, internally check: (1) which plan the question refers
to, (2) whether the retrieved context actually contains the answer.

Answer using ONLY the information in the context below - do not guess
or add information not present there. If the plan isn't specified in
the question, ask the member to clarify which plan they mean rather
than guessing.{plan_reminder}

This is not medical advice. For any medical questions, please consult a
licensed healthcare provider."""

            messages = [{"role": "system", "content": system_prompt}]

            prior_turns = effective_history[:-1] if effective_history else []
            for turn in prior_turns:
                role = turn["role"] if turn["role"] in ("user", "assistant") else "user"
                messages.append({"role": role, "content": turn["content"]})

            user_message = f"""Context: {context}

Question: {request.message}"""
            messages.append({"role": "user", "content": user_message})

            print(f"[MEMORY] session={request.session_id} tokens_before={tokens_before} tokens_after={tokens_after} summarized={summarized}")

            input_tokens = count_message_tokens(messages)

            # =====================
            # Day 30: open a Langfuse generation observation for this LLM
            # call. The span carries the full prompt as input; latency is
            # timed automatically between start and end. Session and member
            # IDs travel in metadata so traces can be filtered per member
            # and per conversation in the dashboard.
            # =====================
            if LANGFUSE_ENABLED:
                try:
                    generation = langfuse.start_observation(
                        name="groq-completion",
                        as_type="generation",
                        model=MODEL_NAME,
                        input=messages,
                        metadata={
                            "session_id": request.session_id,
                            "member_id": request.member_id,
                            "question": request.message,
                            "classification": retrieval_result["classification"],
                            "plan_id": plan_id,
                            "tokens_before": tokens_before,
                            "tokens_after": tokens_after,
                            "summarized": summarized,
                            "cached": False,
                        },
                    )
                except Exception as e:
                    print(f"[LANGFUSE] Could not start trace: {e}")

            stream = client.chat.completions.create(
                model=MODEL_NAME,
                messages=messages,
                stream=True
            )

            for chunk in stream:
                token = chunk.choices[0].delta.content
                if token:
                    full_answer += token
                    yield f"data: {token}\n\n"

            output_tokens = count_tokens(full_answer)
            cost = log_usage(request.session_id, input_tokens, output_tokens, cached=False)

            # =====================
            # Day 30: close the span with the response, token usage and
            # estimated cost. flush() is called because this is a
            # short-lived request path - without it the span can be lost
            # before the background exporter sends it.
            # =====================
            if generation is not None:
                try:
                    generation.update(
                        output=full_answer,
                        usage_details={
                            "input": input_tokens,
                            "output": output_tokens,
                            "total": input_tokens + output_tokens,
                        },
                        metadata={"estimated_cost_usd": cost},
                    )
                    generation.end()
                    langfuse.flush()
                except Exception as e:
                    print(f"[LANGFUSE] Could not end generation: {e}")

            save_turn(request.session_id, "assistant", full_answer)

            if cacheable and key:
                _response_cache[key] = full_answer

            print(f"[CHAT] session={request.session_id} answer={redact_pii(full_answer)}")

            elapsed = time.time() - start_time
            print(f"[INFO] session={request.session_id} time={elapsed:.2f}s classification={retrieval_result['classification']}")

            yield "data: [DONE]\n\n"

        except Exception as e:
            elapsed = time.time() - start_time
            print(f"[ERROR] session={request.session_id} time={elapsed:.2f}s error={str(e)}")
            traceback.print_exc()

            # Day 30: record the failure on the span so error rate is
            # visible in the dashboard, not just in local logs
            if generation is not None:
                try:
                    generation.update(output=f"ERROR: {e}", level="ERROR")
                    generation.end()
                    langfuse.flush()
                except Exception:
                    pass

            yield f"data: [ERROR] Something went wrong while generating a response. Please try again.\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.get("/history/{session_id}")
def get_history(session_id: str):
    history = load_history(session_id)
    return {"session_id": session_id, "history": history}