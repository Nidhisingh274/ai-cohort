import streamlit as st
import requests
import uuid
import pandas as pd

st.set_page_config(page_title="Coverage Chatbot", page_icon="💬")
st.title("💬 Coverage Chatbot")

BACKEND_URL = "http://127.0.0.1:8000/chat"

# =====================
# STEP 3: Generate session_id once, store in session_state
# =====================
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())

# =====================
# STEP 4: Keep message history in session_state so it persists across reruns
# =====================
if "messages" not in st.session_state:
    st.session_state.messages = []

# =====================
# STEP 2: Render the conversation thread (existing messages)
# =====================
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])

# =====================
# STEP 2-4: st.chat_input for new messages, POST to backend, display reply
# =====================
user_input = st.chat_input("Ask about your coverage...")

if user_input:
    # Show the user's message immediately
    with st.chat_message("user"):
        st.write(user_input)
    st.session_state.messages.append({"role": "user", "content": user_input})

    # =====================
    # STEP 3: POST to /chat endpoint via requests
    # =====================
    with st.spinner("Thinking..."):
        try:
            response = requests.post(
                BACKEND_URL,
                json={
                    "session_id": st.session_state.session_id,
                    "member_id": "M1001",
                    "message": user_input
                },
                timeout=30
            )
            response.raise_for_status()
            data = response.json()
            answer = data.get("answer", "Sorry, I couldn't generate a response.")
        except requests.exceptions.RequestException as e:
            answer = f"Error connecting to the backend: {str(e)}. Please make sure the backend server is running."

    # Show the assistant's reply
    with st.chat_message("assistant"):
        st.write(answer)
    st.session_state.messages.append({"role": "assistant", "content": answer})

# =====================
# STEP 5: Sidebar with plan selector and "New conversation" button
# =====================
with st.sidebar:
    st.header("Settings")

    # Plan selector dropdown, populated from Day 4 plans.csv
    plans_df = pd.read_csv("data/plans.csv")
    plan_names = plans_df["plan_name"].tolist()
    selected_plan = st.selectbox("Select your plan", plan_names)

    st.divider()

    # "New conversation" button - resets session_id and clears history
    if st.button("🔄 New conversation"):
        st.session_state.session_id = str(uuid.uuid4())
        st.session_state.messages = []
        st.rerun()