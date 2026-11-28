# secure-devops-platform

Minimal FastAPI service shipped as a hardened container and deployed to K3s/Kubernetes, with a security-first CI pipeline (lint, test, build, SBOM, signing, scanning, deploy, smoke test).

## Features

- Health & readiness endpoints for orchestrator probes and CI smoke tests
- Stateless, 12-factor-style configuration via environment variables
- Multi-stage Docker image, non-root, minimal runtime
- Hardened Kubernetes manifests (namespace, Deployment, Service, NetworkPolicy, RBAC)
- CI: lint, pytest, container build/push, SBOM, cosign keyless, gitleaks, bandit, pip-audit, trivy, K3s deploy, **port-forward smoke test** (not NodePort-dependent)

## API

| Method | Path       | Response                                                 |
|--------|------------|----------------------------------------------------------|
| GET    | `/`        | `{"service":"secure-devops-platform","version":"0.1.0"}` |
| GET    | `/healthz` | `{"status":"ok"}`                                        |
| GET    | `/readyz`  | `{"status":"ready"}`                                     |

## Tech stack

Python 3.12 · FastAPI · Uvicorn · pytest · httpx · ruff · Docker · Kubernetes/K3s · GitHub Actions · GHCR · cosign · syft · trivy · bandit · pip-audit · gitleaks

## Project layout

```
app/                 FastAPI app (main.py, config.py)
tests/               pytest tests
deploy/k8s/          namespace, deployment, service, networkpolicy, rbac
.github/workflows/   ci.yml
Dockerfile           multi-stage image
docker-compose.yml   local container
Makefile             common tasks
requirements.txt     runtime deps
requirements-dev.txt dev deps (+ runtime)
pytest.ini           pytest config
```

## Prerequisites

- Python 3.12 + pip
- (opsional) Docker + Docker Compose
- (opsional) `kubectl` + kubeconfig K3s/Kubernetes
- (opsional) `k3s`/`kind` lokal

## Run locally

### venv

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
uvicorn app.main:app --host 0.0.0.0 --port 8080
```

Open http://127.0.0.1:8080/healthz · /readyz · /

### Make

```bash
make install
# run app yourself with uvicorn, or:
make run    # docker compose up -d --build
make down   # docker compose down
```

### Docker Compose

Service `api`, container `sdp-api`, port `8080:8080`, healthcheck `/healthz`. `make run` / `make down`.

## Configuration

| Var    | Default | Notes                                                        |
|--------|---------|--------------------------------------------------------------|
| `PORT` | `8080`  | dibaca `app.config`; container memakai uvicorn `--port 8080` |

App version: `0.1.0`.

## Testing & lint

```bash
make test     # pytest
make lint     # ruff check . && ruff format --check .
make format   # ruff format .
pytest
```

`pytest.ini`: `testpaths=tests`, `test_*.py`, `-q`, ignore `DeprecationWarning`. Dev deps: pytest, httpx, ruff `0.8.4`.

## Docker

```bash
make build                                   # docker build -t secure-devops-platform:0.1.0 .
docker run --rm -p 8080:8080 secure-devops-platform:0.1.0
```

- multi-stage `python:3.12-slim`
- non-root `app`, `EXPOSE 8080`, `uvicorn app.main:app --host 0.0.0.0 --port 8080`
- production K8s adds `runAsNonRoot`, `readOnlyRootFilesystem`, `allowPrivilegeEscalation:false`, drop `ALL`, seccomp `RuntimeDefault`, `automountServiceAccountToken:false`, `emptyDir /tmp`

## Kubernetes

Namespace `secure-devops`. Deployment `secure-devops-api` (2 replicas, containerPort 8080, readiness `/readyz`, liveness `/healthz`, resource requests/limits). Service `secure-devops-api` `port 80 -> targetPort http`, **NodePort `30080`** (tersedia, tapi CI smoke test tidak lagi bergantung padanya).

```bash
kubectl apply -f deploy/k8s/namespace.yaml
kubectl apply -f deploy/k8s/rbac.yaml
kubectl apply -f deploy/k8s/networkpolicy.yaml || true
# set image (or use CI sed by digest); deployment.yaml ships image:...:PLACEHOLDER
kubectl apply -f deploy/k8s/deployment.yaml
kubectl apply -f deploy/k8s/service.yaml
kubectl -n secure-devops rollout status deployment/secure-devops-api --timeout=180s
```

Smoke test **without NodePort**:

```bash
kubectl -n secure-devops port-forward svc/secure-devops-api 18080:80 &
PF_PID=$!
sleep 3
curl -fsS http://127.0.0.1:18080/healthz
curl -fsS http://127.0.0.1:18080/readyz
kill $PF_PID
```

Requires image pull access to GHCR for private images.

## CI/CD (GitHub Actions)

`.github/workflows/ci.yml`, runner `[self-hosted, devsecops]`, on push/PR `main`. Image `ghcr.io/<owner>/<repo>`, deploy digest `ghcr.io/...@sha256:...`, build `sha` + `latest`, `id-token: write`, `attestations`, `security-events`, `packages: write`, `contents: read`.

Order: **lint → test → build & push → SBOM → sign**; security: **secret-scan, SAST, dependency-scan, image-scan**; **deploy** (`main`, `environment: production`, needs all) → verify cosign → kubeconfig `KUBECONFIG_B64` → apply → deploy by digest → rollout → **smoke test `port-forward`**.

- **Smoke test** `kubectl -n secure-devops port-forward svc/secure-devops-api 18080:80`, `curl 127.0.0.1:18080/healthz|/readyz`, kill PF; **no NodePort / node IP dependency**.
- cosign keyless OIDC GitHub; `COSIGN_EXPERIMENTAL=1`; verify cert identity regexp + issuer `https://token.actions.githubusercontent.com`; cosign `v2.4.1`.
- SBOM SPDX + CycloneDX artifacts (syft); trivy CRITICAL/HIGH exit-code; SARIF; bandit `-ll`; pip-audit `--strict`; gitleaks full history.

Secrets: `GITHUB_TOKEN`, `KUBECONFIG_B64` (+ runner access). `networkpolicy` applied `|| true`. `deploy/k8s/deployment.yaml` image `...:PLACEHOLDER` replaced by CI `sed` to digest. Build `cache-from/to type=gha`. `docker/login-action@v3`, `docker/build-push-action@v6`, `docker/setup-buildx-action@v3`.

## Makefile

| Target   | Action                                       |
|----------|----------------------------------------------|
| `install`| `pip install -r requirements-dev.txt`        |
| `test`   | `pytest`                                     |
| `lint`   | `ruff check .` + `ruff format --check .`     |
| `format` | `ruff format .`                              |
| `build`  | `docker build -t secure-devops-platform:0.1.0 .` |
| `run`    | `docker compose up -d --build`               |
| `down`   | `docker compose down`                        |

## Security

- Non-root container; K8s `runAsNonRoot`, `readOnlyRootFilesystem`, `allowPrivilegeEscalation:false`, drop `ALL`, seccomp `RuntimeDefault`, no SA token, `NetworkPolicy`, `RBAC`
- No secrets in repo; `.gitignore` `*.pem`, `*.key`, `__pycache__`, `.pytest_cache`, `.ruff_cache`, `.vscode`, `.idea`; `KUBECONFIG_B64` / `GITHUB_TOKEN` via CI secrets
- CI: gitleaks, bandit, pip-audit, trivy, SBOM, cosign keyless + verify, digest deploy
- Note: `.env` exists locally; ensure it is not committed (not currently in `.gitignore`)

## License

No `LICENSE` file in repo yet; choose and add one.
