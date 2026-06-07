# Edge-case fixtures — expected behavior

These probe the detection boundaries. They are **separate** from the demo
fixtures (`cur_sample.csv` / `utilization_sample.csv`) so the demo numbers and
their tests stay intact. **No thresholds or detection logic were changed to make
these pass** (one genuine bug was surfaced and fixed — case C).

Ingest with the same endpoint:

```bash
curl -s -F cur_file=@files/edge_cur_sample.csv \
        -F utilization_file=@files/edge_utilization_sample.csv \
        http://127.0.0.1:8000/ingest
```

| Case | Resource | Setup | Probes | Expected behavior |
|---|---|---|---|---|
| **A** | `i-0edgebound15` | CPU flat **exactly 15.0** every day | Strict `<` at the idle threshold | **Active, no finding.** `mean = 15.0` is *not* `< 15.0`; every day is non-idle so `idle_ratio = 0.0` (outside the scheduling band). The boundary is exclusive. |
| **B** | `i-0edgesched60` | 6 days @ 2% + 4 days @ 80% (overall mean 33.2%) | Inclusive `<=` at the scheduling band max (0.60) | **Scheduling-candidate.** Overall mean ≥ 15 (not permanently idle), `idle_ratio = 6/10 = 0.60` which is `<= 0.60` → flagged, confidence 0.4, **no terminate**, waste $0. |
| **C** | `i-0edgenocpu0` | Utilization rows present but **only `NetworkIn`** (no `CPUUtilization`) | No-CPU-signal handling | **Orphan / no-metrics finding** (confidence 0.3). Before the M6 fix this hit `sum([])/len([])` → `ZeroDivisionError` → HTTP 500. No CPU signal means no utilization signal to judge idle, so it is treated as the most deferential (orphan) case. |
| **D** | `i-0edgerevorph` | Utilization rows present but **no billing row** (reverse orphan) | Billing-primary LEFT join | **Not surfaced at all.** The join is billing-primary; a resource we are not billed for produces no finding (and does not appear in `/resources`). Metrics without a cost row are out of scope. |

Summary of findings produced by the edge set: **A → none, B → scheduling
($0), C → orphan ($29.95/mo), D → none.** Two findings total.
