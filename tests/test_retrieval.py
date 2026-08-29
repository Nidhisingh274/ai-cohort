"""
Day 29: basic tests for the retrieval engine. These are deterministic -
no LLM calls, no network - so they run fast and free in CI.
"""

from retrieval_engine import classify, retrieve, vector_lookup


def test_classify_structured_deductible():
    """A plan/deductible question should route to structured lookup."""
    assert classify("What is the deductible on the Gold PPO plan?") == "structured"


def test_classify_structured_claim():
    """A claim-status question should route to structured lookup."""
    assert classify("What is the status of claim C1001?") == "structured"


def test_classify_unstructured():
    """A coverage/policy question with no plan data keyword should route
    to unstructured (vector) lookup."""
    assert classify("Is physical therapy covered?") == "unstructured"


def test_retrieve_returns_plan_data():
    """Retrieving a known plan should return its SQL row with the right
    plan_id, not an empty result."""
    result = retrieve("What is the deductible on the Silver HMO plan?")
    assert result["sql_results"], "Expected at least one SQL result"
    assert result["sql_results"][0]["plan_id"] == "P102"


def test_retrieve_claim_returns_correct_row():
    """The Day 27 fix: claim-detail questions must route to SQL and
    return the actual claim row, not an empty context."""
    result = retrieve("What procedure was claim C1001 filed for?")
    assert result["sql_results"], "Expected the claim row to be retrieved"
    assert result["sql_results"][0]["claim_id"] == "C1001"
    assert result["sql_results"][0]["procedure"] == "X-ray"


def test_vector_lookup_returns_chunks():
    """Vector search should return chunks with the expected schema, when
    the Chroma vector store is present. chroma_data/ is gitignored (it's
    a local, regenerable artifact), so on a fresh CI checkout with no
    vector store built yet, this returns an empty list rather than
    failing - the schema check only runs if there is data to check."""
    chunks = vector_lookup("Is physical therapy covered under Silver HMO?", n_results=3)
    if chunks:
        assert "text" in chunks[0]
        assert "id" in chunks[0]
    else:
        import warnings
        warnings.warn("No Chroma data found (chroma_data/ is gitignored) - schema check skipped")