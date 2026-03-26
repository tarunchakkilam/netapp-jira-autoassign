# Kubernetes Deployment (k3s, Multi-User)

This folder provides a namespace-scoped deployment model so each user/team can run the scheduler with their own Jira/LLM/SMTP secrets.

## Architecture

- Shared ChromaDB in `platform` namespace: `k8s/chromadb-shared.yaml`
- One scheduler deployment per user namespace
- Non-sensitive config in `ConfigMap`
- Sensitive values in namespace `Secret`

## Prerequisites

- Local k3s cluster (`kubectl` connected)
- Built scheduler image available to cluster nodes:
  - `jira-autoassign-scheduler:latest`

## 1) Deploy shared ChromaDB (once)

```bash
kubectl apply -f k8s/chromadb-shared.yaml
kubectl -n platform rollout status deploy/chromadb
kubectl -n platform get svc chromadb
```

## 2) Create user namespace

Replace `jira-autoassign-user` with your namespace if needed.

```bash
kubectl apply -f k8s/namespace.yaml
```

## 3) Apply config and user secrets

Create user secret file from template:

```bash
cp k8s/secret.example.yaml /tmp/jira-autoassign-secret.yaml
# Edit /tmp/jira-autoassign-secret.yaml values
```

If you changed namespace name, update namespace in all files before applying.

```bash
kubectl apply -f k8s/configmap.yaml
kubectl apply -f /tmp/jira-autoassign-secret.yaml
```

## 4) Deploy scheduler

```bash
kubectl apply -f k8s/deployment.yaml
kubectl -n jira-autoassign-user rollout status deploy/jira-autoassign-scheduler
kubectl -n jira-autoassign-user get pods
```

## 5) Verify runtime

```bash
kubectl -n jira-autoassign-user logs -f deploy/jira-autoassign-scheduler
kubectl -n jira-autoassign-user describe pod -l app=jira-autoassign-scheduler
```

## Multi-user pattern

For each additional user/team:

1. Create another namespace (for example `jira-autoassign-alice`).
2. Copy and apply `configmap.yaml` and a **different** secret file in that namespace.
3. Deploy scheduler in that namespace.

The same scheduler image can be reused across all namespaces.

## Secret rotation

Update only the secret in the user namespace, then restart deployment:

```bash
kubectl -n jira-autoassign-user apply -f /tmp/jira-autoassign-secret.yaml
kubectl -n jira-autoassign-user rollout restart deploy/jira-autoassign-scheduler
kubectl -n jira-autoassign-user rollout status deploy/jira-autoassign-scheduler
```

## Smoke tests

- Scheduler pod is `Running` and `Ready`
- Logs show periodic scheduler loop
- No auth errors for Jira/LLM
- Chroma heartbeat is healthy:

```bash
kubectl -n platform get pods -l app=chromadb
kubectl -n platform port-forward svc/chromadb 8000:8000
curl http://localhost:8000/api/v1/heartbeat
```

## Troubleshooting

- `ImagePullBackOff`
  - Build/tag image on node or configure image registry + imagePullSecrets.
- `CrashLoopBackOff` on scheduler
  - Check missing env vars in secret and configmap.
  - `kubectl -n <ns> logs deploy/jira-autoassign-scheduler --previous`
- Jira auth failures
  - Verify `JIRA_BASE_URL`, `JIRA_EMAIL`, `JIRA_API_TOKEN`, `JIRA_USE_BEARER_AUTH`.
- LLM errors
  - Verify `NETAPP_LLM_API_KEY`, `NETAPP_LLM_BASE_URL`, and network egress.
- Chroma connection errors
  - Ensure `CHROMA_HOST=chromadb.platform.svc.cluster.local`.
