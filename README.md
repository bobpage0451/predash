# Presence Dashboard

An email-intelligence platform that ingests emails via IMAP, processes them with LLMs (Ollama), and surfaces insights through a web dashboard.

## Architecture

```
┌─────────────────────────────────────────────────┐
│                  Dev Container                  │
│  (Ubuntu + Node + Python)                       │
│                                                 │
│   ┌──────────────┐       ┌──────────────────┐   │
│   │  Dashboard    │       │  Worker          │   │
│   │  (Next.js)    │       │  (Python)        │   │
│   │  :3000        │       │                  │   │
│   └──────┬───────┘       └────┬────┬────────┘   │
│          │                    │    │             │
│          ▼                    ▼    ▼             │
│   ┌────────────┐   ┌──────────┐  ┌──────────┐  │
│   │ PostgreSQL │   │ Postgres │  │  Ollama   │  │
│   │   :5432    │   │  :5432   │  │  :11434   │  │
│   └────────────┘   └──────────┘  └──────────┘  │
└─────────────────────────────────────────────────┘
```

| Component | Tech Stack | Purpose |
|---|---|---|
| **Dashboard** | Next.js 16, React 19, TypeScript, Tailwind CSS v4 | Web UI for viewing processed email data |
| **Worker** | Python 3, SQLAlchemy 2, Alembic, IMAPClient | IMAP ingestion & LLM-based email processing |
| **Infra** | Docker Compose, Dev Containers | Local development environment |

## Repo Structure

```
presence_dashboard/
├── apps/
│   └── dashboard/          # Next.js frontend (see apps/dashboard/README.md)
├── services/
│   └── worker/             # Python worker service (see services/worker/README.md)
├── infra/
│   └── docker-compose.yml  # Dev environment (see infra/README.md)
└── .devcontainer/          # VS Code Dev Container config
```

## Quick Start

### Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (or Docker Engine + Compose)
- [VS Code](https://code.visualstudio.com/) with the [Dev Containers](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers) extension (recommended)

### 1. Clone & open in Dev Container

```bash
git clone https://github.com/<you>/presence_dashboard.git
cd presence_dashboard
code .
# VS Code will prompt: "Reopen in Container" → click it
```

This spins up PostgreSQL, Ollama, and a dev container automatically via `infra/docker-compose.yml`.

### 2. Set up the Worker

```bash
cd /workspace/services/worker
cp .env.example .env        # edit with your IMAP credentials
pip install -r requirements.txt
```

### 3. Run the full pipeline (recommended)

```bash
cd /workspace/services/worker
python -m app                         # run all 4 stages end-to-end
python -m app --limit 10              # forward --limit to all stages
python -m app --stop-on-error         # abort on first stage failure
```

Runs **IMAP ingest → pre-LLM filter → story extraction → embedding backfill → topic assignment** sequentially with per-stage logging and a summary at the end. Emails that don't look like newsletters are skipped before the LLM call. By default, a failure in one stage doesn't block the next.

### Run stages individually

You can also run each stage separately:

```bash
# IMAP ingestion
python -m app.imap

# Story extraction
python -m app.llm                        # extract stories (default)
python -m app.llm --stories --limit 10   # cap to 10 emails

# Embedding backfill
python -m app.llm --embeddings                    # embed all stories missing a vector
python -m app.llm --embeddings --limit 100        # cap to 100 stories

# Topic assignment
python -m app.llm --topics               # assign all unassigned stories
python -m app.llm --topics --sim-threshold 0.80  # lower similarity threshold
```

See [Worker README](services/worker/README.md) for full CLI flag documentation per stage.

### 4. Run the Dashboard

```bash
cd /workspace/apps/dashboard
npm install
npm run dev                  # → http://localhost:3000
```

## Database Cheatsheet

Connect to PostgreSQL from inside the dev container:

```bash
psql postgresql://presence:presence@postgres:5432/presence
```

| Command | Description |
|---|---|
| `\dt` | List all tables |
| `\d emails_raw` | Show `emails_raw` schema |
| `SELECT * FROM emails_raw LIMIT 5;` | Preview raw emails |
| `SELECT * FROM email_stories LIMIT 5;` | Preview extracted stories |
| `SELECT filter_outcome, count(*) FROM email_filter_metrics GROUP BY 1;` | Pre-filter outcomes breakdown |
| `SELECT id, label, story_count FROM topics ORDER BY last_story_at DESC LIMIT 10;` | Preview topics with labels |

## Component READMEs

- [**Dashboard**](apps/dashboard/README.md) — Frontend setup & development
- [**Worker**](services/worker/README.md) — IMAP ingestion & processing service
- [**Infra**](infra/README.md) — Docker Compose & Dev Container setup

## License

See [LICENSE](LICENSE).
