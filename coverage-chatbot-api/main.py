import sys
import os
import time
import sqlite3
import traceback
from datetime import datetime
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import tiktoken

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from retrieval_engine import retrieve, DB_PATH
from rag_chatbot import generate_answer, client, MODEL_NAME
from redact_pii import redact_pii

app = FastAPI()

# =====================
# STEP 1: conversations table (persisted memory)
# =====================
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
    """STEP 2: persist one chat turn to SQLite."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT INTO conversations (session_id, role, content, timestamp) VALUES (?, ?, ?, ?)",
        (session_id, role, content, datetime.now().isoformat())
    )
    conn.commit()
    conn.close()


def load_history(session_id):
    """Load FULL persisted history for a session, oldest first."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.execute(
        "SELECT role, content, timestamp FROM conversations WHERE session_id = ? ORDER BY id ASC",
        (session_id,)
    )
    rows = cursor.fetchall()
    conn.close()
    return [{"role": r[0], "content": r[1], "timestamp": r[2]} for r in rows]


# =====================
# STEP 4: Token counting (tiktoken)
# =====================
_encoding = tiktoken.get_encoding("cl100k_base")

def count_tokens(text):
    return len(_encoding.encode(text))

def count_history_tokens(history):
    return sum(count_tokens(t["content"]) for t in history)


# =====================
# Plan memory - detect which plan the member has mentioned
# =====================
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


# =====================
# STEP 4: Summarize the oldest turns with one LLM call
# =====================
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


MAX_RECENT_TURNS = 10   # STEP 3: last N turns kept directly in context
TOKEN_THRESHOLD = 2000  # STEP 4: summarize once history exceeds this


def build_effective_history(session_id):
    """
    STEP 3 + STEP 4: builds the conversation context sent to the LLM.
    Always includes the last MAX_RECENT_TURNS directly. If FULL history
    exceeds TOKEN_THRESHOLD tokens, summarizes everything older than the
    last MAX_RECENT_TURNS turns into one LLM summary, replacing them.
    """
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

    # STEP 2: persist the user's message immediately
    save_turn(request.session_id, "user", request.message)

    # Day 25: log the incoming message with PHI/PII redacted
    print(f"[CHAT] session={request.session_id} message={redact_pii(request.message)}")

    def event_generator():
        full_answer = ""
        try:
            # STEP 3-4: build conversation memory (recent turns + summary if needed)
            effective_history, tokens_before, tokens_after, summarized = build_effective_history(request.session_id)

            # STEP 3: remember which plan the member already specified
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

            # STEP 6: log token counts for this request
            print(f"[MEMORY] session={request.session_id} tokens_before={tokens_before} tokens_after={tokens_after} summarized={summarized}")

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

            # STEP 2: persist the assistant's reply
            save_turn(request.session_id, "assistant", full_answer)

            # Day 25: log the outgoing answer with PHI/PII redacted
            print(f"[CHAT] session={request.session_id} answer={redact_pii(full_answer)}")

            elapsed = time.time() - start_time
            print(f"[INFO] session={request.session_id} time={elapsed:.2f}s classification={retrieval_result['classification']}")

            yield "data: [DONE]\n\n"

        except Exception as e:
            elapsed = time.time() - start_time
            print(f"[ERROR] session={request.session_id} time={elapsed:.2f}s error={str(e)}")
            traceback.print_exc()
            yield f"data: [ERROR] Something went wrong while generating a response. Please try again.\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.get("/history/{session_id}")
def get_history(session_id: str):
    history = load_history(session_id)
    return {"session_id": session_id, "history": history}