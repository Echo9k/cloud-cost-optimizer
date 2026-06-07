# Cloud Cost Optimizer & Remediation Engine

An **API-first FinOps tool**. It ingests two exports — a cost export (CUR-shaped)
and a utilization export (CloudWatch-shaped) — joins them on resource ID, flags
idle and orphaned resources, and **proposes** decommission commands for a human
to run. **It detects and recommends; it never executes.** The running app holds
no credential that can mutate or delete anything.

Why two feeds: a billing row proves a resource *cost money*, not that it's
*idle*. Billed quantity (instance-hours) is identical whether CPU is at 2% or
90%. Utilization is the only signal that separates idle from busy — so the
metrics feed is mandatory, not optional.

## Stack

- **Python 3.12**, FastAPI, SQLite, Pydantic, SQLAlchemy.
- [`uv`](https://docs.astral.sh/uv/) for dependency management.
- Dashboard is a thin static client that consumes the API only (no cloud
  identity, never talks to AWS).

## Run from zero

From a fresh clone — **no AWS credentials needed; this runs entirely on
synthetic fixtures.**

```bash
# 1. Install dependencies (creates a local .venv, Python 3.12)
uv sync

# 2. Start the API + dashboard (one process). Creates a fresh SQLite file.
uv run uvicorn app.main:app
#    -> serving on http://127.0.0.1:8000
```

In a **second terminal**, ingest the two synthetic fixtures (this is the step the
dashboard needs before it shows anything):

```bash
curl -s -F cur_file=@files/cur_sample.csv \
        -F utilization_file=@files/utilization_sample.csv \
        http://127.0.0.1:8000/ingest
#    -> {"billing_rows":56,"utilization_rows":42}
```

Then open the dashboard:

```
http://127.0.0.1:8000/
```

You'll see **$37.94/mo claimed waste** and three findings, sorted by waste:

| Resource | Finding | Confidence | Command | Waste |
|---|---|---|---|---|
| `i-0b2idle002` | permanently idle | 0.9 (High) | `aws ec2 terminate-instances …` | $29.95/mo |
| `vol-0d4orph04` | orphan / data gap | 0.3 (Low) | `aws ec2 delete-volume …` | $7.99/mo |
| `i-0c3period03` | scheduling candidate | 0.4 (Caution) | *no terminate — review* | $0.00 |

Click **Approve** on an actionable finding: its status flips to `approved` and
persists, and the command becomes copy-pasteable. **You** run it in your own
terminal — that copy-paste step is the confirmation layer, by design.

### API endpoints

- `POST /ingest` — upload the two CSV feeds.
- `GET /resources` — raw billing-primary join (cost rows + utilization series).
- `GET /detections` — binary detection signals.
- `GET /findings` — findings with confidence, caveat, proposed command, status.
- `POST /findings/{resource_id}/approve` — flip status to `approved` (persists;
  executes nothing).

### Tests

```bash
uv run pytest
```

Edge-case fixtures and their expected behavior live in
[`files/EDGE_CASES.md`](files/EDGE_CASES.md).

## Teardown / decommission

**Nothing to decommission.** This MVP runs entirely on synthetic fixtures in
`files/`. It makes **no live cloud calls** and creates **no cloud resources**, so
there is no account state to tear down and no live test resources to confirm
closed. The running system's maximum capability is to *read a local CSV*.

The only state it creates is a local SQLite file (`cost_optimizer.db`, gitignored).
To reset to zero, stop the server and delete it:

```bash
rm -f cost_optimizer.db
```

The proposed `aws …` commands are **strings** surfaced for a human to run with
their own credentials — the app never executes them. This airgap is the design
thesis, not a limitation.
