# ☁️ Cloud Cost Optimizer & Remediation Engine

An **API-first**, Python-based engine that ingests cloud resource inventory,
detects waste with a pluggable **rules engine**, and **remediates** findings
through a safe, audited workflow. Ships with a zero-dependency dashboard and a
SQLite backing store — no cloud account or paid services required.

> **MVP status.** The remediation layer mutates a *simulated* fleet stored in
> SQLite so the full detect → recommend → remediate → audit loop is runnable
> end-to-end. Swapping the `_apply_*` handlers in `app/remediation.py` for real
> provider SDK calls (boto3, etc.) is the productionization path.

## Features

- **Rules engine** (`app/optimizer.py`) — pure, unit-testable rules:
  - `idle` — running compute with negligible CPU → stop
  - `rightsize` — lightly-used compute → drop a size tier
  - `orphaned` — unattached volumes / IPs → delete
  - `stale` — long-stopped resources still billing storage → delete
  - `untagged` — governance: missing cost-allocation tags
- **Remediation engine** (`app/remediation.py`) — **dry-run by default**;
  every action (simulated or applied) is written to an audit table.
- **REST API** (FastAPI) with auto-generated OpenAPI docs at `/docs`.
- **Dashboard** (`/`) — KPIs, savings-by-category bars, and a one-click
  Apply / Dry-Run / Dismiss workflow. Vanilla JS, no CDN.
- **SQLite** store via SQLAlchemy 2.0 — free, file-based, zero setup.

## Quick start

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Then open **http://localhost:8000** and click:

1. **Load Demo Fleet** — seeds 7 synthetic multi-cloud resources.
2. **Run Optimizer Scan** — generates recommendations.
3. **Apply / Dry Run / Dismiss** on any finding.

API docs: **http://localhost:8000/docs**

## Core API

| Method | Path                                          | Purpose                              |
|--------|-----------------------------------------------|--------------------------------------|
| GET    | `/api/resources`                              | List inventory                       |
| POST   | `/api/resources`                              | Ingest a resource                    |
| POST   | `/api/resources/seed`                         | Load the demo fleet                  |
| POST   | `/api/optimizer/scan`                         | Run the rules engine                 |
| GET    | `/api/recommendations`                        | List findings (filter by status/severity/type) |
| POST   | `/api/recommendations/{id}/remediate`         | Remediate (`{"dry_run": true|false}`) |
| POST   | `/api/recommendations/{id}/dismiss`           | Dismiss a finding                    |
| GET    | `/api/remediations`                           | Audit trail                          |
| GET    | `/api/summary`                                | Dashboard KPIs                       |

## Configuration

Thresholds are environment-overridable (see `app/config.py`):

| Variable | Default | Meaning |
|----------|---------|---------|
| `CCO_DATABASE_URL` | `sqlite:///./cco.db` | SQLAlchemy URL |
| `CCO_IDLE_CPU_PCT` | `5.0` | Below this avg CPU% → idle |
| `CCO_RIGHTSIZE_CPU_PCT` | `40.0` | Below this (and above idle) → rightsize |
| `CCO_STALE_AGE_DAYS` | `30` | Stopped longer than this → stale |
| `CCO_REQUIRED_TAGS` | `owner,environment,cost-center` | Governance tags |

## Tests

```bash
pytest -q          # 18 tests: rules engine (unit) + API (e2e)
```

## Architecture

```
app/
├── main.py         FastAPI app + dashboard
├── config.py       Tunable thresholds
├── database.py     SQLAlchemy engine/session (SQLite)
├── models.py       Resource · Recommendation · RemediationAction
├── schemas.py      Pydantic API contracts
├── optimizer.py    Rules engine (detect → recommend)
├── remediation.py  Remediation engine (safe, audited)
├── seed.py         Synthetic multi-cloud fleet
├── routers/        resources · recommendations · remediation · summary
└── templates/      dashboard.html
```

**Design principles:** safe-by-default remediation, pure/testable rules,
data-driven thresholds, and a clean separation between detection (optimizer)
and action (remediation).
