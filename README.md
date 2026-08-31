# Coverage Chatbot

A production-shaped RAG assistant for health insurance members - answers questions about plan coverage, deductibles, copays and claim status, grounded in structured plan data and policy documents.

Built over 31 days as an AI engineering capstone. All data is synthetic; no real member data is used anywhere in this project.

## What It Does

A member can ask things like:

- "What is the annual deductible for the Gold PPO plan?" - answered from the plans table
- "Is physical therapy covered under the Silver HMO plan?" - answered from policy documents, or honestly declined when the documents do not say
- "What is the status of claim C1001?" - answered from the claims table
- "I'm on the Bronze HMO plan." then "What is my copay?" - the plan is remembered across turns

Prompt-injection attempts and requests for another member's data are blocked before they reach the model.

## Architecture

Streamlit UI sends requests to a FastAPI backend. A query classifier routes each question to SQLite (plans and claims), ChromaDB (policy chunks), or both. Retrieved context goes to Groq's openai/gpt-oss-20b with a grounding prompt that forbids answering beyond what was retrieved. Responses stream token-by-token over SSE. Guardrails screen input and output, conversation memory persists to SQLite, and every LLM call is traced to Langfuse.

## Key Features

Retrieval - hybrid routing between structured SQL and semantic vector search over a chunked policy corpus, using all-MiniLM-L6-v2 embeddings in ChromaDB.

Grounded generation - the system prompt (chosen by A/B test) answers only from retrieved context, asks which plan the member means rather than guessing, and declines when the corpus does not cover the question.

Conversation memory - turns persist to SQLite; the plan a member mentions is remembered across the session; history older than roughly 2000 tokens is summarised rather than dropped.

Safety - PII redaction on all logs (member IDs, claim IDs, names, dates, emails, phones). Input guardrails block prompt injection, cross-member data requests and off-topic prompts. Output guardrails catch PHI leakage and route any clinical question to a licensed-provider disclaimer. All five adversarial test prompts are blocked.

Rich responses - claim status and coverage summary cards, plus citations showing which policy chunks an answer came from.

Resilience - 10s timeouts, one retry, and a canned support fallback on every tool call. Verified with a chaos test that deliberately breaks a tool: the member gets a polite hand-off, not a stack trace.

Cost controls - per-request token counting and cost logging to CSV, a per-member rate limiter, and an exact-match response cache that never caches member-specific questions.

Observability - every LLM call traced to Langfuse with latency, token usage, full prompt and response, and estimated cost.

Evaluation - an 18-question RAGAS eval set scoring faithfulness, answer relevancy, context precision and context recall. Used to find and fix a real retrieval bug (see below).

Deployment - multi-stage Dockerfiles for backend and frontend, docker-compose with health checks and secrets via env_file, and Kubernetes manifests with 2 replicas, readiness and liveness probes, and secrets via envFrom - live-verified on a local Minikube cluster.

## Results

The RAGAS evaluation found that claim-detail questions ("What procedure was claim C1001 filed for?") returned nothing, while claim-status questions worked - the Day 10 query classifier had keywords for one phrasing but not the other. Fixing that one keyword list:

| Metric | Before | After |
|---|---|---|
| Faithfulness | 0.609 | 0.722 |
| Answer relevancy | not scored | 0.735 |
| Context precision | 0.676 | 0.752 |
| Context recall | 0.778 | 0.889 |

Full detail in ragas_scorecard.md.

## Tech Stack

Python, FastAPI, Streamlit, ChromaDB, SQLite, sentence-transformers, Groq (OpenAI-compatible), LangChain, LangGraph, MCP, RAGAS, Langfuse, Docker, Kubernetes, GitHub Actions.

## Running It

Install dependencies with pip install -r requirements.txt, then copy .env.example to .env and add your GROQ_API_KEY and Langfuse keys.

Start the backend: cd coverage-chatbot-api and run uvicorn main:app --reload

Start the frontend in a separate terminal: streamlit run app.py

Or run both with Docker: docker compose up --build

UI at http://localhost:8501, API at http://localhost:8000.

## Known Limitations

Kubernetes deployment. The backend pod reached 1/1 Running in the cluster after pushing images to Docker Hub (five approaches tried before this one worked - see k8s_notes.md). Scaling to 3 replicas, a rolling update showing the zero-downtime pattern, and two live scenario requests sent directly to the in-cluster pod via kubectl port-forward were all confirmed working. One item remains open: traces from the in-cluster pod did not reach the Langfuse dashboard, because a dependency (langfuse) was missing from the Docker requirements file used to build the deployed image - diagnosed, understood, and fixed in the source, pending one more image rebuild that did not complete within this submission's time window on this 8GB machine. See k8s_notes.md and observability_notes.md.

Corpus coverage. The knowledge base is six chunks. Questions about physical therapy, dental and vision are declined because the documents genuinely do not cover them - correct behaviour, but a thin corpus.

No authentication. member_id is hardcoded. Real per-member authorisation is P0 in the roadmap and must land before any real data.

Synthetic data only. Formal compliance review is required before this touches real member records. See GOVERNANCE.md.

## Documentation

| Document | Contents |
|---|---|
| GOVERNANCE.md | Data sources, PHI/PII inventory, bias risks, accountability |
| capstone_walkthrough.md | Five live scenarios with results and Langfuse evidence |
| retrospective.md | What worked, what was hard, what I'd do differently |
| v2_roadmap.md | Prioritised next steps, compliance-gated |
| ragas_scorecard.md | Evaluation scores, weakest metric, before/after fix |
| adversarial_tests.md | Five attack prompts and guardrail results |
| docker_notes.md | Containerisation, health checks, issues hit |
| k8s_notes.md | Kubernetes deployment, scaling, rolling update, troubleshooting log |
| observability_notes.md | Langfuse tracing, kubectl debugging, alert thresholds |
| ab_test_results.md | Prompt A/B test and decision |
| chaos_test.md | Resilience testing with a deliberately broken tool |

## Demo

[Watch the demo video](https://drive.google.com/file/d/1-Yz0gqU3Sl2H4Qjf0q2gD2M5xMhf5A_b/view?usp=drive_link)