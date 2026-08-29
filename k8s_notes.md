# Kubernetes Notes — Day 29

Deploying the coverage chatbot to a local Minikube cluster: Deployments, Services, Secrets via envFrom, health probes, scaling, and rolling updates.

## Cluster Setup

Minikube v1.38.1 and kubectl v1.34.1 installed on Windows 11. Cluster started with:

minikube start

Confirmed with kubectl get nodes: node "minikube" reached Ready status as control-plane, running Kubernetes v1.35.1 on the Docker driver.

## Images

The Day 28 images (my-first-app-backend:latest and my-first-app-frontend:latest, built by docker compose) are loaded into the cluster with:

minikube image load my-first-app-backend:latest
minikube image load my-first-app-frontend:latest

Both Deployments set imagePullPolicy: IfNotPresent so the cluster uses these locally loaded images rather than trying to pull from a remote registry.

## Manifests (k8s/)

backend-deployment.yaml - 2 replicas, container port 8000, secrets injected via envFrom/secretRef, readinessProbe and livenessProbe both pointing at /health.

backend-service.yaml - ClusterIP service on port 8000, so the frontend can reach the backend by service name (http://backend:8000) inside the cluster, the same pattern used in docker-compose on Day 28.

frontend-deployment.yaml - 1 replica, container port 8501, BACKEND_URL set to http://backend:8000/chat, secrets via envFrom, probes pointing at Streamlit's built-in /_stcore/health.

frontend-service.yaml - NodePort service on 30851, so the UI is reachable from the host via minikube service frontend.

## Secrets

The Groq API key is never written into any YAML in this repo. It is created directly in the cluster:

kubectl create secret generic coverage-secrets --from-literal=GROQ_API_KEY=<key>

Both Deployments consume it with envFrom: secretRef: name: coverage-secrets, so the key is injected as an environment variable at runtime and no secret value ever appears in version control.

## Probes

Both Deployments define a readinessProbe and a livenessProbe against the health endpoint. The readiness probe keeps a pod out of the Service's endpoints until it can actually answer, which matters here because the backend loads the all-MiniLM-L6-v2 embedding model on startup and takes roughly 30-60 seconds before it is genuinely ready. initialDelaySeconds is set to 60 for readiness and 90 for liveness for exactly that reason - a shorter delay would have the liveness probe kill the pod mid-startup, causing a restart loop.

## Apply, Scale, Rolling Update, Teardown

Apply:
kubectl apply -f k8s/

Confirm pods reach Running / Ready:
kubectl get pods
kubectl get deployments

Scale the backend from 2 to 3 replicas:
kubectl scale deployment backend --replicas=3

kubectl get pods then shows a third backend pod being created and joining the Service's endpoints once its readiness probe passes.

Rolling update: change the image tag in backend-deployment.yaml (for example to :v2 after rebuilding and reloading the image) and re-apply:
kubectl apply -f k8s/backend-deployment.yaml
kubectl rollout status deployment/backend

Kubernetes replaces pods one at a time by default (maxUnavailable 25%), bringing up a new pod and waiting for its readiness probe before terminating an old one, which is what makes the rollout zero-downtime: with 2 or 3 replicas, at least one pod is always Ready and serving traffic through the Service.

Teardown:
kubectl delete -f k8s/
kubectl delete secret coverage-secrets
minikube stop

## Notes on This Run

Minikube installed and the cluster started successfully (kubectl get nodes returned Ready). Loading the 3.47GB Day 28 images into the cluster proved slow on this machine - minikube image load repeatedly warned "Executing docker container inspect took an unusually long time", the same Docker Desktop performance issue documented in docker_notes.md on Day 28, where a build step also stalled for hours on this hardware. The manifests, Secret handling, probe configuration, and the scale/rollout/teardown commands above are all in place and correct; completing the live apply and rollout on the cluster is gated on that image load finishing rather than on anything in the configuration.

## Summary

| Piece | Where |
|---|---|
| Backend Deployment, 2 replicas, probes, envFrom | k8s/backend-deployment.yaml |
| Backend Service (ClusterIP :8000) | k8s/backend-service.yaml |
| Frontend Deployment, probes, BACKEND_URL | k8s/frontend-deployment.yaml |
| Frontend Service (NodePort 30851) | k8s/frontend-service.yaml |
| Secret creation (no values in git) | kubectl create secret, documented above |
| Scale / rolling update / teardown commands | documented above |