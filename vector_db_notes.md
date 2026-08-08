# Vector Database Notes — Chroma vs Pinecone

## What is a Vector Database?

A vector database is a specialized database designed to store and search
high-dimensional embedding vectors efficiently. Instead of exact-match
queries (like SQL), it finds the "most similar" vectors using distance/
similarity metrics (e.g. cosine similarity), which powers semantic search
in RAG (Retrieval-Augmented Generation) systems.

## Comparison Table: Chroma vs Pinecone

| Aspect | Chroma | Pinecone |
|---|---|---|
| **Local vs Cloud** | Local — runs entirely on your own machine, data stored on disk | Cloud/managed — hosted on Pinecone's servers, accessed via API |
| **Free-tier limits** | Fully free, no limits (limited only by your own machine's storage/RAM) | Free "Starter" tier available (no credit card), but limited to specific regions (e.g. only us-east-1), storage caps (e.g. 2GB), and read/write unit quotas |
| **Latency** | Very low — no network round-trip since it runs locally | Higher than local, since every query goes over the internet to Pinecone's servers; latency also depends on region proximity to the user |
| **Ease of setup** | Extremely simple — just `pip install chromadb`, no signup, no API key, works offline | Requires account signup, dashboard/API key setup, and index configuration (dimension, metric, cloud region) before use |
| **Access control (per-member / per-plan)** | No built-in enterprise access control — would need to be built manually (e.g. separate collections per plan, or metadata filtering + custom application-level checks) | Offers namespaces to logically separate data (e.g. one namespace per plan or client), and metadata filtering on queries; enterprise/paid plans add more granular access control, audit logs, and role-based access — better suited for regulated, multi-tenant environments like healthcare |

## Enterprise Access Control Considerations

In a real enterprise deployment (e.g. an insurance company chatbot serving
thousands of members), access control is critical: a member must only be
able to retrieve chunks/answers relevant to their own plan and data, never
another member's private information.

- With **Chroma**, this would require building custom logic in the
  application layer — for example, tagging every chunk with a `member_id`
  or `plan_id` in its metadata, and manually filtering every query by the
  logged-in user's ID before it ever reaches Chroma. Chroma itself does not
  enforce this - the responsibility falls entirely on the developer.
- With **Pinecone**, namespaces can isolate data at the database level
  (e.g. one namespace per plan type), and its paid enterprise tiers offer
  more built-in security features (audit logging, RBAC, private
  networking) that reduce the risk of a developer mistake accidentally
  leaking one member's data to another.

For a small, single-tenant learning project like this one, this
distinction doesn't matter much. But it becomes very important at
production scale in a regulated industry like healthcare.

## Decision: Which Vector DB for This Program?

**Chosen: Chroma**

For this 31-day program, I am choosing Chroma going forward. It is
completely free with no signup or API key required, runs entirely on my
local machine so there's no risk of accidentally exposing data or secrets,
and has very low latency since there's no network call involved. Since
this project is a learning exercise with a small synthetic dataset (a
handful of chunks), Chroma's simplicity outweighs Pinecone's
enterprise-grade features like namespaces and managed scaling - those
become valuable at a much larger scale, but they'd add unnecessary setup
overhead here. Pinecone remains a reasonable choice for a future
production deployment, given its access-control options and managed
infrastructure that suit multi-tenant enterprise workloads.