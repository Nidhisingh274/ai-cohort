import os
import sqlite3
import asyncio
from dotenv import load_dotenv
from typing import TypedDict
from langchain_classic.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.tools import Tool
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END

# =====================
# STEP 1: Call the Day 23 MCP tools from this Day 22 workflow.
#
# get_claim_status goes over the REAL MCP protocol (spawn mcp_server.py as
# a subprocess, stdio handshake, tools/call) - measured at ~2.2s per call,
# well inside this mission's 10s budget.
#
# check_coverage uses a direct in-process import of the same @mcp.tool()
# function. Measured over the protocol it takes 300+ seconds per call on
# this machine (8GB RAM, CPU-only), because each subprocess reloads the
# all-MiniLM-L6-v2 embedding model from scratch - 30x over the 10s budget,
# so every call would time out, retry, and fall back with no real answer.
# See chaos_test.md for the measurements.
# =====================
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from mcp_server import check_coverage as mcp_check_coverage
from mcp_server import DB_PATH

load_dotenv()

SERVER_PARAMS = StdioServerParameters(
    command=os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         ".venv", "Scripts", "python.exe"),
    args=[os.path.join(os.path.dirname(os.path.abspath(__file__)), "mcp_server.py")],
)


async def call_mcp_tool_over_protocol(tool_name: str, arguments: dict) -> str:
    """Real MCP client call: spawn the Day 23 server over stdio, complete the
    handshake, invoke the tool by name, and return its text result."""
    async with stdio_client(SERVER_PARAMS) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(tool_name, arguments)
            return result.content[0].text


llm = ChatOpenAI(
    base_url="https://api.groq.com/openai/v1",
    api_key=os.environ["GROQ_API_KEY"],
    model="openai/gpt-oss-20b",
    temperature=0,
)

# =====================
# STEP 3-4: 10s timeout, max 1 retry, canned fallback
# =====================
TOOL_TIMEOUT = 10
MAX_RETRIES = 1
FALLBACK_MESSAGE = (
    "I'm having trouble accessing that right now, please contact member support."
)


async def _call_with_timeout(func, *args):
    return await asyncio.wait_for(asyncio.to_thread(func, *args), timeout=TOOL_TIMEOUT)


def resilient_tool_call(func, *args, tool_name="tool"):
    """
    STEP 3-4: 10s timeout + up to MAX_RETRIES retries. Any failure returns
    the canned support message - the member never sees a raw 500.
    """
    attempts = MAX_RETRIES + 1
    for attempt in range(1, attempts + 1):
        try:
            result = asyncio.run(_call_with_timeout(func, *args))
            print(f"[TOOL OK] {tool_name} succeeded on attempt {attempt}")
            return result
        except asyncio.TimeoutError:
            print(f"[TOOL TIMEOUT] {tool_name} attempt {attempt}/{attempts} exceeded {TOOL_TIMEOUT}s")
        except Exception as e:
            print(f"[TOOL ERROR] {tool_name} attempt {attempt}/{attempts} failed: {type(e).__name__}: {e}")

    print(f"[FALLBACK] {tool_name} failed after {attempts} attempts - returning canned support message")
    return FALLBACK_MESSAGE


def check_coverage_tool(input_str: str) -> str:
    try:
        plan_name, question = [x.strip() for x in input_str.split(",", 1)]
    except ValueError:
        return "Please provide input as 'plan_name, question', e.g. 'Silver HMO, Is physical therapy covered?'"
    return resilient_tool_call(mcp_check_coverage, plan_name, question, tool_name="check_coverage")


def _get_claim_status_via_protocol(claim_id: str) -> str:
    """Calls the Day 23 MCP server over the real MCP protocol."""
    return asyncio.run(
        call_mcp_tool_over_protocol("get_claim_status", {"claim_id": claim_id})
    )


def get_claim_status_tool(input_str: str) -> str:
    return resilient_tool_call(
        _get_claim_status_via_protocol, input_str.strip(), tool_name="get_claim_status"
    )


# =====================
# STEP 2: Day 20 conversation memory
# =====================
def load_history(session_id, limit=10):
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.execute(
            "SELECT role, content FROM conversations WHERE session_id = ? ORDER BY id DESC LIMIT ?",
            (session_id, limit),
        )
        rows = cursor.fetchall()
        conn.close()
        return [{"role": r[0], "content": r[1]} for r in reversed(rows)]
    except Exception as e:
        print(f"[MEMORY] Could not load history: {e}")
        return []


def save_turn(session_id, role, content):
    try:
        from datetime import datetime
        conn = sqlite3.connect(DB_PATH)
        conn.execute(
            "INSERT INTO conversations (session_id, role, content, timestamp) VALUES (?, ?, ?, ?)",
            (session_id, role, content, datetime.now().isoformat()),
        )
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[MEMORY] Could not save turn: {e}")


KNOWN_PLANS = {
    "gold ppo": "P101", "silver hmo": "P102", "bronze hmo": "P103",
    "gold": "P101", "silver": "P102", "bronze": "P103",
}


def detect_plan(history):
    plan_id, plan_name = None, None
    for turn in history:
        lowered = turn["content"].lower()
        for name, pid in KNOWN_PLANS.items():
            if name in lowered:
                plan_id, plan_name = pid, name
    return plan_id, plan_name


coverage_tools = [
    Tool(name="check_coverage", func=check_coverage_tool,
         description="Check plan coverage details. Input MUST be 'plan_name, question' where plan_name is exactly one of: 'Gold PPO', 'Silver HMO', 'Bronze HMO'. Example: 'Silver HMO, What is my deductible?'"),
]

claims_tools = [
    Tool(name="get_claim_status", func=get_claim_status_tool,
         description="Get the status of an insurance claim. Input: claim_id, e.g. 'C1001'."),
]


def build_executor(system_prompt, tools):
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", "{input}"),
        MessagesPlaceholder(variable_name="agent_scratchpad"),
    ])
    agent = create_tool_calling_agent(llm, tools, prompt)
    return AgentExecutor(agent=agent, tools=tools, verbose=True,
                         handle_parsing_errors=True, max_iterations=6)


COVERAGE_SYSTEM = ("You are the Coverage Specialist for a health insurance chatbot. "
                   "You handle questions about plan coverage, premiums, deductibles and "
                   "copays. Use your tools to look up real data before answering. "
                   "This is not medical advice.")

CLAIMS_SYSTEM = ("You are the Claims Specialist for a health insurance chatbot. "
                 "You handle questions about claim status and claim amounts. "
                 "Use your tools to look up real claim data before answering.")


def router_classify(question: str) -> str:
    router_prompt = f"""You are a Router for a health insurance chatbot. Classify the
member's question into exactly one category: "coverage" or "claims".

- "coverage" = plans, premiums, deductibles, copays, whether a procedure is
  covered, or general insurance knowledge.
- "claims" = claim status, claim amounts, or filing a claim.

Respond with ONLY one word: coverage or claims.

Question: {question}
Category:"""
    try:
        response = llm.invoke(router_prompt)
        category = response.content.strip().lower()
        return "claims" if "claim" in category else "coverage"
    except Exception as e:
        print(f"[ROUTER ERROR] {e} - defaulting to coverage")
        return "coverage"


class AgentState(TypedDict):
    question: str
    session_id: str
    category: str
    plan_context: str
    answer: str


def router_node(state: AgentState) -> AgentState:
    history = load_history(state["session_id"])
    plan_id, plan_name = detect_plan(history + [{"role": "user", "content": state["question"]}])
    plan_context = ""
    if plan_id:
        plan_context = (f"\n\nRemembered context: the member has been discussing the "
                        f"{plan_name.title()} plan (plan_id: {plan_id}). If they don't "
                        f"repeat the plan name, assume they still mean this plan.")
    category = router_classify(state["question"])
    print(f"[ROUTER] question={state['question']!r} -> category={category} plan={plan_name}")
    return {"category": category, "plan_context": plan_context}


def coverage_node(state: AgentState) -> AgentState:
    executor = build_executor(COVERAGE_SYSTEM + state["plan_context"], coverage_tools)
    try:
        result = executor.invoke({"input": state["question"]})
        answer = result.get("output", FALLBACK_MESSAGE)
    except Exception as e:
        print(f"[AGENT ERROR] coverage specialist failed: {e}")
        answer = FALLBACK_MESSAGE
    return {"answer": answer}


def claims_node(state: AgentState) -> AgentState:
    executor = build_executor(CLAIMS_SYSTEM + state["plan_context"], claims_tools)
    try:
        result = executor.invoke({"input": state["question"]})
        answer = result.get("output", FALLBACK_MESSAGE)
    except Exception as e:
        print(f"[AGENT ERROR] claims specialist failed: {e}")
        answer = FALLBACK_MESSAGE
    return {"answer": answer}


def route_decision(state: AgentState) -> str:
    return state["category"]


graph = StateGraph(AgentState)
graph.add_node("router", router_node)
graph.add_node("coverage_specialist", coverage_node)
graph.add_node("claims_specialist", claims_node)
graph.set_entry_point("router")
graph.add_conditional_edges("router", route_decision, {
    "coverage": "coverage_specialist",
    "claims": "claims_specialist",
})
graph.add_edge("coverage_specialist", END)
graph.add_edge("claims_specialist", END)

workflow = graph.compile()


def ask(question: str, session_id: str = "day24-session"):
    save_turn(session_id, "user", question)
    final_state = workflow.invoke({
        "question": question, "session_id": session_id,
        "category": "", "plan_context": "", "answer": "",
    })
    answer = final_state["answer"]
    save_turn(session_id, "assistant", answer)
    return final_state["category"], answer


if __name__ == "__main__":
    import uuid
    session_id = f"day24-{uuid.uuid4()}"
    print(f"Session: {session_id}\n")

    test_questions = [
        "I'm on the Silver HMO plan.",
        "What's my deductible?",
        "What's the status of claim C1001?",
    ]

    for i, q in enumerate(test_questions, 1):
        print(f"\n{'='*70}\nQuestion {i}: {q}\n{'='*70}")
        category, answer = ask(q, session_id)
        print(f"Routed to: {category} specialist")
        print(f"Answer: {answer}")

    print("\nAll questions completed.")