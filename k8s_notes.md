# Kubernetes Notes — Day 29

Deploying the coverage chatbot to a local Minikube cluster: Deployments, Services, Secrets via envFrom, health probes, scaling, rolling updates, and teardown.

## Cluster Setup

Minikube v1.38.1 and kubectl v1.34.1 on Windows 11. Started with:

minikube start --driver=docker --memory=4096 --cpus=2

The default start allocated only 2851MB, which was not enough - the control plane repeatedly failed with K8S_UNHEALTHY_CONTROL_PLANE. Raising Docker Desktop's WSL2 memory ceiling to 5GB via a .wslconfig file and starting minikube with --memory=4096 gave a clean start.

kubectl get nodes confirmed: node "minikube" Ready, control-plane, v1.35.1.

## Manifests (k8s/)

backend-deployment.yaml - 2 replicas, container port 8000, secrets injected via envFrom/secretRef, readinessProbe and livenessProbe on /health.

backend-service.yaml - ClusterIP on port 8000, so the frontend reaches the backend by service name (http://backend:8000) inside the cluster, the same pattern used in docker-compose on Day 28.

frontend-deployment.yaml - 1 replica, container port 8501, BACKEND_URL set to http://backend:8000/chat, secrets via envFrom, probes on Streamlit's /_stcore/health.

frontend-service.yaml - NodePort 30851.

## Secret

The Groq API key is never written into any YAML in this repo. Created directly in the cluster from the gitignored .env file:

kubectl create secret generic coverage-secrets --from-env-file=.env
-> secret/coverage-secrets created

Both Deployments consume it with envFrom: secretRef: name: coverage-secrets, so the key is injected as an environment variable at runtime and no secret value ever reaches version control. Using --from-env-file also means the key never appears in shell history.

## Probes

Both Deployments define readinessProbe and livenessProbe against their health endpoints. The readiness probe keeps a pod out of the Service's endpoints until it can actually answer, which matters here because the backend loads the all-MiniLM-L6-v2 embedding model on startup and takes 30-60 seconds to become genuinely ready. initialDelaySeconds is 60 for readiness and 90 for liveness - a shorter liveness delay would kill the pod mid-startup and cause a restart loop.

## Apply

kubectl apply -f k8s/

-> deployment.apps/backend created
-> service/backend created
-> deployment.apps/frontend created
-> service/frontend created

kubectl get deployments confirmed backend with 2 desired replicas and frontend with 1:

NAME       READY   UP-TO-DATE   AVAILABLE
backend    0/2     2            0
frontend   0/1     1            0

kubectl get pods showed 2 backend pods and 1 frontend pod scheduled, all in ErrImagePull:

backend-6b759f6996-rf7pc   0/1   ErrImagePull
backend-6b759f6996-zbdrh   0/1   ErrImagePull
frontend-ff88fb4c5-vtgc6   0/1   ContainerCreating

## Scale

kubectl scale deployment backend --replicas=3
-> deployment.apps/backend scaled

kubectl get pods then showed a third backend pod created immediately:

backend-6b759f6996-hcbbh   ← new
backend-6b759f6996-rf7pc
backend-6b759f6996-zbdrh

The Deployment controller reconciled the new desired count straight away, without touching the existing pods.

## Rolling Update

kubectl set image deployment/backend backend=my-first-app-backend:v2
-> deployment.apps/backend image updated

kubectl get pods showed both ReplicaSets side by side:

backend-6b759f6996-rf7pc   ← old ReplicaSet (v1)
backend-6b759f6996-zbdrh   ← old
backend-6b759f6996-zwxdh   ← old
backend-7546f64c6c-krmbb   ← new ReplicaSet (v2), only one pod

This is the zero-downtime mechanism in action: Kubernetes brought up one new pod first and did not terminate any old pod, because the new one never became Ready. With a working image, the old pods would keep serving traffic through the Service until each replacement passed its readiness probe, which is exactly why the rollout is zero-downtime.

kubectl rollout status deployment/backend timed out after 30s with "1 out of 3 new replicas have been updated" - the correct behaviour, since the new pod could not become Ready.

kubectl rollout history deployment/backend showed two revisions, so a rollback target existed:

REVISION  CHANGE-CAUSE
1         <none>
2         <none>

kubectl rollout undo deployment/backend
-> deployment.apps/backend rolled back

## Teardown

kubectl delete -f k8s/
-> deployment.apps "backend" deleted
-> service "backend" deleted
-> deployment.apps "frontend" deleted
-> service "frontend" deleted

kubectl delete secret coverage-secrets
-> secret "coverage-secrets" deleted

kubectl get all then showed all pods Terminating and only the default kubernetes ClusterIP service remaining - a clean teardown.

## What Did Not Work: Loading the Images

The pods never reached Running because the Day 28 images could not be loaded into the cluster. This is documented honestly rather than glossed over, because it shaped everything above.

Four approaches were tried:

1. minikube image load my-first-app-backend:latest - ran for 15-20 minutes, returned to the prompt with no error, but minikube image ls showed only the Kubernetes system images. Tried three separate times, including once on a freshly rebooted machine.
2. docker compose build inside minikube docker-env - reached step 14 of 30+ after 15 minutes, stalling on downloading pyarrow.
3. Raising memory to 4096MB and rebuilding the cluster from scratch - fixed the control-plane crashes but did not help the image load.
4. docker save to a tar file, then minikube image load backend.tar - same result, silently no-op.

The root cause is size. Each image is 3.47GB, because the backend carries the full ML stack (torch, transformers, chromadb, sentence-transformers). On this machine (8GB RAM, Docker Desktop on WSL2, no GPU), transferring that into the Minikube container repeatedly exhausted resources. The same environment produced a five-hour stalled Docker build on Day 28, documented in docker_notes.md, so this is a consistent hardware constraint rather than a one-off.

Notably, the image loads did not error - they returned cleanly and did nothing, which is why it took several attempts to identify. kubectl describe pod gave the confirmation:

Failed to pull image "my-first-app-backend:latest": Error response from daemon: pull access denied ... repository does not exist

That is exactly what you would expect when imagePullPolicy: IfNotPresent finds nothing locally and falls back to a registry that has no such image.

## What This Run Did and Did Not Prove

Verified end to end on the live cluster: cluster startup, Secret creation from a gitignored env file, applying all four manifests, the Deployment controller honouring 2 replicas, scaling to 3, a rolling update creating a second ReplicaSet without terminating the old one, rollout history and rollback, and a clean teardown. Also verified the diagnostic path - reading pod events with kubectl describe to find the actual failure - which is the most common real-world Kubernetes debugging loop.

Not verified, because no container ever started: pods reaching Running/Ready, readiness and liveness probes actually passing against /health, and the Service routing live traffic to healthy pods. Those depend on the image being present, which is the constraint above rather than anything in the manifests.

## Summary

| Step | Result |
|---|---|
| minikube start (4096MB) | Node Ready |
| Secret from .env via kubectl create secret | Created, no value in git |
| kubectl apply -f k8s/ | All 4 objects created |
| Backend replicas | 2 desired, honoured |
| Scale to 3 | Third pod created immediately |
| Rolling update | New ReplicaSet created, old pods kept - zero-downtime behaviour confirmed |
| Rollback | Succeeded |
| Teardown | Clean, only default kubernetes service left |
| Pods Running/Ready | Not reached - 3.47GB images could not be loaded on this hardware |