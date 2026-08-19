from pydantic import BaseModel

# =====================
# STEP 3: Structured card schemas for rich UI rendering
# =====================

class ClaimStatusCard(BaseModel):
    """Represents a single claim's status, for card-style rendering in the UI."""
    claim_id: str
    status: str
    amount: float
    date: str


class CoverageSummaryCard(BaseModel):
    """Represents a plan's coverage summary, for card-style rendering in the UI."""
    plan_name: str
    deductible: float
    copay: float
    covered: bool