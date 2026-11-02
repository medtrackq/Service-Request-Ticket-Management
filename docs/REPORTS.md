# Dashboard & Report Calculations

All figures are computed live from database records (`backend/app/services/reports.py`).
No figures are fabricated. Sample tickets created by `python -m app.cli load-sample-data` are
flagged `is_sample = true`, shown with a "ตัวอย่าง / Sample" badge, counted in the KPI
`sample`, and can be excluded with the filter `include_sample=false` (or purged with
`python -m app.cli purge-sample-data`).

## Scope and filters

* Every statistic only covers tickets the user may see (same RBAC scope as the ticket list).
* Filters: creation date range (Asia/Bangkok calendar days), department, request type, status,
  status category, priority, assigned staff, sample data on/off.

## Definitions

| Metric | Definition |
|--------|------------|
| Total Tickets | Tickets matching the filters |
| New Tickets | status = `NEW` |
| Open Tickets | status category ∈ NEW, OPEN, WAITING (not RESOLVED / CLOSED / CANCELLED) |
| In Progress | status = `IN_PROGRESS` |
| Waiting | status category WAITING (`WAITING_CUSTOMER`, `WAITING_INTERNAL`) |
| Resolved / Closed | status = `RESOLVED` / `CLOSED` |
| Overdue | open ticket with `due_at` < now |
| Due date | set at creation as `created_at + resolution target hours` for the ticket priority (setting `service_targets`); can be changed by a manager. Tickets whose priority has no target get no automatic due date |
| First response time | `first_response_at − created_at`. `first_response_at` is the first customer-visible staff action: a manual status change or a customer-visible update (PUBLIC comment). Automatic transitions (e.g. NEW→ASSIGNED caused by assignment) and internal notes do not count |
| Resolution time | `resolved_at − created_at` for tickets currently RESOLVED or CLOSED (`closed_at` if closed without passing RESOLVED). Reopening clears `resolved_at`; it is set again on the next resolution |
| Target met % | share of tickets (with a target for their priority) whose first response / resolution time ≤ the target |
| Open ticket aging | `now − created_at` for open tickets, buckets 0–1, 1–3, 3–7, 7–14, 14–30, 30+ days |
| Volume by month | count by calendar month of `created_at` in Asia/Bangkok (last 12 months when no date filter) |
| Resolution by month | average resolution time grouped by month of resolution |
| Staff workload | per active staff member, based on the **current** assignee: assigned (all), active (open), waiting, resolved, closed, overdue; plus a row for unassigned open tickets |

## Service targets are configurable — not contractual SLAs

`Admin → Settings → service_targets` holds internal targets per priority (hours):

| Priority | First response (default) | Resolution (default) |
|----------|-------------------------|----------------------|
| URGENT | 2 | 24 |
| HIGH | 4 | 72 |
| NORMAL | 8 | 120 |
| LOW | 24 | 240 |

These defaults are **placeholders** and must be reviewed by BUC management before go-live.
They are measured in elapsed (calendar) hours; business-hours calendars are not modelled.
