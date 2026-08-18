import sys
import os
import time
import traceback
from datetime import datetime
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

# Allow importing retrieval_engine.py and rag_chatbot.py from the parent folder
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from retrieval_engine import retrieve
from rag_chatbot import generate_answer, client, MODEL_NAME

app = FastAPI()

# =====================
# STEP 3: Session store - key by session_id
# =====================
SESSIONS = {}  # {session_id: [{"role": "user"/"assistant", "content": "...", "timestamp": "..."}]}


@app.get("/health")
def health():
    return {"status": "ok"}


# =====================
# STEP 1: Request body shape for POST /chat
# =====================
class ChatRequest(BaseModel):
    session_id: str
    member_id: str
    message: str


# =====================
# Day 18 - STEP 1-2: Streaming /chat endpoint using SSE
# =====================
@app.post("/chat")
def chat(request: ChatRequest):
    start_time = time.time()

    # Initialize this session's history if it's new
    if request.session_id not in SESSIONS:
        SESSIONS[request.session_id] = []

    # Log the user's message in history
    SESSIONS[request.session_id].append({
        "role": "user",
        "content": request.message,
        "timestamp": datetime.now().isoformat()
    })

    def event_generator():
        full_answer = ""
        try:
            # Retrieve context first (non-streaming, this part is fast)
            retrieval_result = retrieve(request.message)
            context = retrieval_result["context"]

            system_prompt = """You are a warm, professional health coverage assistant. Members may be
stressed about medical costs, so answer clearly, kindly, and concisely.

Before answering, internally check: (1) which plan the question refers
to, (2) whether the retrieved context actually contains the answer.

Answer using ONLY the information in the context below - do not guess
or add information not present there. If the plan isn't specified in
the question, ask the member to clarify which plan they mean rather
than guessing.

Example:
Q: What's my deductible on the Gold plan?
A: Your deductible on the Gold PPO plan is $2,000 per year.

If the context doesn't contain the answer, respond: "I don't have that
information in your plan documents. Please contact member support for
help."

This is not medical advice. For any medical questions, please consult a
licensed healthcare provider."""

            user_message = f"""Context: {context}

Question: {request.message}"""

            # STEP 2: Use the LLM SDK's streaming mode
            stream = client.chat.completions.create(
                model=MODEL_NAME,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message}
                ],
                stream=True
            )

            for chunk in stream:
                token = chunk.choices[0].delta.content
                if token:
                    full_answer += token
                    # STEP 2: Yield each token as an SSE-formatted line
                    yield f"data: {token}\n\n"

            # Log the complete assistant response in history
            SESSIONS[request.session_id].append({
                "role": "assistant",
                "content": full_answer,
                "timestamp": datetime.now().isoformat()
            })

            elapsed = time.time() - start_time
            print(f"[INFO] session={request.session_id} time={elapsed:.2f}s classification={retrieval_result['classification']}")

            # Signal that the stream is done
            yield "data: [DONE]\n\n"

        except Exception as e:
            elapsed = time.time() - start_time
            print(f"[ERROR] session={request.session_id} time={elapsed:.2f}s error={str(e)}")
            traceback.print_exc()
            yield f"data: [ERROR] Something went wrong while generating a response. Please try again.\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


# =====================
# STEP 4: GET /history/{session_id}
# =====================
@app.get("/history/{session_id}")
def get_history(session_id: str):
    if session_id not in SESSIONS:
        return {"session_id": session_id, "history": []}
    return {"session_id": session_id, "history": SESSIONS[session_id]}