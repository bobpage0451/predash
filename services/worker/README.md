# Worker Service

The worker is a Python service responsible for **ingesting emails via IMAP**, extracting stories with LLMs, **grouping stories into topics**, and **matching stories against user-defined desired actions** — all stored in PostgreSQL.

## What It Does

1. **IMAP Ingestion** — Connects to an IMAP mailbox over TLS, fetches new messages (incremental by UID), parses headers/body, and writes them to `emails_raw`.
2. **Pre-LLM Filtering** — Before calling the LLM, each email is scored with lightweight heuristics (header signals, sender pattern, body quality). Emails that score below the confidence threshold or fail quality checks are stamped in `email_filter_metrics` and skipped, saving LLM cost on receipts, password-reset emails, and pure-promo blasts.
3. **Story Extraction** — Sends emails that pass the filter to Ollama to extract individual `email_stories` with headline, summary, tags, and `action_type`. Newsletters with multiple topics produce multiple stories.
3. **Embedding** — Computes vector embeddings (768-dim, via Ollama `nomic-embed-text`) for each story.
4. **Topic Assignment** — Groups stories into `topics` using pgvector cosine similarity with centroid matching. Topics are matchable if recent (≤60 days) or evergreen (≥20 stories). New topics are created when no match exceeds the similarity threshold (default 0.85). When a topic accumulates ≥2 stories, a short label is auto-generated via Ollama.
5. **Embed Desired Actions** — Computes embeddings for user-created desired actions that don't have one yet. Actions are also embedded inline when created via the dashboard API.
6. **Action Matching** — Cross-joins desired actions against stories using pgvector cosine distance. Matches above the similarity threshold (default 0.72) are stored in `action_matches`, with an optional `action_type` filter bonus.
7. **Deduplication** — Uses `message_id`, `imap_uid`, and `sha256` to avoid duplicate inserts.

> The pre-filter is idempotent and uses `session.merge()`, so re-running after adjusting `NEWSLETTER_CONFIDENCE_THRESHOLD` will overwrite old decisions without manual cleanup.

## Project Structure

```
services/worker/
├── app/
│   ├── __init__.py
│   ├── __main__.py            # `python -m app` entry point (full pipeline)
│   ├── main.py                # Full pipeline runner (all stages sequentially)
│   ├── db.py                  # SQLAlchemy engine & session factory
│   ├── models.py              # ORM models (emails_raw, email_stories, topics)
│   ├── imap/
│   │   ├── __init__.py
│   │   ├── __main__.py        # `python -m app.imap` entry point
│   │   └── ingest.py          # One-shot IMAP fetch logic
│   └── llm/
│       ├── __init__.py
│       ├── __main__.py          # `python -m app.llm [--stories|--embeddings|--topics|--embed-actions|--match-actions]`
│       ├── ollama_client.py     # Ollama HTTP API client (chat + embed)
│       ├── extract_stories.py   # Story extraction from emails
│       ├── compute_embeddings.py  # Embedding backfill for stories
│       ├── assign_topics.py     # Topic assignment via centroid matching
│       ├── generate_topic_label.py # LLM-based topic label generation
│       ├── embed_desired_actions.py # Embed desired action descriptions
│       └── match_actions.py     # Match stories against desired actions
├── alembic/                   # Database migrations
├── alembic.ini                # Alembic configuration
├── scripts/
│   └── db_check.py            # Smoke test: insert & query dummy data
├── requirements.txt
├── .env.example               # Template for environment variables
└── .env                       # Your local config (git-ignored)
```

## Setup

### 1. Install dependencies

```bash
cd /workspace/services/worker
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
```

Edit `.env` with your IMAP credentials:

```dotenv
IMAP_HOST=mail.eclipso.de
IMAP_PORT=993
IMAP_USER=you@eclipso.de
IMAP_PASS=your-password-here
IMAP_MAILBOX=INBOX
```

Optional variables:

| Variable | Default | Description |
|---|---|---|
| `EMAIL_SOURCE` | `imap:{IMAP_HOST}` | Source identifier stored with each email |
| `IMAP_LIMIT` | _(unlimited)_ | Max number of messages to fetch per run |
| `DATABASE_URL` | `postgresql://presence:presence@postgres:5432/presence` | PostgreSQL connection string |
| `OLLAMA_BASE_URL` | `http://ollama:11434` | Ollama API endpoint |
| `OLLAMA_MODEL` | `llama3.1:8b` | Default LLM model |
| `PROCESSOR_NAME` | `ollama` | Processor name tag for run tracking |
| `OLLAMA_TIMEOUT_SECONDS` | `120` | HTTP timeout per LLM call |
| `EMAIL_PROCESS_LIMIT` | `50` | Default max emails per run |
| `EMBEDDING_MODEL` | `nomic-embed-text` | Ollama embedding model |
| `TOPIC_ASSIGN_LIMIT` | _(unlimited)_ | Default max stories for topic assignment |
| `TOPIC_STORY_FETCH_WINDOW_DAYS` | `0` (all) | Only fetch stories from the last N days |
| `ACTION_MATCH_LIMIT` | `0` (unlimited) | Max stories to consider per action match run |
| `ACTION_SIM_THRESHOLD` | `0.72` | Cosine similarity threshold for action matching |
| `NEWSLETTER_CONFIDENCE_THRESHOLD` | `0.5` | Min confidence score for an email to reach the LLM (0.0–1.0) |

## Usage

### Run full pipeline

```bash
python -m app                         # run all 6 stages sequentially
python -m app --limit 10              # forward --limit to all stages
python -m app --stop-on-error         # abort on first stage failure
python -m app --source "eclipso:user" # filter story extraction by source
```

Runs the entire pipeline end-to-end: **IMAP ingest → story extraction → embedding backfill → topic assignment → embed desired actions → action matching**. Each stage gets a log banner with timing, and you get a summary table at the end. By default, failures in one stage don't block the next.

CLI flags:

| Flag | Description |
|---|---|
| `--limit N` | Max items per stage (forwarded to all sub-commands) |
| `--source <s>` | Filter by source (forwarded to story extraction) |
| `--mailbox <m>` | Filter by mailbox (forwarded to story extraction) |
| `--stop-on-error` | Abort pipeline on first stage failure (default: continue) |

### Run IMAP ingestion

```bash
python -m app.imap
```

This performs a **one-shot fetch**: connects to IMAP, downloads new messages since the last ingested UID, parses them, and inserts into `emails_raw`.

### Run story extraction

```bash
python -m app.llm                    # default: extract stories
python -m app.llm --stories          # explicit: same as above
python -m app.llm --limit 10        # cap to 10 emails
```

Each candidate email is first scored by the **pre-LLM filter** (heuristics only, no network call). Emails that fail the confidence or quality checks are recorded in `email_filter_metrics` with `filter_outcome = "low_confidence" | "poor_quality"` and skipped. Only emails with `filter_outcome = "pass"` are sent to Ollama. Results are written to `email_stories`. Incremental and idempotent.

CLI flags:

| Flag | Description |
|---|---|
| `--limit N` | Max emails to process (default: `EMAIL_PROCESS_LIMIT` or 50) |
| `--source <s>` | Filter by `EmailRaw.source` |
| `--mailbox <m>` | Filter by `EmailRaw.mailbox` |
| `--model <m>` | Override Ollama model |
| `--prompt-version <v>` | Override prompt version |
| `--processor <p>` | Override processor name |
| `--no-since-last` | Skip checkpoint filter (reprocess all unprocessed) |

### Run embedding backfill

```bash
python -m app.llm --embeddings
python -m app.llm --embeddings --limit 100
```

Computes vector embeddings for stories that don't have one yet.

### Run topic assignment

```bash
python -m app.llm --topics
```

Groups unassigned stories into topics using vector similarity against topic centroids. Creates new topics when no match exceeds the threshold. When a topic gains its 2nd+ story, a label is auto-generated via Ollama. Idempotent and safe to rerun.

CLI flags:

| Flag | Description |
|---|---|
| `--limit N` | Max stories to process (default: `TOPIC_ASSIGN_LIMIT` or unlimited) |
| `--sim-threshold F` | Cosine similarity threshold for assignment (default: `0.85`) |
| `--ollama-base-url URL` | Ollama API endpoint for label generation (default: `OLLAMA_BASE_URL`) |
| `--ollama-model M` | Ollama model for label generation (default: `OLLAMA_MODEL`) |

### Run desired action embedding

```bash
python -m app.llm --embed-actions
python -m app.llm --embed-actions --limit 10
```

Embeds desired action descriptions that don't have a vector yet. Also runs automatically as pipeline stage 5. Actions created via the dashboard API are embedded inline on save, so this is mainly a batch fallback.

### Run action matching

```bash
python -m app.llm --match-actions
python -m app.llm --match-actions --sim-threshold 0.72
```

Matches email stories against active desired actions using pgvector cosine similarity. Inserts new matches into `action_matches` (idempotent via unique constraint). Optionally checks if the story's `action_type` matches the action's `action_types` filter.

CLI flags:

| Flag | Description |
|---|---|
| `--limit N` | Max stories to consider per action (default: `ACTION_MATCH_LIMIT` or unlimited) |
| `--sim-threshold F` | Cosine similarity threshold (default: `ACTION_SIM_THRESHOLD` or `0.72`) |

### Run database smoke test

```bash
python scripts/db_check.py
```

Inserts dummy rows into `emails_raw` and `email_stories`, then queries them back to verify the DB connection and schema are working.

## Database Migrations (Alembic)

```bash
# Generate a new migration after changing models.py
alembic revision --autogenerate -m "describe your change"

# Apply all pending migrations
alembic upgrade head

# Check current migration state
alembic current
```

## Key Models

### `emails_raw`

Stores raw email data as ingested from IMAP. Key fields: `source`, `mailbox`, `message_id`, `imap_uid`, `from_addr`, `subject`, `body_text`, `body_html`, `raw_headers`, `sha256`.

### `email_stories`

Individual stories extracted from emails. Key fields: `email_id` (FK → `emails_raw`), `headline`, `summary`, `tags`, `action_type`, `embedding` (VECTOR(768)), `topic_id` (FK → `topics`).

### `topics`

Topic clusters built from story embeddings via centroid matching. Key fields: `centroid_embedding` (VECTOR(768)), `story_count`, `last_story_at`, `label` (NULL until LLM-generated), `status`.

### `desired_actions`

User-defined actions to watch for. Key fields: `description`, `action_types` (JSONB array of types to filter), `embedding` (VECTOR(768)), `active` (boolean).

### `action_matches`

Matches between desired actions and email stories. Key fields: `desired_action_id` (FK → `desired_actions`), `story_id` (FK → `email_stories`), `similarity_score`, `action_type_matched`, `matched_at`. Unique on `(desired_action_id, story_id)`.

### `email_filter_metrics`

Pre-LLM heuristic scores — one row per email, written before any LLM call. Key fields: `email_id` (FK → `emails_raw`, unique), `confidence` (0–1 float), `quality` (`"good"` / `"poor"` / `"skip"`), `filter_outcome` (`"pass"` / `"low_confidence"` / `"poor_quality"`). Raw signal columns (`word_count`, `link_density`, `text_html_ratio`, `avg_sentence_len`, `cta_count`, `has_list_unsubscribe`, `has_bulk_precedence`, `esp_detected`) are stored individually for threshold tuning. Rows are overwritten on re-run via `MERGE`, so changing `NEWSLETTER_CONFIDENCE_THRESHOLD` and re-running is all that's needed to re-evaluate.
