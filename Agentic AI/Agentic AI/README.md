# Personal Finance Coach — Backend

A deterministic personal finance management backend built with Python and FastAPI. It ingests transaction data, categorises spending, detects recurring payments, generates financial nudges, runs what-if simulations, and provides rule-based financial coaching.

---

## Table of Contents

1. [What It Does](#what-it-does)
2. [Architecture](#architecture)
3. [Prerequisites](#prerequisites)
4. [Installation](#installation)
5. [Environment Configuration](#environment-configuration)
6. [Database Initialisation](#database-initialisation)
7. [Starting the Server](#starting-the-server)
8. [Running Tests](#running-tests)
9. [API Documentation (Swagger)](#api-documentation-swagger)
10. [API Reference](#api-reference)
11. [Supported Ingestion Formats](#supported-ingestion-formats)
12. [Frontend Integration](#frontend-integration)
13. [Database Persistence](#database-persistence)
14. [Security Limitations](#security-limitations)
15. [Deployment Prerequisites](#deployment-prerequisites)
16. [Known Issues and Future Work](#known-issues-and-future-work)

---

## What It Does

- **Transaction ingestion**: CSV statements, PDF statements (table-based), SMS text parsing
- **Auto-categorisation**: Rule-based with learned corrections
- **Recurring payment detection**: Identifies monthly/weekly subscription patterns
- **Financial metrics**: Income, expenses, savings rate, emergency runway, month-over-month comparison
- **What-if simulations**: Model the impact of spending reductions or subscription cancellations
- **Financial nudges**: Data-driven alerts for budget overruns, high spending, low runway
- **Deterministic coaching**: Intent-aware financial Q&A with no external LLM dependency
- **Goal tracking**: CRUD for savings goals with progress tracking
- **PII sanitisation**: Strips account numbers, emails, phone numbers, and PAN cards from coach inputs

---

## Architecture

```
main.py                  ← FastAPI application, route registration, CORS
db.py                    ← SQLite connection, schema initialisation
schemas.py               ← Pydantic request/response models
routers/
  ingest.py              ← POST /ingest/file, /ingest/sms, /ingest/sample
  transactions.py        ← GET /transactions, PATCH /transactions/{id}/category
  subscriptions.py       ← GET /subscriptions, POST /subscriptions/{merchant}/unused
  profile.py             ← GET /profile, PUT /profile
  goals.py               ← GET/POST /goals, PUT/DELETE /goals/{id}
  whatif.py              ← POST /whatif, GET /whatif/presets, POST /whatif/presets/{name}/apply
  coach.py               ← POST /coach/chat
  report.py              ← GET /report/monthly
services/
  db_service.py          ← Database CRUD operations
  ingest.py              ← CSV, PDF, SMS parsing
  categorizer.py         ← Transaction categorisation and rule learning
  engine.py              ← Financial calculations and what-if simulation
  recurring.py           ← Recurring payment detection
  nudges.py              ← Nudge generation
  agent.py               ← Deterministic financial coach
  sanitizer.py           ← PII detection and redaction
data/
  sample_statement.csv   ← Demo data (6 months of transactions)
tests/
  test_phase1.py         ← Ingestion, categorisation, profiles, goals (15 unit tests)
  test_phase2.py         ← Financial engine, recurring, nudges
  test_phase3.py         ← What-if simulation, coach
  integration/
    test_api.py          ← End-to-end API tests via FastAPI TestClient (29 tests)
```

**Database**: SQLite (single file). All tables are created automatically on first run.

---

## Prerequisites

- Python 3.11 or newer (tested on Python 3.13)
- pip

No other infrastructure is required. The database is a local file.

---

## Installation

```bash
# Clone or copy the repository
cd personal-finance-coach

# Create and activate a virtual environment (strongly recommended)
python3 -m venv venv
source venv/bin/activate       # macOS / Linux
# .\venv\Scripts\activate      # Windows

# Install dependencies
pip install -r requirements.txt
```

---

## Environment Configuration

Copy the example environment file and edit it:

```bash
cp .env.example .env
```

Edit `.env`:

```env
# Deployment environment ("development" or "production").
ENVIRONMENT=development

# Path to the SQLite database file.
DATABASE_URL=finance.db

# Comma-separated allowed CORS origins.
# Use "*" only for local development.
ALLOWED_ORIGINS=http://localhost:3000

# Safety: allow POST /reset to wipe data (disabled by default; blocked in production).
ENABLE_RESET=false
```

> **Never commit `.env` to version control.** It is excluded in `.gitignore`.

---

## Database Initialisation

The database is created automatically when the server starts. No migration tool or external database server is required.

To initialise manually:

```bash
python3 db.py
```

> **The initialisation is idempotent** — running it on an existing database is safe. It uses `CREATE TABLE IF NOT EXISTS` and will not overwrite or delete existing data.

---

## Starting the Server

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

The `--reload` flag enables auto-reload on code changes. Remove it in production.

---

## Running Tests

```bash
# All tests (48 total)
python3 -m unittest discover tests/

# Phase-specific
python3 -m unittest tests/test_phase1.py -v
python3 -m unittest tests/test_phase2.py -v
python3 -m unittest tests/test_phase3.py -v

# Integration tests
python3 -m unittest tests/integration/test_api.py -v
```

Tests use isolated temporary databases. They never touch `finance.db`.

---

## API Documentation (Swagger)

With the server running, open:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **OpenAPI JSON**: http://localhost:8000/openapi.json

---

## API Reference

### System

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Health check. Returns `{"status": "ok"}` |
| `POST` | `/reset` | ⚠️ Wipes all data. Disabled by default; requires `ENABLE_RESET=true` and non-production environment. |
| `GET` | `/rules` | List all categorisation rules |
| `DELETE` | `/rules/{id}` | Delete a categorisation rule |
| `GET` | `/guardrail/log` | PII sanitisation audit log |

### Ingestion

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/ingest/file` | Upload CSV, PDF, or TXT file (multipart/form-data) |
| `POST` | `/ingest/sms` | Parse a single SMS string: `{"text": "..."}` |
| `POST` | `/ingest/sample` | Load bundled demo data |

### Transactions

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/transactions` | List transactions. Query params: `month` (YYYY-MM), `category`, `limit`, `offset` |
| `PATCH` | `/transactions/{id}/category` | Correct a category and learn a rule |

### Profile

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/profile` | Get the financial profile |
| `PUT` | `/profile` | Update profile fields: `monthly_budget`, `monthly_income`, `fixed_costs`, `emergency_fund`, `currency`, `risk_tolerance`, `goals_enabled` |

### Goals

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/goals` | List all goals |
| `POST` | `/goals` | Create a goal. Returns `201 Created` with the new goal object |
| `PUT` | `/goals/{id}` | Update a goal |
| `DELETE` | `/goals/{id}` | Delete a goal |

### Subscriptions

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/subscriptions` | List detected recurring payments (synced from transactions) |
| `POST` | `/subscriptions/{merchant}/unused` | Mark/unmark a subscription as unused: `{"unused": true}` |

### Dashboard & Nudges

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/dashboard` | Aggregated financial summary |
| `GET` | `/nudges` | List of data-driven financial nudges |

### What-If Simulations

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/whatif` | Run a custom simulation. Body: `{"changes": {"Food": -0.30, "cancel": ["Netflix"]}}` |
| `GET` | `/presets` | List preset scenarios |
| `POST` | `/presets/{name}/apply` | Apply a named preset simulation |

### Reports

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/report/monthly?month=YYYY-MM` | Monthly income/expense/savings report |

### Coach

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/coach/chat` | Ask the financial coach a question: `{"message": "Can I afford a laptop?"}` |

---

## Supported Ingestion Formats

### CSV

Expected columns (case-insensitive): `Date`, `Description`, `Amount`, `Category`, `Merchant`.

- Dates should be in `YYYY-MM-DD` format.
- Positive amounts are treated as income; negative as expenses.
- Missing `Category` or `Merchant` columns are tolerated — defaults are applied.
- Duplicate rows (same date + description + amount) are silently ignored.
- Maximum file size: **10 MB**.

### PDF

PDF bank statements are supported **only if they contain extractable table data** (not scanned/image-based PDFs). Parsing depends on the column layout: `date`, `description`/`particulars`, and `amount`/`value` columns must be present.

> ⚠️ PDF parsing is best-effort. Different banks format statements differently. If extraction fails, a 422 error is returned.

### SMS / TXT

Uploads a plain-text file containing a single SMS. Recognised pattern: `A/c XXNNNN debited/credited for Rs AMOUNT on DATE via UPI to MERCHANT`.

Alternatively, POST directly to `/ingest/sms` with `{"text": "..."}`.

### Limitations

- Only tabular PDFs are supported (not image/scanned PDFs).
- CSV must be UTF-8 encoded.
- Only one bank statement format is natively tested (the bundled `sample_statement.csv`).
- Different banks may use different column names or date formats. Custom parsing would need to be added.

---

## Frontend Integration

Each frontend developer receives the same backend source code and configures their own independent deployment.

**API base URL**: By default `http://localhost:8000`. Configure this in your frontend as an environment variable (e.g., `VITE_API_URL=http://localhost:8000`).

**CORS**: Set `ALLOWED_ORIGINS` in `.env` to the exact origin of your frontend (e.g., `http://localhost:3000`). The default `*` is convenient for development but must be restricted in any shared deployment.

**Swagger documentation**: Available at `<base_url>/docs` — useful for understanding request/response formats while building the frontend.

---

## Database Persistence

- The database is a SQLite file (default: `finance.db` in the project directory).
- The path is controlled by `DATABASE_URL` in `.env`.
- **The file must persist across deployments.** If the host destroys the filesystem on redeploy (e.g., Heroku dynos, ephemeral containers), financial data will be lost.
- For persistent deployments, either:
  - Mount a persistent disk/volume at the database path, or
  - Migrate to PostgreSQL (see [Known Issues](#known-issues-and-future-work)).
- Do **not** commit `finance.db` to version control — it is excluded in `.gitignore`.

---

## Security Limitations

### Single-User Deployment Model

This backend is designed for **single-user, isolated deployments**. Each developer receives a copy of the source code, configures their own environment, and runs their own instance serving a single user.

**Implications:**
- There is **no authentication**. Anyone who can reach the API can read and write all financial data.
- The `/reset` endpoint wipes all data. It is **disabled by default** and strictly blocked when `ENVIRONMENT=production`. Only enable it in development with `ENABLE_RESET=true`.
- `ALLOWED_ORIGINS=*` must be changed to your specific frontend origin before deploying.
- All data in the database belongs to one implicit user (`default`). There are no per-user ownership checks.

### What Is Implemented

- CORS configured via `ALLOWED_ORIGINS` (restrict in deployment)
- `.env` and `*.db` excluded from git
- PII sanitisation in coach inputs (account numbers, emails, phone numbers, PAN cards)
- Input validation via Pydantic
- File upload safety: 10 MB limit enforced chunk-by-chunk with immediate connection termination
- Supported file types validated before processing

### What Is NOT Implemented

- Authentication or session management
- Authorization or per-user data isolation
- Rate limiting
- HTTPS (must be configured at the reverse proxy / hosting layer)
- Audit logging for data access (only PII sanitisation events are logged)

> **Do not expose this API to the internet without an authentication layer** if any sensitive financial data is involved.

---

## Deployment Prerequisites

For a simple local or VM deployment:

1. Python 3.11+ installed on the server
2. A persistent filesystem location for `finance.db`
3. A process manager (e.g., `systemd`, `supervisor`) to keep uvicorn running
4. A reverse proxy (e.g., Nginx) for HTTPS and to set `ALLOWED_ORIGINS` appropriately

**Minimum start command:**

```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

**For production (without --reload):**

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 1
```

> Use `--workers 1` with SQLite. Multiple workers sharing the same SQLite file can cause write contention. If you need multiple workers, migrate to PostgreSQL.

---

## Known Issues and Future Work

### Current Limitations

| Issue | Impact | Workaround |
|-------|--------|------------|
| No authentication | Anyone reaching the API can access all data | Deploy behind a VPN or add HTTP Basic Auth at the proxy level |
| SQLite write concurrency | One uvicorn worker only | Use `--workers 1`; or migrate to PostgreSQL |
| PDF parsing is best-effort | Non-standard layouts may fail | Manual CSV upload |
| Dashboard `/dashboard` uses a fixed `"default"` user | Cannot serve multiple users | Single-user deployment model by design |
| `/reset` is unauthenticated | Anyone can wipe all data | Remove or disable in production |
| Emergency fund defaults to 50,000 | Inaccurate runway if profile not set | Set `emergency_fund` via `PUT /profile` |

### Future Work

- **Authentication**: Add JWT or API key authentication before any shared deployment
- **PostgreSQL support**: Required for multi-user or multi-instance deployments
- **Docker**: A `Dockerfile` and `docker-compose.yml` would simplify developer onboarding
- **PDF parser improvements**: Support more bank statement layouts
- **Goal projections**: Calculate realistic projected goal completion dates based on savings rate
- **Multi-currency support**: Currency conversion for international transactions
- **Webhook/push notifications**: Alert users of nudges via push
