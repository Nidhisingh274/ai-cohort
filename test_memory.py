import requests
import uuid
import time

BACKEND_URL = "http://127.0.0.1:8000/chat"
session_id = str(uuid.uuid4())
print(f"Session ID: {session_id}\n")

# 15+ turns - plan mentioned early (turn 2), never repeated after, to prove memory
turns = [
    "Hi, I have a few questions about my health coverage.",
    "I'm on the Gold PPO plan.",
    "What's my monthly premium?",
    "What's my annual deductible?",
    "What's my copay percentage?",
    "Is preventive care covered?",
    "What about hospital visits?",
    "Are prescriptions included?",
    "What's the network type for my plan?",
    "How do I file a claim if I need to?",
    "What's the status of claim C1001?",
    "How long does claim review take?",
    "What happens after I meet my deductible?",
    "Can you remind me what plan I'm on?",
    "What's my out-of-pocket maximum?",
]

for i, msg in enumerate(turns, 1):
    resp = requests.post(BACKEND_URL, json={
        "session_id": session_id,
        "member_id": "M1001",
        "message": msg
    }, stream=True, timeout=60)

    answer = ""
    for line in resp.iter_lines(decode_unicode=True):
        if line and line.startswith("data: "):
            token = line[len("data: "):]
            if token == "[DONE]":
                break
            answer += token

    print(f"Turn {i}: {msg}")
    print(f"Answer: {answer}\n")
    time.sleep(0.5)

print("All 15 turns completed. Check backend terminal for [MEMORY] token logs.")