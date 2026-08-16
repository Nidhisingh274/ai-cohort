import sys
import os
import time
import traceback
from datetime import datetime
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

# Allow importing retrieval_engine.py and rag_chatbot.py from the parent folder
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from retrieval_engine import retrieve
from rag_chatbot import generate_answer

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
# STEP 1-2 + STEP 6: POST /chat - orchestrates retrieve -> generate, with
# error handling and timing
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

    try:
        # STEP 2: retrieve -> generate
        retrieval_result = retrieve(request.message)
        context = retrieval_result["context"]
        answer = generate_answer(request.message, context)

    except Exception as e:
        # STEP 6: graceful error handling around the LLM path
        elapsed = time.time() - start_time
        print(f"[ERROR] session={request.session_id} time={elapsed:.2f}s error={str(e)}")
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail="Something went wrong while generating a response. Please try again."
        )

    # Log the assistant's response in history
    SESSIONS[request.session_id].append({
        "role": "assistant",
        "content": answer,
        "timestamp": datetime.now().isoformat()
    })

    elapsed = time.time() - start_time
    print(f"[INFO] session={request.session_id} time={elapsed:.2f}s classification={retrieval_result['classification']}")

    return {
        "session_id": request.session_id,
        "member_id": request.member_id, 
        "answer": answer,
        "classification": retrieval_result["classification"]
    }


# =====================
# STEP 4: GET /history/{session_id}
# =====================
@app.get("/history/{session_id}")
def get_history(session_id: str):
    if session_id not in SESSIONS:
        return {"session_id": session_id, "history": []}
    return {"session_id": session_id, "history": SESSIONS[session_id]}