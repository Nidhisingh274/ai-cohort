# AI Governance Checklist — Coverage Chatbot

Owner: Project owner (this exercise)
Last reviewed: August 2026
Scope: The health-coverage chatbot built across this 31-day program (retrieval engine, RAG backend, Streamlit frontend, multi-agent workflow, and MCP server).

## 1. Data Sources and Sensitivity

| Source | Contents | Sensitivity | Notes |
|---|---|---|---|
| data/plans.csv | Plan ID, plan name, monthly premium, annual deductible, copay percentage, coverage type, network tier | Low - product data, not member-specific | Safe to surface directly to members |
| data/claims.csv (claims table in coverage.db) | Claim ID, member ID, plan ID, procedure, claim amount, status, date filed | High - member-linked claim and procedure data | Must be scoped to the requesting member only |
| raw_text/ (benefits.txt, claims_process.txt, enrollment.txt, faq_scraped.txt) | Plan benefit summaries, claim process descriptions, an enrollment form, scraped public FAQ text | Mixed - enrollment.txt contains a synthetic member name, member ID, and date of birth | Treat enrollment-style documents as PHI-bearing. enrollment.txt retains known OCR errors from Day 5 ingestion (a misread signature name and a misread enrolment year), deliberately kept to reflect real OCR quality; redact_pii covers both the correct and misread name variants, and the date pattern catches both the correct and misread dates. |
| knowledge_base.jsonl / chroma_data | Chunked text from the above, plus embeddings | Inherits the sensitivity of its sources | Anything indexed can be retrieved, so PHI-bearing chunks must be redacted before logging |
| conversations table in coverage.db | Full chat transcripts keyed by session_id | High - members may type identifiers, symptoms, or claim details | Retained for conversation memory; must be redacted in logs |

All data used in this project is synthetic. No real member data was used at any point.

## 2. PHI / PII Fields Present

Identified by scanning the SQL tables and knowledge_base.jsonl:

- member_id (e.g. M1001) - direct member identifier, present in claims and in enrollment.txt
- claim_id (e.g. C1001) - links to a specific member's claim
- Member names (e.g. "John Doe" in enrollment.txt)
- Date of birth (e.g. 1990-05-15 in enrollment.txt)
- procedure (e.g. X-ray, Surgery) - a medical procedure tied to a member is health information
- claim_amount and date_filed - not identifiers alone, but identifying in combination with the above
- Free-text member messages in the conversations table, which may contain emails, phone numbers, or symptoms the member volunteers

plan_id, plan_name, premium, deductible, and copay are product attributes and are not PHI on their own.

### Scan Method and Results

These fields were confirmed by running scan_pii_columns.py, which inspects every table in coverage.db for PII-suggestive column names and scans knowledge_base.jsonl for identifier-shaped values. Results:

| Source | Flagged |
|---|---|
| plans table | plan_name (product data, not PHI - see note below) |
| claims table | claim_id, member_id, procedure |
| conversations table | no PII-named columns, but the content column holds free-text member messages and must be treated as PHI-bearing |
| knowledge_base.jsonl | member_id (M1001 in chunk_0006), two dates (1990-05-15 date of birth, 2028-01-15 enrolment date), and two labelled name fields (Member Name, Signature) - all from the enrolment form ingested on Day 5 |

Two deliberate decisions came out of this scan:

plan_name is flagged by the column-name heuristic because it contains "name", but Gold PPO / Silver HMO / Bronze HMO are product identifiers, not personal ones. It is not redacted.

procedure (X-ray, Surgery) is genuine health information when tied to a member, and in a production system it would be redacted from logs. It is deliberately not redacted here, because redacting it would break the assistant's core function - a member asking about their own claim needs to be told it was an X-ray, not "[PROCEDURE]". The mitigation is access control rather than redaction: a member must only ever be able to retrieve their own claims, which the cross-member input guardrail enforces at the request level and which real authentication would enforce properly in production (see section 6).

## 3. Bias Risks

- Plan-tier assumptions. The system holds Gold, Silver, and Bronze plans with different premiums. Answers must not imply that a lower-tier member deserves less thorough help, less detail, or a less warm tone. The same system prompt and the same tools serve every tier.
- Retrieval bias. Vector search returns the nearest chunks, and the corpus is dominated by Gold PPO material. A Silver or Bronze question can surface Gold text as "relevant" (this was observed in Day 19 testing). Answers must be grounded in the member's own plan row, not in whichever chunk ranked highest.
- Coverage-gap bias. When the corpus has no text on a topic (physical therapy, for example), the assistant says it doesn't have that information rather than inferring coverage. Guessing would systematically disadvantage members whose benefits are underdocumented.
- Language and literacy. Answers use plain language and avoid unexplained insurance jargon, so comprehension does not depend on the member's familiarity with insurance terminology.
- Automation bias. Members may over-trust a confident-sounding answer. Every answer that touches clinical matters carries a licensed-provider disclaimer, and coverage answers point to member support for final confirmation.

## 4. Accountability and Review Ownership

| Responsibility | Owner |
|---|---|
| Prompt and system-message changes | Project owner |
| Retrieval corpus and what gets indexed | Project owner |
| Guardrail rules (input and output) | Project owner |
| Reviewing flagged or fallback responses | Project owner, in this exercise; a named compliance reviewer in production |
| Incident response if PHI is surfaced incorrectly | Project owner, in this exercise; a designated privacy officer in production |

Review cadence in this exercise: guardrails re-run whenever prompts, tools, or the retrieval corpus change (see adversarial_tests.md).

## 5. Controls Implemented

- redact_pii() in redact_pii.py masks member IDs, claim IDs, names, emails, phone numbers, dates of birth, and SSN-shaped strings. It is wired into the /chat logging path so transcripts are never written to logs in raw form.
- Input guardrail in guardrails_config.py flags prompt-injection patterns ("ignore previous instructions", system-prompt extraction attempts) and cross-member data requests ("show me another member's claims").
- Output guardrail in guardrails_config.py scans outgoing text for PHI/PII leakage and for medical-advice phrasing ("you should take", "your condition is"), redirecting the latter to a licensed-provider disclaimer.
- Grounding. The system prompt (finalised on Day 12) instructs the model to answer only from retrieved context and to ask which plan the member means rather than guessing.
- Resilience. Tool failures degrade to a canned support message rather than exposing errors (Day 24).

## 6. Production Compliance Note

This checklist and the guardrails in this repository are an engineering exercise built on synthetic data. They are not a substitute for a formal compliance review.

Before any production use with real member data, the following would be required and are explicitly out of scope here: a HIPAA risk assessment and Business Associate Agreements with any model or infrastructure provider, a legal and privacy review of data retention (the conversations table currently retains transcripts indefinitely with no deletion policy), access controls and authentication so a member can only ever retrieve their own claims (the current member_id is hardcoded and unauthenticated), audit logging that is itself access-controlled, encryption in transit and at rest, a documented incident-response process, and sign-off from a qualified compliance or privacy officer. Clinical accuracy would additionally require review by a licensed healthcare professional.