# Retrospective — 31-Day Build

A one-page look back at building the coverage chatbot, from a CSV of three insurance plans to a containerised, traced, evaluated RAG system.

## What Worked Well

**Building in layers, each one testable on its own.** The order the program imposed - data, then retrieval, then generation, then interface, then agents, then ops - meant that when something broke, the broken thing was almost always the layer just added. By Day 27, when the RAGAS evaluation surfaced a failure, the fix was traceable to one keyword list in one function written on Day 10. That would have been very hard to isolate if everything had been built at once.

**Grounding the model early.** The Day 12 prompt work - answer only from retrieved context, ask which plan rather than guessing, decline when the context does not cover it - paid off for the remaining nineteen days. In the Day 31 walkthrough, the physical therapy question still correctly returned "I don't have that information" rather than inventing a benefit. For a health-coverage assistant, a wrong answer about what is covered is worse than no answer, and that behaviour held from Day 12 through to the capstone without regressing.

**Evaluating instead of guessing.** The Day 26 A/B test and the Day 27 RAGAS run both changed decisions. The A/B test confirmed the hybrid prompt was genuinely better and showed exactly where - all three ambiguity questions, none of the others. RAGAS found a retrieval routing bug that manual testing had missed entirely: "What procedure was claim C1001 filed for?" returned nothing while "What is the status of claim C1001?" worked fine, because the classifier's keyword list had "claim status" but not "procedure". That one-line fix moved faithfulness from 0.61 to 0.72 and context_recall from 0.78 to 0.89. Without a structured eval set, that bug would still be in the code.

**Defensive wrapping around anything optional.** Tool calls, tracing, citation lookups - all wrapped in try/except from the start. This was not theoretical caution. On Day 30, three separate Langfuse SDK API mismatches were hit in a row, and the chatbot kept answering correctly through all of them, logging a clean line each time instead of crashing. On Day 24, a chaos test that deliberately broke a tool produced a polite support hand-off rather than a stack trace.

## What Was Harder Than Expected

**Hardware, not concepts.** The genuinely hard part was not RAG or agents or Kubernetes - it was running any of it on an 8GB Windows laptop. A single Docker build stalled for five hours on Day 28. Minikube's control plane crashed repeatedly until its memory was raised. Image loads into the cluster failed silently five different ways across two days. Time went into `diskpart compact vdisk` and `.wslconfig` memory ceilings rather than into the actual subject matter. Nothing in the curriculum warned that image size would become the binding constraint, and the 3.47GB image is a direct consequence of carrying torch and transformers for the embedding model.

**Library churn.** Three separate days lost significant time to APIs that had moved since the tutorials were written. Groq deprecated llama-3.1-8b-instant mid-project (Day 18). LangChain removed AgentExecutor from its main package, requiring langchain-classic (Day 21). RAGAS 0.4 broke on an import from a sunset langchain-community module, requiring a pin to <0.4 and then a further pin on langchain-community itself (Day 27). Langfuse v4 replaced its entire tracing API (Day 30). The lesson that stuck: when a documented method does not exist, stop guessing at alternatives and introspect the object - `print([m for m in dir(obj) if not m.startswith('_')])` answered in one command what four guesses had not.

**Small models are unpredictable at tool selection.** Day 21 hit "Tool choice is none, but model called a tool" because gpt-oss-20b emits native tool-call output even when tools are not registered that way. Day 23 found that neither Copilot nor Cline reliably chose the registered MCP tool unless it was named explicitly in the prompt. The tool descriptions and schemas were correct; the models simply did not always use them. That is not something the tutorials prepare you for.

## Three Things I'd Do Differently Starting Over

**1. Design for image size from Day 1.** The backend should have been split from the start: a lightweight service handling SQL lookups, plans and claims, and a separate embedding service carrying torch. The lightweight image would be roughly 200MB instead of 3.47GB, and every Kubernetes step from Day 29 onward would have worked on this hardware. This is not just a workaround for a small laptop - it is better architecture. The embedding model is used by one of several code paths, and coupling the entire deployment to its dependency footprint is a design mistake that only became visible under deployment pressure.

**2. Write the eval set before writing the retrieval logic.** The RAGAS eval set arrived on Day 27 and immediately found a bug from Day 10. Had those eighteen question/ground-truth pairs existed on Day 10, the claim-detail routing gap would have been caught the day it was introduced, seventeen days earlier - and the Day 26 A/B test would have had a real regression suite behind it rather than five hand-scored questions.

**3. Pin every dependency version on the day it works.** requirements.txt was frozen but not thought about, which meant Docker builds resolved different versions than the local environment - numpy 2.5.1 needing Python 3.12+ while the Dockerfile said 3.11, and pywin32 breaking a Linux build entirely. Pinning deliberately, and keeping a separate Linux requirements file from the start rather than improvising one mid-build, would have removed a whole category of "works locally, fails in the container" problems.

## One Thing I'd Keep Exactly As It Was

Documenting failures honestly in the notes files as they happened, rather than only recording what worked. docker_notes.md, k8s_notes.md and ragas_scorecard.md each contain a full account of what broke and why. Those sections turned out to be the most useful parts of the repo - when the same Docker slowness reappeared on Day 29, the Day 28 notes had already identified it as a hardware pattern rather than a new bug, which saved diagnosing it twice.