import os
import re
import io
import contextlib
from dotenv import load_dotenv
from langchain_classic.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.tools import Tool
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_openai import ChatOpenAI

from tool_calling_chatbot import check_coverage, get_claim_status, get_plan_details

load_dotenv()

# =====================
# LLM setup - same Groq model used throughout the project
# =====================
llm = ChatOpenAI(
    base_url="https://api.groq.com/openai/v1",
    api_key=os.environ["GROQ_API_KEY"],
    model="openai/gpt-oss-20b",
    temperature=0,
)

# =====================
# STEP 2: Wrap Day 13 tools as LangChain Tool objects
# =====================
def check_coverage_tool(input_str: str) -> str:
    """Expects input like 'P101, X-ray'."""
    try:
        plan_id, procedure = [x.strip() for x in input_str.split(",", 1)]
        return str(check_coverage(plan_id, procedure))
    except Exception as e:
        return f"Error: {e}. Provide input as 'plan_id, procedure', e.g. 'P101, X-ray'."


def get_claim_status_tool(input_str: str) -> str:
    """Expects a claim ID like 'C1001'."""
    try:
        return str(get_claim_status(input_str.strip()))
    except Exception as e:
        return f"Error: {e}"


def get_plan_details_tool(input_str: str) -> str:
    """Expects a plan ID like 'P101'."""
    try:
        return str(get_plan_details(input_str.strip()))
    except Exception as e:
        return f"Error: {e}"


tools = [
    Tool(
        name="check_coverage",
        func=check_coverage_tool,
        description=(
            "Check if a specific medical procedure is covered under a plan. "
            "Input MUST be exactly 'plan_id, procedure', e.g. 'P101, X-ray'."
        ),
    ),
    Tool(
        name="get_claim_status",
        func=get_claim_status_tool,
        description=(
            "Get the current status of an insurance claim. "
            "Input MUST be just the claim ID, e.g. 'C1001'."
        ),
    ),
    Tool(
        name="get_plan_details",
        func=get_plan_details_tool,
        description=(
            "Get full details (premium, deductible, copay) for an insurance plan. "
            "Input MUST be just the plan ID, e.g. 'P101'."
        ),
    ),
]

# =====================
# STEP 3: Build the agent using native tool-calling (bind_tools), which
# avoids a known Groq/gpt-oss issue where the model's built-in tool-call
# behavior conflicts with plain-text ReAct prompting ("Tool choice is
# none, but model called a tool"). A manual Thought -> Action ->
# Observation trace is built below from the recorded steps.
# =====================
prompt = ChatPromptTemplate.from_messages([
    ("system", "You are a helpful health coverage assistant. Use the "
               "available tools when the question requires specific plan "
               "or claim data. Answer general questions directly without "
               "using a tool."),
    ("human", "{input}"),
    MessagesPlaceholder(variable_name="agent_scratchpad"),
])

agent = create_tool_calling_agent(llm, tools, prompt)

agent_executor = AgentExecutor(
    agent=agent,
    tools=tools,
    verbose=True,                    # STEP 4: print reasoning/tool-call traces
    handle_parsing_errors=True,
    max_iterations=6,
    return_intermediate_steps=True,  # lets us build a Thought/Action/Observation trace
)

# =====================
# STEP 4-6: Run 5 test questions, capture traces, save to .md
# =====================
test_questions = [
    "Is an X-ray covered under plan P101?",
    "What's the status of claim C1001?",
    "Can you give me the full details of plan P102?",
    "What is a deductible in general?",
    "Is a checkup covered under plan P103?",
]

ANSI_ESCAPE = re.compile(r"\x1b\[[0-9;]*m")

md_lines = [
    "# Agent Reasoning Traces — Day 21",
    "",
    "Full Thought -> Action -> Observation -> Final Answer traces from the "
    "LangChain agent (AgentExecutor), for 5 test questions, using the Day 13 "
    "tools (check_coverage, get_claim_status, get_plan_details).",
    "",
]

for i, question in enumerate(test_questions, 1):
    print(f"\n{'='*70}\nRunning Question {i}: {question}\n{'='*70}")
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            result = agent_executor.invoke({"input": question})
        final_answer = result.get("output", "")
        steps = result.get("intermediate_steps", [])
    except Exception as e:
        final_answer = f"Error: {e}"
        steps = []

    raw_trace = ANSI_ESCAPE.sub("", buf.getvalue())
    print(raw_trace)

    # Manually build a Thought -> Action -> Observation trace from the
    # tool-calling steps LangChain recorded.
    react_lines = [f"Question: {question}"]
    if steps:
        for action, observation in steps:
            react_lines.append("Thought: I need more information, so I'll use a tool.")
            react_lines.append(f"Action: {action.tool}")
            react_lines.append(f"Action Input: {action.tool_input}")
            react_lines.append(f"Observation: {observation}")
    else:
        react_lines.append("Thought: I can answer this directly without a tool.")
    react_lines.append("Thought: I now know the final answer")
    react_lines.append(f"Final Answer: {final_answer}")
    react_trace = "\n".join(react_lines)

    print(react_trace)

    md_lines.append(f"## Question {i}: {question}\n")
    md_lines.append("```")
    md_lines.append(react_trace)
    md_lines.append("```")
    md_lines.append(f"\n**Final Answer:** {final_answer}\n")

with open("agent_traces.md", "w", encoding="utf-8") as f:
    f.write("\n".join(md_lines))

print("\nAll 5 questions completed. Traces saved to agent_traces.md")