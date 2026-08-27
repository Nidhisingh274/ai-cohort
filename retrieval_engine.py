import os
import sys
import sqlite3
import chromadb
from sentence_transformers import SentenceTransformer

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "coverage.db")

# =====================
# Setup: connect to SQL and Vector DB once
# =====================
print("Loading embedding model...", file=sys.stderr)
model = SentenceTransformer("all-MiniLM-L6-v2")

def embed(text):
    return model.encode(text).tolist()

CHROMA_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "chroma_data")
client = chromadb.PersistentClient(path=CHROMA_PATH)
collection = client.get_or_create_collection(name="coverage_kb")

print("Retrieval engine ready.\n", file=sys.stderr)

# =====================
# STEP 1: Question Classifier
# =====================
STRUCTURED_KEYWORDS = [
    "deductible", "premium", "copay", "claim status", "claim id",
    "how much", "cost", "price", "status of claim", "monthly",
    # Day 27 fix: claim-detail phrasing was routing to vector search only,
    # so claim rows never reached the context (see ragas_scorecard.md).
    "procedure", "filed", "date filed", "when was", "claim amount",
]

UNSTRUCTURED_KEYWORDS = [
    "covered", "coverage", "exclusion", "excluded", "benefit",
    "eligible", "does it cover", "is it covered", "process", "how do i file"
]

def classify(question):
    """Classify a question as 'structured', 'unstructured', or 'both'."""
    q_lower = question.lower()

    has_structured = any(keyword in q_lower for keyword in STRUCTURED_KEYWORDS)
    has_unstructured = any(keyword in q_lower for keyword in UNSTRUCTURED_KEYWORDS)

    if has_structured and has_unstructured:
        return "both"
    elif has_structured:
        return "structured"
    elif has_unstructured:
        return "unstructured"
    else:
        # Default to unstructured (safer for coverage-related questions)
        return "unstructured"

# =====================
# STEP 2: SQL Lookup (structured data)
# =====================
def sql_lookup(question):
    """
    Query coverage.db based on keywords in the question.
    Uses simple template matching - looks for plan names or claim IDs
    mentioned in the question.
    """
    conn = sqlite3.connect(DB_PATH)
    q_lower = question.lower()
    results = []

    # Try to detect a plan name mentioned in the question
    known_plans = ["gold ppo", "silver hmo", "bronze hmo", "gold", "silver", "bronze"]
    mentioned_plan = None
    for plan in known_plans:
        if plan in q_lower:
            mentioned_plan = plan
            break

    # Try to detect a claim ID pattern (e.g. "C1001")
    import re
    claim_match = re.search(r"\bC\d{4}\b", question, re.IGNORECASE)

    if claim_match:
        claim_id = claim_match.group().upper()
        cursor = conn.execute(
            "SELECT * FROM claims WHERE claim_id = ?", (claim_id,)
        )
        rows = cursor.fetchall()
        col_names = [desc[0] for desc in cursor.description]
        for row in rows:
            results.append(dict(zip(col_names, row)))

    elif mentioned_plan:
        # Match against plan_name using LIKE for partial matches (e.g. "gold" matches "Gold PPO")
        cursor = conn.execute(
            "SELECT * FROM plans WHERE LOWER(plan_name) LIKE ?",
            (f"%{mentioned_plan}%",)
        )
        rows = cursor.fetchall()
        col_names = [desc[0] for desc in cursor.description]
        for row in rows:
            results.append(dict(zip(col_names, row)))

    else:
        # No specific plan/claim mentioned - return all plans as fallback
        cursor = conn.execute("SELECT * FROM plans")
        rows = cursor.fetchall()
        col_names = [desc[0] for desc in cursor.description]
        for row in rows:
            results.append(dict(zip(col_names, row)))

    conn.close()
    return results


# =====================
# STEP 3: Vector Lookup (unstructured data)
# =====================
def vector_lookup(question, n_results=5):
    """Embed the question and retrieve top-N relevant chunks from Chroma."""
    query_vector = embed(question)
    results = collection.query(
        query_embeddings=[query_vector],
        n_results=n_results
    )

    chunks = []
    for i in range(len(results["ids"][0])):
        chunks.append({
            "id": results["ids"][0][i],
            "text": results["documents"][0][i],
            "plan_type": results["metadatas"][0][i]["plan_type"],
            "section": results["metadatas"][0][i]["section"],
            "distance": results["distances"][0][i]
        })
    return chunks

# =====================
# STEP 4: retrieve() - routes and merges results
# =====================
def retrieve(question):
    """
    Main routing function. Classifies the question, calls the
    appropriate lookup(s), and merges results into one context block.
    """
    classification = classify(question)

    sql_results = []
    vector_results = []

    if classification in ("structured", "both"):
        sql_results = sql_lookup(question)

    if classification in ("unstructured", "both"):
        vector_results = vector_lookup(question)

    # =====================
    # Merge and de-duplicate into one context block
    # =====================
    context_parts = []

    if sql_results:
        context_parts.append("=== Structured Data (SQL) ===")
        for row in sql_results:
            context_parts.append(str(row))

    if vector_results:
        context_parts.append("\n=== Policy Text (Vector Search) ===")
        seen_texts = set()  # for de-duplication
        for chunk in vector_results:
            if chunk["text"] not in seen_texts:
                context_parts.append(
                    f"[{chunk['plan_type']} | {chunk['section']}] {chunk['text']}"
                )
                seen_texts.add(chunk["text"])

    merged_context = "\n".join(context_parts)

    return {
        "question": question,
        "classification": classification,
        "sql_results": sql_results,
        "vector_results": vector_results,
        "context": merged_context
    }


# =====================
# Quick manual test (only runs if this file is executed directly)
# =====================
if __name__ == "__main__":
    test_q = "What's my deductible on the Gold plan?"
    result = retrieve(test_q)
    print(f"Question: {result['question']}")
    print(f"Classification: {result['classification']}")
    print(f"\nMerged Context:\n{result['context']}")