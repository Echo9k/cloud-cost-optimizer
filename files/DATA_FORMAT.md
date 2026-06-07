# Data Format — Cost Optimizer Inputs

The tool ingests **two** exports and joins them on resource ID. This mirrors real FinOps
tooling: billing tells you *what you pay*, metrics tell you *whether it's used*. Neither
alone is sufficient — see "Why two files" below.

---

## File 1 — `cur_sample.csv` (AWS Cost and Usage Report, legacy schema)

Slash-prefixed columns. We use the minimal faithful subset; a real CUR has 100+ columns,
but `identity/`, `bill/`, and `lineItem/` always appear and are all we need.

| Column | Meaning | Used for |
|---|---|---|
| `identity/LineItemId` | Unique per line item per partition (not stable across reports) | row id only |
| `bill/BillingPeriodStartDate` | Billing month start | grouping |
| `lineItem/UsageAccountId` | Account that incurred the cost | grouping |
| `lineItem/LineItemType` | `Usage`, `Tax`, `Credit`, etc. | filter to `Usage` |
| `lineItem/UsageStartDate` / `UsageEndDate` | The time window for this row | **time series per resource** |
| `lineItem/ProductCode` | e.g. `AmazonEC2` | classification |
| `lineItem/UsageType` | e.g. `BoxUsage:t3.medium`, `EBS:VolumeUsage.gp3` | resource-type + waste signatures |
| `lineItem/Operation` | e.g. `RunInstances`, `CreateVolume` | classification |
| `lineItem/ResourceId` | The instance/volume ID — **the join key** | join to metrics |
| `lineItem/UsageAmount` | **Billed quantity** (instance-hours, GB-Mo) — NOT utilization | cost attribution |
| `lineItem/UnblendedRate` / `UnblendedCost` | Per-unit rate and resulting cost | $ savings calc |
| `product/ProductName`, `product/region` | Human labels | display |
| `resourceTags/user/Name` | A user tag (dynamic; may be absent) | display |

**Critical:** `UsageAmount` is what you're *billed*, not how *busy* the resource is. A
running EC2 instance bills ~24 instance-hours/day whether its CPU is at 2% or 90%. In this
fixture the EC2 cost rows for the active, idle, and periodic instances are **identical** —
that's the point. Cost alone cannot tell them apart.

---

## File 2 — `utilization_sample.csv` (CloudWatch-shaped metrics)

| Column | Meaning |
|---|---|
| `resource_id` | Matches `lineItem/ResourceId` — **the join key** |
| `timestamp` | Sample time (daily here; hourly in production) |
| `namespace` | e.g. `AWS/EC2` |
| `metric_name` | e.g. `CPUUtilization` |
| `statistic` | `Average`, `Maximum`, etc. |
| `value` | The metric value |
| `unit` | e.g. `Percent` |
| `period_seconds` | Aggregation window (86400 = daily) |

---

## Why two files (the join)

Join `cur_sample.csv.lineItem/ResourceId` = `utilization_sample.csv.resource_id`.
- Cost without a matching metric row → candidate **orphan** (e.g. a volume with no compute
  metric). This is *state* inferred from absence, and covers the "unattached disk" case.
- Cost with a metric row → evaluate the utilization **shape** for idle vs periodic.

---

## Scenario design (what each resource exercises)

Fixture spans 14 days starting Mon 2026-05-18, so the weekday/weekend cadence is visible.

| Resource | Cost signature | Utilization | Expected Finding |
|---|---|---|---|
| `i-0a1active01` | flat ~$1.00/day | ~68–70% flat | **none** — clearly in use |
| `i-0b2idle002` | flat ~$1.00/day | ~1.5–2% flat | **idle, high confidence** |
| `i-0c3period03` | flat ~$1.00/day | ~3.5% weekends, ~61–64% weekdays | **idle candidate, LOW confidence + caveat** — the false-positive guard |
| `vol-0d4orph04` | flat ~$0.27/day | *no metric row* | **orphan volume** — detected via absence (state, not utilization) |

The periodic instance is the centerpiece: identical cost to the idle one, but its
utilization *shape* (low mean, high variance, weekday periodicity) is what stops the
engine from confidently recommending you kill something that's busy every Monday.
