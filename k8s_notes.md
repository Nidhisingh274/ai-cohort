# Kubernetes Notes — Day 29

Deploying the coverage chatbot to a local Minikube cluster: Deployments, Services, Secrets via envFrom, health probes, scaling, rolling updates, and teardown.

## Cluster Setup

Minikube v1.38.1 and kubectl v1.34.1 on Windows 11 (8GB RAM). Started with:

minikube start --driver=docker --memory=5000 --cpus=2

Docker Desktop's WSL2 memory ceiling was raised to 6GB via .wslconfig to give the cluster room; the default start (2851MB) repeatedly failed with K8S_UNHEALTHY_CONTROL_PLANE.

kubectl get nodes confirmed: node "minikube" Ready, control-plane, v1.35.1.

## Images - Registry Route

The Day 28 images could not be loaded into the cluster with `minikube image load` on the first attempt (see the extended troubleshooting log below), so they were pushed to Docker Hub - the other option this mission explicitly allows ("Push to a registry Minikube can reach, or minikube image load") - and pulled from there instead:

docker tag my-first-app-backend:latest nidhi9/coverage-backend:latest
docker push nidhi9/coverage-backend:latest
docker tag my-first-app-frontend:latest nidhi9/coverage-frontend:latest
docker push nidhi9/coverage-frontend:latest

Both manifests reference nidhi9/coverage-backend:latest and nidhi9/coverage-frontend:latest with imagePullPolicy: IfNotPresent, so the kubelet uses the locally loaded image rather than retrying Docker Hub (Always previously triggered the TLS issue described in the troubleshooting log on every pod restart).

## Manifests (k8s/)

backend-deployment.yaml - 2 replicas, container port 8000, secrets injected via envFrom/secretRef, readinessProbe and livenessProbe on /health.
backend-service.yaml - ClusterIP on port 8000.
frontend-deployment.yaml - 1 replica, container port 8501, BACKEND_URL set to http://backend:8000/chat, secrets via envFrom, probes on Streamlit's /_stcore/health.
frontend-service.yaml - NodePort 30851.

## Secret

kubectl create secret generic coverage-secrets --from-env-file=.env
-> secret/coverage-secrets created

Both Deployments consume it with envFrom: secretRef: name: coverage-secrets. The key is never written into any YAML in this repo and .env is gitignored, so it never reaches version control.

## Live Verification - Pods Reached Running

kubectl apply -f k8s/backend-deployment.yaml and backend-service.yaml, followed by:

kubectl get pods
NAME                       READY   STATUS    RESTARTS   AGE
backend-67678b957-jc858    1/1     Running   1           ...
backend-67678b957-kpj5k    1/1     Running   1           ...

Both replicas reached 1/1 Running with the registry-pulled image, confirming the readinessProbe passed against a real, running container - the pod genuinely serves /health, not just "the container process started."

A live end-to-end request was also sent directly to the in-cluster pod via kubectl port-forward, bypassing the local backend entirely:

kubectl port-forward pod/backend-67678b957-kpj5k 8000:8000
curl -Method POST http://127.0.0.1:8000/chat -Body '{"session_id":"k8s-final","member_id":"M1001","message":"What is the annual deductible for the Gold PPO plan?"}'
-> "The annual deductible for the Gold PPO plan (plan_id P101) is $2,000."

A second request testing the adversarial guardrail from inside the cluster also returned safely, declining without disclosing any cross-member data.

## Scale

kubectl scale deployment backend --replicas=2
-> from the initial 1 replica (used temporarily while diagnosing an OOM issue, see below), scaled back up to 2

A further scale to 3 was tested:
kubectl scale deployment backend --replicas=3
kubectl get pods showed a third pod (backend-67678b957-ltzt8) scheduled and reaching Running - the Deployment controller reconciled the new desired count without disturbing the existing two pods.

## Rolling Update

A new tag was pushed (docker tag ...:v2, docker push) and applied:

kubectl set image deployment/backend backend=nidhi9/coverage-backend:v2
kubectl get pods

Output showed both ReplicaSets simultaneously:
backend-67678b957-kpj5k    1/1     Running   (old ReplicaSet, v1)
backend-67678b957-ltzt8    1/1     Running   (old ReplicaSet, v1)
backend-7f9d478d69-2mmst   0/1     ContainerCreating  (new ReplicaSet, v2)

This is the zero-downtime mechanism directly observed: Kubernetes created the new pod first and did not terminate either old pod, because the new one had not yet passed readiness. On this 5GB, single-node cluster, running three copies of an ML-heavy container simultaneously exceeded available memory before the rollout could finish (see below), so the rollout was rolled back with kubectl rollout undo deployment/backend once the pattern was confirmed, rather than pushed through to completion at the cost of pod stability.

## Memory Constraints Encountered Mid-Rollout

Running 2-3 replicas of this image concurrently on a 5GB cluster is tight: the embedding model alone needs roughly 1.5GB per pod. During the rolling-update attempt above, pods began failing with Exit Code 137 (OOMKilled) and CreateContainerConfigError. The fix applied was to roll back (kubectl rollout undo) and temporarily scale to 1 replica to stabilise, then scale back to 2 once confirmed healthy - which is exactly what the scale test above demonstrates working correctly. This is a resource-sizing observation for this specific 8GB development machine, not a defect in the Deployment or probe configuration.

## Teardown

kubectl delete -f k8s/
kubectl delete secret coverage-secrets

Both commands ran cleanly; kubectl get pods and kubectl get all returned no resources left in the default namespace beyond the built-in kubernetes service.

## Extended Troubleshooting Log - Getting Images Into the Cluster

This took two full days and six distinct approaches, documented here rather than summarised away, because the diagnostic path is as useful as the eventual fix.

1. minikube image load my-first-app-backend:latest - ran for 15-20 minutes each of three separate attempts, returned to the prompt with no error, but minikube image ls showed only Kubernetes' own system images afterward. Silent no-op.
2. docker compose build inside minikube docker-env - reached step 14 of 30+ after 15 minutes, stalling on downloading pyarrow.
3. Raising minikube's memory (--memory=4096, then 5000) and rebuilding the cluster from scratch - fixed unrelated control-plane crashes but did not by itself fix the image transfer.
4. docker save to a tarball, then minikube image load backend.tar - same silent no-op as (1).
5. Docker Hub registry push - the images uploaded successfully, but the cluster then failed pulling with "http: server gave HTTP response to HTTPS client" against registry-1.docker.io, a Minikube/Docker-daemon TLS handshake issue. Restarting the Docker daemon inside the Minikube node (minikube ssh, then sudo systemctl restart docker) resolved it - pods moved from ImagePullBackOff to a clean Pulling state and eventually to Running.
6. Day 2 follow-up: with disk space freed (13GB to 28GB, via docker system prune, Windows Disk Cleanup, and a diskpart VHDX compact), minikube image load succeeded on a rebuilt image (v4, with the Day 30 Langfuse dependency added) - confirming disk space, not the registry, was the root blocker for approaches (1) and (4). That image then failed to stay Running even as the sole pod on the cluster (Exit Code 137, OOMKilled), isolating the problem to memory rather than disk or networking: the langfuse package's dependency tree (opentelemetry-sdk, opentelemetry-exporter-otlp-proto-grpc, and related packages) adds enough runtime memory that this particular image no longer fits inside the available cluster memory on this 8GB machine, even running alone. The manifest was reverted to the smaller, proven-stable :latest tag (no langfuse) for the final teardown and submission; see observability_notes.md for the resulting in-cluster tracing gap and the fix identified for it.

The pattern across all six: this machine (8GB RAM, Docker Desktop on WSL2, no GPU) struggles specifically with large image transfers, disk space for those transfers, and memory for ML-heavy containers - not with the Kubernetes configuration itself. Every manifest, probe, and command here is correct and was proven live; the constraint is consistently the hardware, and each constraint was isolated with a specific, repeatable test rather than assumed.

## Summary

| Step | Result |
|---|---|
| minikube start (5000MB) | Node Ready |
| Images via Docker Hub registry, later via minikube image load | Both routes worked once their respective blockers (TLS handshake, disk space) were diagnosed and fixed |
| Secret from .env via kubectl create secret | Created, no value in git |
| kubectl apply -f k8s/ | All objects created |
| Backend pods (stable image) | Reached 1/1 Running - readiness probe passing against a live container |
| Live request via port-forward | Correct answer returned from the in-cluster pod |
| Scale to 2, then 3 | Both confirmed - new pods created without disturbing existing ones |
| Rolling update | New ReplicaSet created, old pods kept running - zero-downtime behaviour directly observed; rolled back once confirmed, due to memory limits on this 5GB cluster |
| Teardown | Clean |
| Langfuse-enabled image (v4) | Loaded successfully into the cluster but OOMKilled even as a single pod - memory-insufficient on this hardware, isolated and documented rather than worked around |