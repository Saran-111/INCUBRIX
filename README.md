# IncuBrix Long-Tail Destination Network

[![Python](https://img.shields.io/badge/Python-3.11%20%7C%203.12%20%7C%203.13-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg)](https://fastapi.tiangolo.com)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED.svg)](https://www.docker.com/)
[![Tests](https://img.shields.io/badge/Tests-42%2F42%20Passing-brightgreen.svg)](https://pytest.org)
[![OpenAPI](https://img.shields.io/badge/OpenAPI-3.1.0-6BA539.svg)](file:///openapi.yaml)

A production-grade, containerised connector service and rule-respecting distribution engine built for **IncuBrix Engineering Assessment 4**. 

It expands IncuBrix distribution beyond the 15 major platforms into hundreds of long-tail destinations: Discourse forums, Lemmy federated nodes, Dev.to & Hashnode developer publications, Ghost newsletters, Slack workspaces, signed HMAC partner webhooks, and manual assisted communities (Subreddits, Facebook Groups, Indie Hackers).

---

## 🏛️ Architecture Overview

```
                          [ Creator Rendition ]
                                   │
                                   ▼
         ┌──────────────────────────────────────────────────┐
         │       IncuBrix Ingestion & Validation Gateway     │
         │   • Idempotency Store (Header: Idempotency-Key)  │
         │   • Structured JSON Logger (X-Correlation-Id)    │
         └─────────────────────────┬────────────────────────┘
                                   │
                                   ▼
         ┌──────────────────────────────────────────────────┐
         │             Content Tailoring Engine             │
         │   • Discussion-first framing for forum nodes     │
         │   • Canonical URL preservation for SEO           │
         │   • Smart word-boundary truncation               │
         │   • Mandatory AI disclosure auto-injection       │
         └─────────────────────────┬────────────────────────┘
                                   │
                                   ▼
         ┌──────────────────────────────────────────────────┐
         │               Posting Rules Engine               │
         │   • Frequency cap enforcement (1/24h, 1/7d)      │
         │   • Strict self-promotion & commercial blocker   │
         │   • Hyperlink restriction & policy guard         │
         │   • Automation prohibition / assisted gate       │
         └─────────────────────────┬────────────────────────┘
                                   │
                                   ▼
         ┌──────────────────────────────────────────────────┐
         │       Appendix A Connector Contract Runtime      │
         │      POST /connector/v1/{connector_key}/{method} │
         └───────┬─────────┬─────────┬─────────┬────────────┘
                 │         │         │         │
                 ▼         ▼         ▼         ▼
             Discourse   Lemmy    Dev.to     Ghost
             Hashnode    Slack   Mailchimp  Webhook(HMAC)
                 │
                 ▼
          Assisted Pack Tier (Files + Tailored Text + Rule Checklist)
```

### Key Architectural Tenet: "One Connector, Many Destinations"
A connector is the code for a platform type. A destination is a single configuration row. Adding forum #41 requires zero code changes—it is simply a new entry in the destination catalogue.

---

## 🚀 Quickstart: Setup in Under 10 Commands

### Option A: Local Standalone (Python 3.11+)

```bash
# 1. Clone repository
git clone <repo_url> && cd INCUBRIX

# 2. Create and activate virtual environment
python -m venv .venv
.\.venv\Scripts\activate   # Windows
# source .venv/bin/activate # Linux/macOS

# 3. Install dependencies
pip install -r requirements.txt

# 4. Copy environment configuration
cp .env.example .env

# 5. Run test suite (42 unit, integration, and contract tests)
pytest -v

# 6. Start server
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### Option B: Docker Compose (One-Command Clean Machine)

```bash
# 1. Start all containers (Service + MinIO + Ghost + Lemmy Stateful Mock)
docker compose up -d

# 2. Run simulation test suite inside container (Safe Default)
docker compose exec service pytest -v

# 3. Run real-HTTP local integration tests (Against live container TCP sockets)
docker compose exec -e SIMULATION_MODE=false service pytest -v tests/test_local_instances.py tests/test_live_certification.py

# 4. Access web dashboard & API docs
# Dashboard: http://localhost:8000/
# OpenAPI Docs: http://localhost:8000/docs
```

---

## 🧪 Testing & Verification

### Running the Full Test Suite
The service includes 42 comprehensive tests covering all Appendix A contract methods, posting rules, idempotency with race condition locks, metadata hashing, edge cases, 1,000-row catalogue import benchmark, recommender precision, cryptographic HMAC verification, and both simulation & local HTTP integration certification suites:

```bash
pytest -v
```

### Running the Batch Runner CLI (Integration Standard 10)
A command-line tool that runs an entire folder of test inputs against the API and writes structured outputs to a destination folder:

```bash
python cli/batch_runner.py --input data/test_inputs --output data/batch_output --api-url http://localhost:8000
```

---

## 🔌 Appendix A: IncuBrix Connector Contract

All connectors expose methods at `POST /connector/v1/{connector_key}/{method}`:

| Method | Payload | Returns | Description |
| :--- | :--- | :--- | :--- |
| `validate` | `rendition, destination, connection` | `{ok, violations[]}` | Validates surface format limits (chars, tags, links) |
| `publish` | `rendition, destination, connection, idempotency_key` | `{platform_post_id, live_url, status}` | Delivers post or packages manual assist pack |
| `get_status`| `platform_post_id, connection` | `{status, live_url}` | Confirms post is live and accessible |
| `delete` | `platform_post_id, connection` | `{deleted}` | Deletes post from destination sandbox |
| `fetch_metrics` | `platform_post_id, connection, since` | `{views, likes, comments, shares, clicks}` | Fetches normalized engagement metrics |
| `build_assist_pack` | `rendition, destination` | `{files[], caption, deep_link, checklist[]}` | Builds ready-to-post human package |

### Shared Error Codes Table

| Code | Retryable? | Description |
| :--- | :---: | :--- |
| `DEST_SPEC_VIOLATION` | No | Content breaks format limits; returns field-level violations |
| `DEST_RULE_FREQUENCY_CAP` | Later | Cooldown window active; returns reschedule timestamp |
| `CONNECTION_AUTH_EXPIRED` | After Reconnect | Access token or API key revoked/expired (HTTP 401/403) |
| `PLATFORM_RATE_LIMIT` | Yes | HTTP 429 received; backs off using `Retry-After` header |
| `PLATFORM_QUOTA_EXHAUSTED` | Next Window | Daily quota exhausted; reschedule for tomorrow |
| `PLATFORM_CONTENT_REJECTED` | No | Moderation filter rejected content |
| `PLATFORM_UNAVAILABLE` | Yes | Platform unreachable / timeout (stops after 5 retries) |
| `CONNECTOR_DISABLED` | No | Emergency kill switch enabled for connector |

---

## ⚙️ Configuration Reference (.env)

| Variable | Default | Description |
| :--- | :--- | :--- |
| `SIMULATION_MODE` | `true` | When true, runs against local mocks with zero external API keys |
| `STORAGE_TYPE` | `local` | `local` filesystem or `s3` compatible (MinIO) |
| `S3_ENDPOINT_URL` | `http://localhost:9000` | MinIO endpoint URL |
| `HMAC_SECRET` | `incubrix-secret` | Secret key used for signing webhook callbacks |
| `FREQUENCY_CAP_WINDOW_HOURS` | `24` | Default frequency cap window duration |
| `AUTO_DELETE_MAX_MINUTES` | `10` | Hard threshold for test probe deletion |
