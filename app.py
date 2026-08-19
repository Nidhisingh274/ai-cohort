import streamlit as st
import requests
import uuid
import pandas as pd
import sys
import os

# Allow importing retrieval_engine.py and response_cards.py from this folder
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from retrieval_engine import retrieve
from response_cards import ClaimStatusCard, CoverageSummaryCard

st.set_page_config(page_title="Coverage Chatbot", page_icon="💬")
st.title("💬 Coverage Chatbot")

BACKEND_URL = "http://127.0.0.1:8000/chat"

# =====================
# STEP 1-2: Fetch citations separately (frontend calls retrieve() directly
# just to get chunk IDs for the "Policy sources" footnote, since the
# streaming backend only sends back tokens, not citation metadata)
# =====================
def get_citations(question):
    try:
        retrieval_result = retrieve(question)
        return [chunk["id"] for chunk in retrieval_result.get("vector_results", [])]
    except Exception:
        return []


# =====================
# STEP 4: Render a claim status as a formatted card
# =====================
def render_claim_card(card: ClaimStatusCard):
    with st.container(border=True):
        st.markdown(f"**📋 Claim Status: {card.claim_id}**")
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Status", card.status)
            st.write(f"**Date filed:** {card.date}")
        with col2:
            st.metric("Amount", f"${card.amount:,.2f}")


# =====================
# STEP 4: Render a coverage summary as a formatted card
# =====================
def render_coverage_card(card: CoverageSummaryCard):
    with st.container(border=True):
        st.markdown(f"**🏥 Coverage Summary: {card.plan_name}**")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Deductible", f"${card.deductible:,.2f}")
        with col2:
            st.metric("Copay", f"{card.copay}%")
        with col3:
            st.metric("Covered", "✅ Yes" if card.covered else "❌ No")


# =====================
# Simple heuristics to decide when to show a card, based on the question
# =====================
def try_build_claim_card(question, sql_results):
    """If the question is about a claim and we have SQL results, build a card."""
    if "claim" in question.lower() and sql_results:
        row = sql_results[0]
        if "claim_id" in row:
            return ClaimStatusCard(
                claim_id=row["claim_id"],
                status=row["status"],
                amount=float(row["claim_amount"]),
                date=str(row["date_filed"])
            )
    return None


def try_build_coverage_card(question, sql_results):
    """If the question is about a plan and we have SQL results, build a card."""
    if sql_results and "plan_name" in sql_results[0]:
        row = sql_results[0]
        return CoverageSummaryCard(
            plan_name=row["plan_name"],
            deductible=float(row["annual_deductible"]),
            copay=float(row["copay_pct"]),
            covered=True  # simplification - plan exists, so it's "covered" at the plan level
        )
    return None

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
        if msg.get("citations"):
            with st.expander("📎 Policy sources"):
                for cid in msg["citations"]:
                    st.write(f"- `{cid}`")
        if msg.get("claim_card"):
            render_claim_card(ClaimStatusCard(**msg["claim_card"]))
        if msg.get("coverage_card"):
            render_coverage_card(CoverageSummaryCard(**msg["coverage_card"]))

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
    # STEP 3-6: Stream the response from /chat with stream=True
    # =====================
    with st.chat_message("assistant"):
        message_placeholder = st.empty()  # STEP 3: placeholder to update as tokens arrive
        full_answer = ""

        try:
            with st.spinner("Thinking..."):
                # STEP 3: stream=True tells requests not to wait for the full response
                response = requests.post(
                    BACKEND_URL,
                    json={
                        "session_id": st.session_state.session_id,
                        "member_id": "M1001",
                        "message": user_input
                    },
                    stream=True,
                    timeout=30
                )
                response.raise_for_status()

            # STEP 3: Iterate over the streamed lines as they arrive
            for line in response.iter_lines(decode_unicode=True):
                if not line:
                    continue
                if line.startswith("data: "):
                    token = line[len("data: "):]

                    if token == "[DONE]":
                        break
                    elif token.startswith("[ERROR]"):
                        full_answer = token
                        break
                    else:
                        full_answer += token
                        # STEP 4: update the placeholder so the answer "types out"
                        message_placeholder.write(full_answer)

        except requests.exceptions.Timeout:
            # STEP 6: handle a dropped connection / timeout mid-stream
            full_answer = "The response took too long and timed out. Please try again."
        except requests.exceptions.RequestException as e:
            full_answer = f"Error connecting to the backend: {str(e)}. Please make sure the backend server is running."

        message_placeholder.write(full_answer)

        # =====================
        # STEP 1-2: Fetch and display citations (Policy sources)
        # =====================
        retrieval_result_for_ui = None
        try:
            retrieval_result_for_ui = retrieve(user_input)
        except Exception as e:
            st.error(f"Debug - citation fetch failed: {e}")

        if retrieval_result_for_ui:
            citation_ids = [chunk["id"] for chunk in retrieval_result_for_ui.get("vector_results", [])]
            if citation_ids:
                with st.expander("📎 Policy sources"):
                    for cid in citation_ids:
                        st.write(f"- `{cid}`")

            # =====================
            # STEP 4: Render claim/coverage cards if applicable
            # =====================
            sql_results = retrieval_result_for_ui.get("sql_results", [])

            claim_card = try_build_claim_card(user_input, sql_results)
            if claim_card:
                render_claim_card(claim_card)

            coverage_card = try_build_coverage_card(user_input, sql_results)
            if coverage_card:
                render_coverage_card(coverage_card)

        st.session_state.messages.append({
        "role": "assistant",
        "content": full_answer,
        "citations": citation_ids if retrieval_result_for_ui else [],
        "claim_card": claim_card.model_dump() if 'claim_card' in dir() and claim_card else None,
        "coverage_card": coverage_card.model_dump() if 'coverage_card' in dir() and coverage_card else None
    })

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