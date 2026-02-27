# Infrastructure

Local development infrastructure managed via **Docker Compose** and **VS Code Dev Containers**.

## Services

| Service | Image | Port | Purpose |
|---|---|---|---|
| `dev` | `mcr.microsoft.com/devcontainers/base:ubuntu` | — | Dev container (Node + Python) |
| `postgres` | `postgres:16` | `5432` | Primary database |
| `ollama` | `ollama/ollama` | `11434` | Local LLM inference |

## How It Works

The `docker-compose.yml` defines the full local stack. The VS Code Dev Container (`.devcontainer/devcontainer.json`) references this compose file and targets the `dev` service, so opening the project in a Dev Container automatically brings up all dependencies.

```
┌─────────────────────────────────────┐
│  VS Code Dev Container (dev)       │
│  • Python 3 + Node.js             │
│  • Mounts repo to /workspace      │
│  • Forwards ports 3000, 5432,     │
│    11434                           │
├─────────────┬──────────────────────┤
│  PostgreSQL │  Ollama              │
│  :5432      │  :11434              │
└─────────────┴──────────────────────┘
```

## Usage

### Via Dev Container (recommended)

Open the repo in VS Code → **Reopen in Container**. Everything starts automatically.

### Manual Docker Compose

```bash
# Start all services
docker compose -f infra/docker-compose.yml up -d

# View logs
docker compose -f infra/docker-compose.yml logs -f

# Stop all services
docker compose -f infra/docker-compose.yml down

# Stop and remove all data volumes
docker compose -f infra/docker-compose.yml down -v
```

## Persistent Volumes

| Volume | Mounted To | Purpose |
|---|---|---|
| `postgres_data` | `/var/lib/postgresql/data` | Database files (survives restarts) |
| `ollama_data` | `/root/.ollama` | Downloaded LLM models |

## Default Credentials

| Setting | Value |
|---|---|
| Postgres user | `presence` |
| Postgres password | `presence` |
| Postgres database | `presence` |
| Connection string | `postgresql://presence:presence@postgres:5432/presence` |

> [!CAUTION]
> These are development-only defaults. **Never use these in production.**

## Environment Variables

The `dev` service injects these convenience defaults:

| Variable | Value |
|---|---|
| `DATABASE_URL` | `postgresql://presence:presence@postgres:5432/presence` |
| `OLLAMA_URL` | `http://ollama:11434` |
