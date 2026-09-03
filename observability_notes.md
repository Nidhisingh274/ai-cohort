# Observability Notes — Day 30

Langfuse tracing wired into the coverage chatbot backend, kubectl debugging practice, and a production alert sketch.

## Langfuse Setup

Package: pip install langfuse (installed 4.15.1).

Keys live in .env as LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY and LANGFUSE_HOST. .env is gitignored and .dockerignored, so no key ever reaches version control or an image. The client is constructed with a bare Langfuse(), which reads those variables from the environment - nothing is hardcoded.

## What Is Traced

Tracing is wrapped around the LLM call inside /chat in coverage-chatbot-api/main.py. Each request opens a generation observation before the Groq call and closes it after the stream finishes, capturing:

Latency - measured automatically between the span opening and end().
Token usage - input, output and total, from the Day 26 count_tokens helpers.
Full prompt - the complete messages array, including the system prompt, prior conversation turns and the retrieved context.
Full response - the assembled streamed answer.
Metadata - estimated cost in USD, retrieval classification, remembered plan_id, memory token counts, whether summarisation fired, session_id and member_id.

Every Langfuse call is wrapped in try/except and the span object is initialised to None. If tracing fails for any reason the chat still answers normally - observability must never be able to break the product it is observing. This was not theoretical: three separate SDK-API mismatches were hit while wiring this up (see below) and the chatbot kept serving correct answers through all of them.

## SDK Version Note

Langfuse v4 is a rewrite on top of OpenTelemetry and the v2-era API no longer exists. Three attempts failed in sequence before landing on the right calls, each surfacing as a clean [LANGFUSE] log line rather than a crash:

langfuse.trace() -> 'Langfuse' object has no attribute 'trace'
langfuse.start_generation() -> 'Langfuse' object has no attribute 'start_generation'
generation.update_trace() -> 'LangfuseGeneration' object has no attribute 'update_trace'

The working API was found by introspecting the objects directly rather than guessing further:

python -c "from langfuse import Langfuse; lf=Langfuse(); print([m for m in dir(lf) if not m.startswith('_')])"

Which gave the correct call: langfuse.start_observation(name=..., as_type="generation", ...), then generation.update(...), generation.end(), langfuse.flush(). Trace-level helpers like update_current_trace are not present on this client build, so session_id and member_id are carried in the span metadata instead - they are still filterable in the dashboard, just not as first-class trace fields.

flush() is called explicitly after each request because this is a short-lived HTTP path; without it the span can be lost before the background exporter ships it.

## Traces Confirmed in the Dashboard

Test conversations were sent to the local backend and traces appeared in the Langfuse dashboard within seconds. Example entries:

Trace at 2026-08-30 15:53:34 - name groq-completion, model openai/gpt-oss-20b, latency 50.80s. Input shows the full system prompt and messages array; output shows the complete Gold PPO coverage answer. Metadata: estimated_cost_usd 0.0001084, tokens_before 9, tokens_after 9, plan_id P101, classification unstructured, session_id day30-v4, member_id M1001, cached false.

Trace at 2026-08-30 15:39:43 - name groq-completion, latency 7.57s, output "The out-of-pocket maximum for the Gold PPO plan is $5,000 per year.", metadata estimated_cost_usd 0.0000613, classification unstructured, plan_id P101.

Latency varied widely across runs - 3.9s, 7.6s, 12.3s, 50.8s and once 84.3s for the same class of question. That spread is a local artefact rather than a Groq characteristic: Docker Desktop and a Minikube cluster were running alongside the backend on an 8GB machine. It is a useful illustration of why p95 latency, not average, is the metric worth alerting on.

## In-Cluster Trace Attempt

The Day 29 backend pod was live-verified end-to-end via kubectl port-forward - a request sent directly to the in-cluster container returned the correct answer ("The annual deductible for the Gold PPO plan is $2,000"), confirming the deployed application logic works identically inside the cluster.

The trace for that request did not appear in the Langfuse dashboard. Diagnosing this with kubectl exec found the first root cause: the langfuse package was missing from requirements-docker.txt, so the image running in the cluster did not have it installed. The application's try/except around all Langfuse calls worked exactly as designed - the missing dependency failed silently, the chat still answered correctly, and no error reached the member.

That dependency was added and the image was rebuilt (tag v4) and pushed to Docker Hub - confirmed with pip show langfuse inside the built image before deploying. Loading it into the Minikube cluster required freeing disk space first (13GB to 28GB, via docker system prune, Windows Disk Cleanup, and a diskpart VHDX compact - see k8s_notes.md), after which minikube image load succeeded.

Once running, though, the v4 pod was OOMKilled (Exit Code 137) - and this held even when it was the only pod on the cluster, isolating the cause to memory rather than to co-scheduled pods or disk. The langfuse package's dependency tree (opentelemetry-sdk, opentelemetry-exporter-otlp-proto-grpc, and related instrumentation packages) adds enough runtime memory overhead that this image no longer fits inside the available cluster memory on this 8GB development machine, even running alone. The plain application image (without langfuse) has run stably at 1-2 replicas on the same cluster throughout this project, so the constraint is specifically the added observability dependency, not the application itself.

For the final submission, the deployment was reverted to the smaller, proven-stable image so the cluster is left in a working, teardown-ready state rather than crash-looping. The path to a working fix is the one already scoped in v2_roadmap.md: split the backend into a lightweight API service and a separate embedding/retrieval service, which would also bring the image small enough for langfuse's dependencies to fit comfortably.

## kubectl Debugging

The Day 29 manifests were re-applied to the Minikube cluster to practise debugging a pod that cannot start.

kubectl apply -f k8s/ created both Deployments and both Services. kubectl get pods showed:

backend-67678b957-fdztj   0/1   ImagePullBackOff
backend-67678b957-sw64z   0/1   ImagePullBackOff
frontend-79cd68bf8d-x9rmd  0/1   ImagePullBackOff

kubectl describe pod -l app=backend gave the diagnosis. The useful parts:

Status: Pending, State: Waiting, Reason: ContainerCreating
Events: Scheduled -> "Successfully assigned default/backend-... to minikube", then Pulling -> "Pulling image my-first-app-backend:latest"

The Events block is the payload here - it shows scheduling succeeded (so this is not a resource or node problem) and the failure is specifically at the image-pull stage. The describe output also confirmed two things worth verifying independently of the failure: the probes are registered correctly (Liveness http-get http://:8000/health delay=90s period=20s, Readiness delay=60s period=10s) and the Secret is wired (Environment Variables from: coverage-secrets Secret Optional: false).

kubectl logs -l app=backend --tail=20 returned:

Error from server (BadRequest): container "backend" in pod "backend-...-sw64z" is waiting to start: image can't be pulled

This is the key lesson from the exercise: logs are only available once a container has started. For a pod stuck before that point, describe is the tool - logs will just tell you why it has nothing to show you. The practical loop is describe first to find out where in the lifecycle it stalled, then logs once the container is actually running. This same loop was used again on two further real failures during this project (a CreateContainerConfigError and repeated OOMKilled restarts) and found genuine root causes each time - a missing dependency, then a memory ceiling - rather than transient issues. See k8s_notes.md for the full sequence.

## Production Alert Sketch

These are the three alerts worth having before this service takes real traffic. Thresholds are starting points to be tuned against a week of real baseline data, not fixed truths.

Error rate. Alert when the share of /chat requests returning an error or hitting the canned fallback exceeds 2% over a rolling 5-minute window, with a minimum of 20 requests in the window so a single failure at 3am does not page anyone. Page on 5%. In this system the signal already exists in two places: the [ERROR] branch in the streaming generator, and spans marked level=ERROR in Langfuse. Worth splitting by cause - an upstream Groq 429 is a capacity problem, a retrieval exception is a code problem, and they need different responses.

p95 latency. Alert when p95 end-to-end /chat latency exceeds 8 seconds over 10 minutes, page at 15 seconds. p95 rather than average, because the observed spread on this project (3.9s to 84.3s for comparable questions) is exactly the pattern an average hides - a mean of 6s can sit on top of a tail where one member in twenty waits over a minute. Two sub-alerts are worth separating: time-to-first-token, which is what the member actually perceives on a streaming UI, and total generation time.

Daily cost ceiling. Alert at 80% of the daily budget and hard-stop new requests at 100%. The data is already being collected in token_usage.csv and in the estimated_cost_usd metadata on every Langfuse span. At the current measured rate - roughly $0.00006 per request - a $5/day ceiling allows about 80,000 requests, so a spike toward that number means either a traffic anomaly or a runaway loop, and both are worth catching. This alert pairs with the Day 26 rate limiter: the limiter caps a single member, the cost ceiling caps the whole service.

Two more worth adding once there is baseline data: cache hit rate dropping sharply (suggests the cache key or the question mix has changed) and guardrail block rate spiking (suggests either an attack or a false-positive regression in the Day 25 patterns).

## What This Confirms and What Remains

Confirmed: Langfuse tracing works correctly against this application (8 local traces with full latency/token/prompt/response data), the deployed Kubernetes cluster runs the identical application logic and answers correctly when hit directly, the missing-dependency gap was found, fixed, and rebuilt into a working image (verified with pip show langfuse inside it, and confirmed loadable into the cluster), and the resilience design (try/except around every observability call) meant every failure mode encountered - missing dependency, then memory ceiling - degraded gracefully rather than breaking the product.

Remaining: the langfuse-enabled image needs more memory than this 8GB development machine's cluster can currently give it, even running alone. This is a hardware/architecture constraint, not an unfixed code or configuration issue - the fix (splitting the backend so the traced API service is lightweight) is scoped in v2_roadmap.md as a P1 item.

## Summary

| Item | Status |
|---|---|
| langfuse installed and wired into /chat | Done |
| Latency, tokens, full prompt and response traced | Done, confirmed in dashboard |
| Keys in .env only, never committed | Done |
| Traces visible in Langfuse dashboard | Confirmed with timestamps and values above (local) |
| kubectl describe on a failing pod | Done - events, probes and Secret wiring all inspected |
| kubectl logs on a pod that never started | Done - returned the "image can't be pulled" BadRequest |
| Production alert sketch | Done - error rate, p95 latency, daily cost ceiling |
| Traces from a pod running inside the cluster | Dependency gap found and fixed; image built and loadable; blocked by memory ceiling on this hardware, isolated via a single-pod test - architectural fix scoped in v2_roadmap.md |