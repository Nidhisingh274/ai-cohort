import os
import json
import sqlite3
from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel, ValidationError

load_dotenv()

client = OpenAI(
    base_url="https://api.groq.com/openai/v1",
    api_key=os.environ["GROQ_API_KEY"],
)

MODEL_NAME = "llama-3.1-8b-instant"

# =====================
# STEP 4: Pydantic models - define the EXPECTED SHAPE of each tool's output
# =====================
class CoverageResult(BaseModel):
    plan_id: str
    procedure: str
    covered: bool
    notes: str

class ClaimStatusResult(BaseModel):
    claim_id: str
    status: str
    procedure: str
    claim_amount: float

class PlanDetailsResult(BaseModel):
    plan_id: str
    plan_name: str
    monthly_premium: float
    annual_deductible: float
    copay_pct: float

class OutOfPocketResult(BaseModel):
    plan_id: str
    procedure: str
    estimated_cost: float
    notes: str

# =====================
# STEP 1: Tool functions - these actually run against coverage.db
# =====================

def check_coverage(plan_id, procedure):
    """Check if a procedure is covered under a given plan (simplified mock logic)."""
    conn = sqlite3.connect("coverage.db")
    cursor = conn.execute("SELECT * FROM plans WHERE plan_id = ?", (plan_id,))
    row = cursor.fetchone()
    conn.close()

    if row is None:
        raw_result = {
            "plan_id": plan_id,
            "procedure": procedure,
            "covered": False,
            "notes": "Plan not found in our records."
        }
    else:
        # Mock logic: our sample data doesn't have per-procedure coverage,
        # so we treat common procedures as covered, and flag unknowns.
        common_procedures = ["x-ray", "surgery", "checkup", "consultation"]
        is_covered = procedure.lower() in common_procedures
        raw_result = {
            "plan_id": plan_id,
            "procedure": procedure,
            "covered": is_covered,
            "notes": "Based on standard plan coverage. Confirm with support for exact terms."
        }

    # STEP 4: Validate with Pydantic before returning
    validated = CoverageResult(**raw_result)
    return validated.model_dump()


def get_claim_status(claim_id):
    """Look up a claim's status from coverage.db."""
    conn = sqlite3.connect("coverage.db")
    cursor = conn.execute("SELECT * FROM claims WHERE claim_id = ?", (claim_id,))
    row = cursor.fetchone()
    conn.close()

    if row is None:
        raw_result = {
            "claim_id": claim_id,
            "status": "not_found",
            "procedure": "unknown",
            "claim_amount": 0.0
        }
    else:
        raw_result = {
            "claim_id": row[0],
            "status": row[5],
            "procedure": row[3],
            "claim_amount": float(row[4])
        }

    validated = ClaimStatusResult(**raw_result)
    return validated.model_dump()


def get_plan_details(plan_id):
    """Get full details for a given plan."""
    conn = sqlite3.connect("coverage.db")
    cursor = conn.execute("SELECT * FROM plans WHERE plan_id = ?", (plan_id,))
    row = cursor.fetchone()
    conn.close()

    if row is None:
        raw_result = {
            "plan_id": plan_id,
            "plan_name": "unknown",
            "monthly_premium": 0.0,
            "annual_deductible": 0.0,
            "copay_pct": 0.0
        }
    else:
        raw_result = {
            "plan_id": row[0],
            "plan_name": row[1],
            "monthly_premium": float(row[2]),
            "annual_deductible": float(row[3]),
            "copay_pct": float(row[4])
        }

    validated = PlanDetailsResult(**raw_result)
    return validated.model_dump()


def estimate_out_of_pocket_cost(procedure, plan_id):
    """Estimate what a member would pay out-of-pocket (simplified mock logic)."""
    conn = sqlite3.connect("coverage.db")
    cursor = conn.execute("SELECT * FROM plans WHERE plan_id = ?", (plan_id,))
    row = cursor.fetchone()
    conn.close()

    if row is None:
        raw_result = {
            "plan_id": plan_id,
            "procedure": procedure,
            "estimated_cost": 0.0,
            "notes": "Plan not found - cannot estimate cost."
        }
    else:
        copay_pct = row[4]
        # Mock base costs for a few sample procedures
        base_costs = {"x-ray": 250, "surgery": 5000, "checkup": 150, "consultation": 100}
        base_cost = base_costs.get(procedure.lower(), 500)  # default estimate
        estimated = round(base_cost * (copay_pct / 100), 2)

        raw_result = {
            "plan_id": plan_id,
            "procedure": procedure,
            "estimated_cost": estimated,
            "notes": f"Estimate based on {copay_pct}% copay on a typical ${base_cost} procedure cost."
        }

    validated = OutOfPocketResult(**raw_result)
    return validated.model_dump()

# =====================
# STEP 2: Tool schemas - tell the LLM what functions exist and how to call them
# =====================
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "check_coverage",
            "description": "Check if a specific medical procedure is covered under a given insurance plan.",
            "parameters": {
                "type": "object",
                "properties": {
                    "plan_id": {"type": "string", "description": "The plan ID, e.g. P101"},
                    "procedure": {"type": "string", "description": "The medical procedure name, e.g. 'X-ray'"}
                },
                "required": ["plan_id", "procedure"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_claim_status",
            "description": "Get the current status of a specific insurance claim by its claim ID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "claim_id": {"type": "string", "description": "The claim ID, e.g. C1001"}
                },
                "required": ["claim_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_plan_details",
            "description": "Get full details (premium, deductible, copay) for a specific insurance plan.",
            "parameters": {
                "type": "object",
                "properties": {
                    "plan_id": {"type": "string", "description": "The plan ID, e.g. P101"}
                },
                "required": ["plan_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "estimate_out_of_pocket_cost",
            "description": "Estimate what a member would pay out-of-pocket for a procedure under a given plan.",
            "parameters": {
                "type": "object",
                "properties": {
                    "procedure": {"type": "string", "description": "The medical procedure name"},
                    "plan_id": {"type": "string", "description": "The plan ID, e.g. P101"}
                },
                "required": ["procedure", "plan_id"]
            }
        }
    }
]

# Map tool names (as strings) to the actual Python functions
AVAILABLE_FUNCTIONS = {
    "check_coverage": check_coverage,
    "get_claim_status": get_claim_status,
    "get_plan_details": get_plan_details,
    "estimate_out_of_pocket_cost": estimate_out_of_pocket_cost,
}

# Day 12 winning system prompt (Variant E), adapted for tool use
SYSTEM_PROMPT = """You are a warm, professional health coverage assistant. Members may be
stressed about medical costs, so answer clearly, kindly, and concisely.

You have access to tools that look up real plan, claim, and coverage
data. Use a tool whenever the question requires specific plan/claim
information you don't already have. If no tool is needed to answer
(e.g. a general question), just answer directly.

This is not medical advice. For any medical questions, please consult a
licensed healthcare provider."""

# =====================
# STEP 3: Tool-execution loop
# =====================
TOOL_CALL_LOG = []  # collects every tool call made, for Step 6 logging

def ask_with_tools(question):
    """
    Send the question to the LLM with available tools. If the LLM
    requests a tool call, execute it and feed the result back for a
    final natural-language answer.
    """
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": question}
    ]

    # First call - let the model decide if it needs a tool
    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=messages,
            tools=TOOLS
        )
    except Exception as e:
        # Groq's smaller models occasionally fail to format a tool call
        # correctly. Log this as a failed attempt and return gracefully
        # instead of crashing the whole run.
        TOOL_CALL_LOG.append({
            "question": question,
            "tool_used": "error",
            "arguments": None,
            "result": f"Tool call generation failed: {str(e)}"
        })
        return "I'm having trouble processing that request right now. Please try rephrasing your question or contact support."

    response_message = response.choices[0].message
    tool_calls = response_message.tool_calls

    if not tool_calls:
        # No tool was needed - return the direct answer
        TOOL_CALL_LOG.append({
            "question": question,
            "tool_used": "none",
            "arguments": None,
            "result": None
        })
        return response_message.content

    # Model wants to call one or more tools
    messages.append(response_message)

    for tool_call in tool_calls:
        function_name = tool_call.function.name
        function_args = json.loads(tool_call.function.arguments)

        function_to_call = AVAILABLE_FUNCTIONS[function_name]
        function_result = function_to_call(**function_args)

        # Log this tool call (Step 6)
        TOOL_CALL_LOG.append({
            "question": question,
            "tool_used": function_name,
            "arguments": function_args,
            "result": function_result
        })

        # Feed the tool's result back to the model
        messages.append({
            "role": "tool",
            "tool_call_id": tool_call.id,
            "content": json.dumps(function_result)
        })

    # Second call - model generates the final natural-language answer
    final_response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=messages
    )

    return final_response.choices[0].message.content