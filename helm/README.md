# Portfolio Tracker Helm Chart

Deploy portfolio-tracker on Kubernetes with Helm.

## Prerequisites

- Kubernetes cluster (k3s, minikube, etc.)
- Helm 3.x
- Traefik ingress controller
- Local Docker images built

## Build Docker Images

```bash
cd ..

# Build backend
docker build -t portfolio-backend:latest -f backend/Dockerfile backend/

# Build frontend
docker build -t portfolio-frontend:latest -f frontend/Dockerfile frontend/
```

## Install

```bash
helm install portfolio-tracker . -n apps --create-namespace
```

## Upgrade

```bash
helm upgrade portfolio-tracker . -n apps
```

## Uninstall

```bash
helm uninstall portfolio-tracker -n apps
```

## Configuration

| Parameter | Description | Default |
|-----------|-------------|---------|
| `ingress.host` | Hostname for ingress | `portfolio.arnabsaha.com` |
| `persistence.dataPath` | Host path for SQLite DB | `/home/Arnab/clawd/projects/portfolio-tracker/data` |
| `config.allowedOrigins` | CORS origins | `http://localhost,http://portfolio.arnabsaha.com` |

## Architecture

```
                    ┌─────────────────┐
     Traefik ──────▶│    Frontend     │
  (port 80)         │   (nginx:80)    │
                    └────────┬────────┘
                             │ /api/*
                             ▼
                    ┌─────────────────┐
                    │    Backend      │
                    │  (FastAPI:8000) │
                    └────────┬────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │   SQLite DB     │
                    │  (host volume)  │
                    └─────────────────┘
```
