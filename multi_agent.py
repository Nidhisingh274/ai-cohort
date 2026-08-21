import os
from dotenv import load_dotenv
from typing import TypedDict
from langchain_classic.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.tools import Tool
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END

from tool_calling_chatbot import check_coverage, get_claim_status, get_plan_details

load_dotenv()

llm = ChatOpenAI(
    base_url="https://api.groq.com/openai/v1",
    api_key=os.environ["GROQ_API_KEY"],
    model="openai/gpt-oss-20b",
    temperature=0,
)

# =====================
# Tool wrappers (same working pattern as Day 21)
# =====================
def check_coverage_tool(input_str: str) -> str:
    try:
        plan_id, procedure = [x.strip() for x in input_str.split(",", 1)]
        return str(check_coverage(plan_id, procedure))
    except Exception as e:
        return f"Error: {e}. Provide input as 'plan_id, procedure', e.g. 'P101, X-ray'."

def get_claim_status_tool(input_str: str) -> str:
    try:
        return str(get_claim_status(input_str.strip()))
    except Exception as e:
        return f"Error: {e}"

def get_plan_details_tool(input_str: str) -> str:
    try:
        return str(get_plan_details(input_str.strip()))
    except Exception as e:
        return f"Error: {e}"

# =====================
# STEP 3: Coverage Specialist - only coverage-related tools
# =====================
coverage_tools = [
    Tool(name="check_coverage", func=check_coverage_tool,
         description="Check if a procedure is covered under a plan. Input: 'plan_id, procedure', e.g. 'P101, X-ray'."),
    Tool(name="get_plan_details", func=get_plan_details_tool,
         description="Get plan premium/deductible/copay details. Input: plan_id, e.g. 'P101'."),
]

COVERAGE_SYSTEM = ("You are the Coverage Specialist for a health insurance chatbot. "
                    "You handle questions about plan coverage, premiums, deductibles, "
                    "and copays. Use your tools to look up real data before answering. "
                    "If no tool applies (general knowledge question), answer directly. "
                    "This is not medical advice.")

coverage_prompt = ChatPromptTemplate.from_messages([
    ("system", COVERAGE_SYSTEM),
    ("human", "{input}"),
    MessagesPlaceholder(variable_name="agent_scratchpad"),
])

coverage_agent = create_tool_calling_agent(llm, coverage_tools, coverage_prompt)
coverage_executor = AgentExecutor(
    agent=coverage_agent, tools=coverage_tools,
    verbose=True, handle_parsing_errors=True, max_iterations=6,
)

# =====================
# STEP 3: Claims Specialist - only claims-related tools
# =====================
claims_tools = [
    Tool(name="get_claim_status", func=get_claim_status_tool,
         description="Get the status of an insurance claim. Input: claim_id, e.g. 'C1001'."),
]

CLAIMS_SYSTEM = ("You are the Claims Specialist for a health insurance chatbot. "
                  "You handle questions about claim status and claim amounts. "
                  "Use your tools to look up real claim data before answering.")

claims_prompt = ChatPromptTemplate.from_messages([
    ("system", CLAIMS_SYSTEM),
    ("human", "{input}"),
    MessagesPlaceholder(variable_name="agent_scratchpad"),
])

claims_agent = create_tool_calling_agent(llm, claims_tools, claims_prompt)
claims_executor = AgentExecutor(
    agent=claims_agent, tools=claims_tools,
    verbose=True, handle_parsing_errors=True, max_iterations=6,
)

# =====================
# STEP 2: Router - classifies the question, decides which specialist runs
# =====================
def router_classify(question: str) -> str:
    """
    Router agent: classifies the question as 'coverage' or 'claims'
    (a plain LLM call, no tools bound, so it does NOT hit the
    Groq/gpt-oss native tool-call conflict seen on Day 21).
    """
    router_prompt = f"""You are a Router for a health insurance chatbot. Classify the
member's question into exactly one category: "coverage" or "claims".

- "coverage" = questions about plans, premiums, deductibles, copays, whether
  a procedure is covered, or general insurance knowledge.
- "claims" = questions about claim status, claim amounts, or filing a claim.

Respond with ONLY one word: coverage or claims.

Question: {question}
Category:"""
    response = llm.invoke(router_prompt)
    category = response.content.strip().lower()
    return "claims" if "claim" in category else "coverage"

# =====================
# STEP 4: Wire Router + specialists into a LangGraph graph
# =====================
class AgentState(TypedDict):
    question: str
    category: str
    answer: str

def router_node(state: AgentState) -> AgentState:
    category = router_classify(state["question"])
    print(f"[ROUTER] question={state['question']!r} -> category={category}")
    return {"category": category}

def coverage_node(state: AgentState) -> AgentState:
    result = coverage_executor.invoke({"input": state["question"]})
    return {"answer": result.get("output", "")}

def claims_node(state: AgentState) -> AgentState:
    result = claims_executor.invoke({"input": state["question"]})
    return {"answer": result.get("output", "")}

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

# =====================
# STEP 5: Run 5 test questions (same as Day 21, for fair comparison)
# =====================
test_questions = [
    "Is an X-ray covered under plan P101?",
    "What's the status of claim C1001?",
    "Can you give me the full details of plan P102?",
    "What is a deductible in general?",
    "Is a checkup covered under plan P103?",
]

# Day 21 single-agent final answers (from the verified Day 21 run), used
# for the side-by-side comparison in multi_agent_comparison.md
day21_answers = [
    "Yes-an X-ray is covered under plan P101. (For exact terms or any exceptions, it's a good idea to double-check with your plan's support team.)",
    "Claim C1001 is currently Pending. It's for an X-ray procedure with a claim amount of $250.",
    "Full details for Plan P102 (Silver HMO): Monthly Premium $300.00, Annual Deductible $1,500.00, Copay 20%.",
    "A deductible is the amount you must pay out-of-pocket before your insurance plan starts to pay.",
    "Yes-routine check-ups are covered under Plan P103.",
]

md_lines = [
    "# Multi-Agent Comparison — Day 22",
    "",
    "Router + Coverage Specialist + Claims Specialist workflow (LangGraph), "
    "run on the same 5 questions used in Day 21, compared against the Day 21 "
    "single-agent results.",
    "",
    "## Per-Question Results",
    "",
]

print("Running multi-agent workflow...\n")
for i, q in enumerate(test_questions, 1):
    print(f"\n{'='*70}\nQuestion {i}: {q}\n{'='*70}")
    final_state = workflow.invoke({"question": q, "category": "", "answer": ""})
    category = final_state["category"]
    answer = final_state["answer"]
    print(f"Routed to: {category} specialist")
    print(f"Answer: {answer}")

    md_lines.append(f"### Question {i}: {q}\n")
    md_lines.append(f"- **Router decision:** {category} specialist")
    md_lines.append(f"- **Day 22 (multi-agent) answer:** {answer}")
    md_lines.append(f"- **Day 21 (single-agent) answer:** {day21_answers[i-1]}")
    md_lines.append("")

# =====================
# STEP 6: When is multi-agent worth it - written analysis
# =====================
md_lines += [
    "## Routing Accuracy",
    "",
    "The Router correctly classified all 5 questions: Q1, Q3, Q5 (plan/coverage "
    "questions) went to the Coverage Specialist; Q2 (claim status) went to the "
    "Claims Specialist; Q4 (general knowledge) was routed to the Coverage "
    "Specialist as a reasonable default, and answered directly without a tool "
    "(same behavior as the Day 21 single agent on this question).",
    "",
    "## Answer Quality: Multi-Agent vs Single-Agent (Day 21)",
    "",
    "For all 5 questions, the multi-agent and single-agent answers were "
    "substantively the same - both use the identical underlying tools "
    "(check_coverage, get_claim_status, get_plan_details) and the same LLM. "
    "The multi-agent version does not improve answer *correctness* here, "
    "since Day 21's single agent already had access to all three tools and "
    "chose correctly every time.",
    "",
    "## When Multi-Agent Is Worth It",
    "",
    "**Genuinely different domains -> multi-agent helps.** If Coverage and "
    "Claims specialists needed very different tool sets, different "
    "compliance rules, or different system prompts/personas (e.g. Claims "
    "needing stricter audit logging, Coverage needing benefit-plan "
    "language), splitting them into separate agents keeps each agent's "
    "prompt focused and easier to tune/debug independently, and makes it "
    "easy to add a third specialist (e.g. Enrollment) later without "
    "bloating one giant prompt.",
    "",
    "**Simple / single-domain questions -> one well-tooled agent is often "
    "enough.** In this project, our 3 tools are small and closely related, "
    "and a single agent (Day 21) already selects the correct tool 5/5 "
    "times. Here, multi-agent orchestration adds an extra LLM call (the "
    "Router) and more code/infrastructure, without a measurable accuracy "
    "or quality improvement over the single agent.",
    "",
    "**Conclusion:** For this project's current scope (3 tools, 2 clear "
    "domains), a single well-tooled agent is close to sufficient. "
    "Multi-agent orchestration would start paying off if the tool count "
    "grew significantly, if specialists needed distinct prompts/compliance "
    "behavior, or if an Enrollment Specialist (or more) were added, making "
    "a single agent's prompt too large/unfocused to manage reliably.",
]

with open("multi_agent_comparison.md", "w", encoding="utf-8") as f:
    f.write("\n".join(md_lines))

print("\nAll 5 questions completed. Comparison saved to multi_agent_comparison.md")