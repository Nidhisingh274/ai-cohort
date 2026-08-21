# Multi-Agent Comparison — Day 22

Router + Coverage Specialist + Claims Specialist workflow (LangGraph), run on the same 5 questions used in Day 21, compared against the Day 21 single-agent results.

## Per-Question Results

### Question 1: Is an X-ray covered under plan P101?

- **Router decision:** coverage specialist
- **Day 22 (multi-agent) answer:** Yes—an X‑ray is covered under Plan P101. If you need details on any copay, deductible, or specific limits for that service, let me know and I can pull up the exact plan terms for you.
- **Day 21 (single-agent) answer:** Yes-an X-ray is covered under plan P101. (For exact terms or any exceptions, it's a good idea to double-check with your plan's support team.)

### Question 2: What's the status of claim C1001?

- **Router decision:** claims specialist
- **Day 22 (multi-agent) answer:** **Claim C1001**  
- **Status:** Pending  
- **Procedure:** X‑ray  
- **Claim Amount:** $250.00  

Your claim is currently in the pending stage. If you need more details or have any questions, just let me know!
- **Day 21 (single-agent) answer:** Claim C1001 is currently Pending. It's for an X-ray procedure with a claim amount of $250.

### Question 3: Can you give me the full details of plan P102?

- **Router decision:** coverage specialist
- **Day 22 (multi-agent) answer:** Here are the full details for **Plan P102 – Silver HMO**:

| Item | Value |
|------|-------|
| **Plan ID** | P102 |
| **Plan Name** | Silver HMO |
| **Monthly Premium** | $300.00 |
| **Annual Deductible** | $1,500.00 |
| **Copay Percentage** | 20% of the cost of covered services |

Let me know if you’d like more information, such as covered services, network details, or how the copay applies to specific procedures.
- **Day 21 (single-agent) answer:** Full details for Plan P102 (Silver HMO): Monthly Premium $300.00, Annual Deductible $1,500.00, Copay 20%.

### Question 4: What is a deductible in general?

- **Router decision:** coverage specialist
- **Day 22 (multi-agent) answer:** A deductible is the amount of money you must pay out‑of‑pocket for covered medical services before your insurance plan starts paying. Think of it as the portion of the bill that you’re responsible for first. Once you’ve met the deductible, the plan typically covers a larger share of subsequent costs (often through copays, coinsurance, or full coverage). The deductible can be a fixed dollar amount for the year, or it may vary by type of service (e.g., separate deductibles for prescription drugs vs. general care).
- **Day 21 (single-agent) answer:** A deductible is the amount you must pay out-of-pocket before your insurance plan starts to pay.

### Question 5: Is a checkup covered under plan P103?

- **Router decision:** coverage specialist
- **Day 22 (multi-agent) answer:** Yes—routine check‑ups are covered under Plan P103. (If you need specifics on copays or any exclusions, let me know and I can pull the exact details.)
- **Day 21 (single-agent) answer:** Yes-routine check-ups are covered under Plan P103.

## Routing Accuracy

The Router correctly classified all 5 questions: Q1, Q3, Q5 (plan/coverage questions) went to the Coverage Specialist; Q2 (claim status) went to the Claims Specialist; Q4 (general knowledge) was routed to the Coverage Specialist as a reasonable default, and answered directly without a tool (same behavior as the Day 21 single agent on this question).

## Answer Quality: Multi-Agent vs Single-Agent (Day 21)

For all 5 questions, the multi-agent and single-agent answers were substantively the same - both use the identical underlying tools (check_coverage, get_claim_status, get_plan_details) and the same LLM. The multi-agent version does not improve answer *correctness* here, since Day 21's single agent already had access to all three tools and chose correctly every time.

## When Multi-Agent Is Worth It

**Genuinely different domains -> multi-agent helps.** If Coverage and Claims specialists needed very different tool sets, different compliance rules, or different system prompts/personas (e.g. Claims needing stricter audit logging, Coverage needing benefit-plan language), splitting them into separate agents keeps each agent's prompt focused and easier to tune/debug independently, and makes it easy to add a third specialist (e.g. Enrollment) later without bloating one giant prompt.

**Simple / single-domain questions -> one well-tooled agent is often enough.** In this project, our 3 tools are small and closely related, and a single agent (Day 21) already selects the correct tool 5/5 times. Here, multi-agent orchestration adds an extra LLM call (the Router) and more code/infrastructure, without a measurable accuracy or quality improvement over the single agent.

**Conclusion:** For this project's current scope (3 tools, 2 clear domains), a single well-tooled agent is close to sufficient. Multi-agent orchestration would start paying off if the tool count grew significantly, if specialists needed distinct prompts/compliance behavior, or if an Enrollment Specialist (or more) were added, making a single agent's prompt too large/unfocused to manage reliably.