import os
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"

import sqlite3
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("coverage-mcp-server")

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "coverage.db")


@mcp.tool()
def check_coverage(plan_name: str, question: str) -> str:
    """Check coverage details for a health plan. Combines structured plan
    data (premium, deductible, copay) with relevant policy text found via
    semantic search, so the AI client can answer coverage questions.

    Args:
        plan_name: The plan name, e.g. "Gold PPO", "Silver HMO", "Bronze HMO"
        question: The member's coverage question, e.g. "Is physical therapy covered?"
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.execute(
        "SELECT * FROM plans WHERE LOWER(plan_name) LIKE ?",
        (f"%{plan_name.lower()}%",)
    )
    row = cursor.fetchone()
    col_names = [desc[0] for desc in cursor.description]
    conn.close()
    plan_info = dict(zip(col_names, row)) if row else {"error": f"Plan '{plan_name}' not found"}

    # Imported here (not at module level) so the MCP server itself starts
    # instantly - the embedding model only loads when this tool is used.
    try:
        from retrieval_engine import vector_lookup
        chunks = vector_lookup(question, n_results=3)
        policy_text = "\n".join([f"[{c['plan_type']}] {c['text']}" for c in chunks])
    except Exception as e:
        policy_text = f"(Policy text search unavailable: {e})"

    return f"Plan data: {plan_info}\n\nRelevant policy text:\n{policy_text}"


@mcp.tool()
def get_claim_status(claim_id: str) -> str:
    """Get the current status of an insurance claim by its claim ID.

    Args:
        claim_id: The claim ID, e.g. "C1001"
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.execute("SELECT * FROM claims WHERE claim_id = ?", (claim_id,))
    row = cursor.fetchone()
    col_names = [desc[0] for desc in cursor.description]
    conn.close()

    if row is None:
        return f"No claim found with ID {claim_id}"

    return str(dict(zip(col_names, row)))


if __name__ == "__main__":
    mcp.run()