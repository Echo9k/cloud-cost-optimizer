Lead Architect mode: ON.

We are building a Python-based, API-first **Cloud Cost Optimizer & Remediation Engine**
using a free database and a dashboard.

**Rules:**
● No Manual Edits: You provide all logic and fixes. I will not edit any code.
● Audit Log: You must maintain a file named prompts.md. After every turn, update that file (or
provide the text block) with the prompt I just used.
● Time-Check: Start a timer. Goal is an MVP in 4-6 hours (Max window: 16h). Report 'Elapsed
Time' at the end of every response. Acknowledge and let's start.

---

## M0 — planning prompt

STOP-AND-PLAN PROTOCOL — build ONE milestone at a time; no code until the plan is
ratified. Start at M0 and ONLY M0; do not read ahead and sprint to a finished app.
Read source-of-truth files (CLAUDE.md, MILESTONES.md, files/DATA_FORMAT.md + fixtures).
Confirm the three invariants (propose-never-execute; confidence + caveat via two-feed
join; orphan/absence is most deferential). FIRST reply: (a) rules ack, (b) three
invariants, (c) plan-mode task breakdown for M0 ONLY — app/models.py schemas, GET
/findings returning one hardcoded Finding, thin dashboard consuming the API, repo init
+ first commit. No code, no scaffolding beyond M0. Wait for explicit "ratified — build it".

## M0 — build prompt

Build it. Two clarifications: (1) Dashboard = FastAPI static route, one process.
(2) Contract location: Pydantic in app/models.py is correct; anticipate M1 — keep
Pydantic API-contract models separate from SQLite/SQLAlchemy ORM persistence models,
do not combine API schema with an ORM row; note the intent now, don't build it yet.
Build M0 (T1–T6) as planned. Commit at end. Report Elapsed Time and GET /findings
sample payload.