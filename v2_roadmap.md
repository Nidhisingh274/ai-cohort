# v2 Roadmap — Coverage Chatbot

Prioritised next steps, ordered by what has to happen before anything else can safely ship.

## P0 - Blocking. Required before any real member data.

**Formal compliance and legal review.** Everything built so far runs on synthetic data, and that is the only reason it is safe. Before a single real member record touches this system, the following are non-negotiable and none of them are engineering tasks:

- HIPAA risk assessment covering the full data path - retrieval, LLM provider, logs, traces
- Business Associate Agreements with Groq (or whichever model provider is used in production) and with Langfuse, since both receive prompt content that would contain PHI
- Legal review of data retention: the conversations table currently keeps full transcripts indefinitely with no deletion policy or member-initiated erasure path
- Sign-off from a qualified compliance or privacy officer

This is P0 because no amount of feature work below matters if the system cannot legally hold the data it needs. GOVERNANCE.md documents the current controls and their limits in detail.

**Authentication and per-member authorisation.** member_id is currently hardcoded to M1001 and completely unauthenticated - anyone hitting /chat can claim to be any member. The Day 25 cross-member guardrail blocks the obvious phrasing ("show me another member's claims"), but a pattern-matching guardrail is a speed bump, not access control. Real authentication, with every claim and plan query scoped server-side to the authenticated member, is the actual fix. Pairs directly with the compliance review above.

**PHI in traces.** Langfuse currently receives full prompts, which include retrieved context and the member's own words. Day 25 built redact_pii() and wired it into application logging, but the tracing path sends raw content. Either redact before the span is created, or move to self-hosted Langfuse inside the compliance boundary. This one is easy to miss precisely because the observability work looked finished.

## P1 - Fixes for known defects and deployment gaps

**Split the backend image.** The single biggest practical blocker in this project. At 3.47GB - almost entirely torch and transformers for the embedding model - the image would not load into Minikube across five different approaches over two days. Splitting into a lightweight API service (SQL lookups, plans, claims, guardrails, roughly 200MB) and a separate embedding/retrieval service would make the Kubernetes deployment work on modest hardware, and is better architecture regardless: the embedding dependency currently constrains the deployment of code paths that never touch it.

**Fix the coverage card on memory-driven follow-ups.** Found during the Day 31 walkthrough. When a member establishes their plan in one turn and asks a follow-up without naming it, the answer text correctly uses the remembered plan but the rendered card can show a different one - the card heuristic in app.py takes the first SQL row rather than the plan held in conversation memory. The text is right and the card is wrong, which is the worse way round for a member skimming the UI. Fix: pass the detected plan_id into the card builder.

**Expand the corpus.** Three of the eighteen RAGAS eval questions - physical therapy, dental cleanings, vision benefits - score near zero because the answers genuinely are not in the six-chunk knowledge base. The system behaves correctly by declining, but "I don't have that information" for common benefit questions is a poor member experience. This is a content problem, not a retrieval one: it needs real Summary of Benefits documents ingested, not prompt or embedding tuning.

**Run the eval suite in CI.** The RAGAS harness exists and works but runs manually. Wiring it into a pipeline with thresholds - fail if faithfulness drops below the current 0.72 baseline - would catch retrieval regressions automatically. The Day 27 routing bug lived undetected in the code for seventeen days; a gate would have caught it the day it landed. Cost is the constraint: one full run is roughly 50,000 tokens, which is a quarter of the free-tier daily budget, so this likely runs nightly or on retrieval-touching PRs rather than every commit.

## P2 - Capability and reach

**Multi-modal support for scanned documents.** Members photograph their EOBs, enrolment forms and denial letters and want to ask about them. The Day 5 OCR work is a starting point - it already surfaced the difficulty, with the enrolment form misreading "Doe" as "Dos" and "2023" as "2028". Production would need a vision model rather than raw Tesseract, and a confidence threshold below which the system asks the member to confirm rather than acting on a misread figure. A wrong deductible read off a blurry photo is worse than asking again.

**Voice input and output.** Members calling about a denied claim are often stressed and would rather talk than type. Speech-to-text on input and TTS on output. Two things get harder: latency budgets tighten considerably, since the current p95 already runs into double-digit seconds under load, and the streaming architecture from Day 18 would need reworking for audio chunks.

**Additional languages.** Health coverage terminology is unforgiving to translate - "deductible", "copay", "out-of-pocket maximum" and "coinsurance" have specific legal meanings that a general translation will blur. This needs a maintained glossary per language and native-speaker review of the system prompt, not a translation layer bolted on. Spanish first, given US health plan demographics.

**Managed cloud Kubernetes.** Once the image is split (P1), moving from Minikube to EKS, GKE or AKS gives real horizontal scaling, managed TLS, and node capacity that removes the constraint this project kept hitting. The manifests are already written and were verified on Day 29 - scaling, rolling updates and probes all behave correctly - so this is mostly a hosting change rather than a rewrite. Prerequisites: the P0 compliance work, since a cloud provider becomes another party in the data path.

## P3 - Quality and operations

- **Hybrid search.** Pure vector search returned Gold PPO chunks for Silver HMO questions during Day 19 testing. Combining BM25 keyword matching with vector similarity would fix the cases where an exact plan name matters more than semantic closeness.
- **Persistent, shared cache.** The Day 26 cache is an in-process dict - it dies on restart and does not work across replicas. Redis would fix both, and would also let the Day 26 rate limiter work correctly across multiple pods, where the current in-memory counter effectively multiplies the limit by the replica count.
- **Real alerting on the Day 30 thresholds.** The alert sketch exists on paper: 2% error rate, 8s p95 latency, daily cost ceiling at 80%. Wiring those into Langfuse alerts or a monitoring service turns them from a document into something that actually pages someone.
- **Human handoff.** Every declined answer currently ends at "contact member support" with no path. A real escalation - ticket creation, or transfer with the conversation transcript attached - closes the loop for the member.

## Sequencing

P0 gates everything. The compliance review, authentication and PHI-in-traces work must land before real member data, and there is no engineering shortcut around any of it. P1 is what makes the system deployable and fixes what is known broken. P2 and P3 are worth doing only once P0 and P1 are behind them - a multilingual voice assistant that leaks PHI is a worse outcome than a text-only English one that does not.