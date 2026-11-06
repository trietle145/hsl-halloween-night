# Plan: Halloween on HSL dashboard

*Rough plan, 6 Nov 2026. Phases 1–2 are concrete. Phases 3–5 are rough and will be reworked as we go.*

## Overview

This is a retrospective Tableau dashboard of HSL service on Halloween, Saturday 31 Oct 2026, covering 00:00 on 31 Oct to about 04:00 on 1 Nov. It compares scheduled service with observed service. Data comes from two APIs:
- the **Mobility Database API**, for archived GTFS schedules
- the **Reittiloki GraphQL API**, for observed departures

The processing is done in SQL with PostgreSQL + PostGIS. The output is Tableau.

## Decisions so far

- **Topic.** The project is about Halloween. 31 Oct was also All Saints' Day, so U-line buses ran their Sunday timetable and there were extra services to Hietaniemi. The dashboard notes this as context.
- **Dropped.** City bikes (2026 data isn't published), GTFS-RT (live only) and any local router.
- **Reachability.** Direct routes only, with no transfers, labelled as such.
- **Baseline.** Saturday 17 Oct. It is already in the past, so it has observed data, and it's well inside Reittiloki's retention. Not 24 Oct, because of the clock change (25 Oct). 7/14 Nov hadn't happened yet when this was decided.
- **Database.** PostgreSQL + PostGIS, chosen because it is industry-standard, free, has a native Tableau connector and handles geometry. The unzipped GTFS is about 1 GB, so Postgres reduces it to small tables before Tableau. Tableau Public needs extracts, not a live connection.

## Dependency graph

```
Reittiloki access test ──┐
                         ├─> Halloween slice (ingest → SQL → 2 Tableau views)
MDB API client ──────────┘          │
                                    ├─> more views (gaps, late-night, comparison)
                                    ├─> observed vs planned
                                    └─> case study write-up
```

---

## Phase 0: Environment (done 6 Nov)

- Python 3.13 venv in `.venv/` with `requirements.txt` (`psycopg[binary]`). Tasks 1–2 use the stdlib only.
- Postgres 17 + PostGIS 3.5 in Docker: `docker compose up -d`. Settings come from `.env` (copied from `.env.example`).
- `.gitignore` covers `.env`, `.venv/`, `data/` and `CLAUDE.md`.

---

## Phase 1: Prove access (concrete, do first)

### Task 1: Reittiloki access test (S): done 6 Nov
**Result:** public, no login. Planned + observed both available (97% observed at Rautatientori on 31 Oct). Details in `docs/sources.md`. Spot-checked 6 departures against the UI, all match. Still open: check terms of use.

Find out whether the public Reittiloki GraphQL endpoint returns observed departures for 31 Oct without logging in. This decides whether the case study can be "planned vs observed" or only "scheduled".

To do it, open reittiloki.hsl.fi, load one central stop (for example Rautatientori) for 31.10.2026, and copy the GraphQL request from the browser's Network tab. Replay it with curl first, removing headers until it breaks, to find the minimum it needs. Then replay it from a small Python script (stdlib `urllib`). Also check Reittiloki's terms of use for scripted access.

**Acceptance**
- [x] The script returns departures for one stop on 31 Oct with both planned and observed times, or the failure is documented (login required, empty result or error).
- [x] The endpoint URL, any required headers and the response shape are noted in `docs/sources.md`.
- [x] The raw JSON is saved to `data/raw/reittiloki/`.

**Verify:** Spot-check 3 departures in the script output against the Reittiloki UI.
**Files:** `src/reittiloki_probe.py`, `docs/sources.md`

### Task 2: Mobility Database API client (S–M): done 6 Nov
**Result:** one snapshot covers 30 Oct–1 Nov (`mdb-865-202611010130`), another covers 16–17 Oct (`mdb-865-202610180116`). Run with `python src/mdb.py 2026-10-30 2026-10-31 2026-11-01 2026-10-16 2026-10-17`. Details in `docs/sources.md`.

Exchange the refresh token for an access token, list the datasets for `mdb-865`, and pick the snapshot whose service date range covers each study date. Reject any snapshot that looks broken: less than about 10 MB, or with no service range (the 27 Oct snapshot is one). Download the chosen snapshot and log its dataset ID and hash.

**Acceptance**
- [x] `python src/mdb.py 2026-10-31` downloads a valid snapshot covering that date and writes `data/raw/gtfs/<dataset_id>.zip`.
- [x] The comparison date gets its own snapshot through the same command.
- [x] The refresh token is read from `.env`, which is gitignored and never committed.
- [x] `data/raw/gtfs/manifest.csv` records the date, dataset_id, download time, service range, size and sha256.

**Verify:** An assert-based self-check shows that the selection logic picks the right snapshot from a hard-coded sample list, and that it rejects the broken one.
**Files:** `src/mdb.py`, `.env.example`, `.gitignore`

### Checkpoint 1
- [x] Both API results are known.
- [x] We decide whether this is **scheduled-only** or **planned vs observed**, and whether the plan needs to change. **Planned vs observed.** Reittiloki is public with 97% observation coverage. The window needs three service days (30 Oct–1 Nov).

---

## Phase 2: One complete slice (concrete)

### Task 3: GTFS to Postgres/PostGIS for the study window (M)
Run Postgres with PostGIS, either from the Windows installer with Stack Builder or in Docker. Load `stops`, `routes`, `trips`, `stop_times`, `calendar`, `calendar_dates` and `shapes` into Postgres, building stop points and route shapes as PostGIS geometries. Work out which service_ids are active on each study date. Convert GTFS times past 24:00, such as 25:30:00, into real timestamps on 1 Nov. The window spans **three service days**: 30 Oct trips with 24+ hour times cover 00:00–~04:30 on 31 Oct (confirmed in Reittiloki, where the service day runs about 04:10 → 05:00 next day). The 00:00–04:00 tail on 1 Nov can come from two service days: 31 Oct trips with 24+ hour times, and 1 Nov trips with early times. Build departures for both service dates, then filter by real timestamp. The baseline needs the same treatment. Load `stop_times` with `COPY`, not row-by-row inserts.

**Acceptance**
- [ ] A `departures` table (date, stop_id, route, mode, trip_id, timestamp) exists, filtered to the study window.
- [ ] A trip at 25:30 on 31 Oct shows up as 01:30 on 1 Nov.
- [ ] U-line trips use the Sunday service on 31 Oct.
- [ ] Departures from the 1 Nov service day that fall before 04:00 are included.

**Verify:** The departure count for one stop and hour matches the HSL timetable.
**Files:** `sql/00_schema.sql`, `sql/01_load.sql`, `sql/02_departures.sql`, `src/build_db.py`, `.env` (DB connection settings)

### Task 4: First two Tableau views (M)
Export small CSV or Hyper extracts and build two views:
- a **route and stop map** filtered by mode
- **departures by hour and mode** for 31 Oct

Clicking a route should filter the chart.

**Acceptance**
- [ ] The dashboard opens with both views linked.
- [ ] Each extract is under about 50 MB.
- [ ] The time axis runs from 00:00 on 31 Oct to 04:00 on 1 Nov, in local time.

**Verify:** Compare the dashboard's hourly totals with a SQL query.
**Files:** `sql/03_exports.sql`, `tableau/halloween.twb`

### Checkpoint 2
- [ ] Running from raw data to dashboard works end to end, repeatably, with one command or a short README.
- [ ] Review the slice before expanding it.

---

## Phase 3: Expand the analysis (rough)

- **Service gaps:** headways per stop, route and direction, with the longest evening gaps.
- **Late-night options:** direct routes from the origin, the last departure to each destination, and a reachable-without-transfers layer on the map.
- **Comparison Saturday:** a side-by-side view that highlights the U-line and Hietaniemi differences.
- **Open questions:** the exact origin stop, the destination list, and how headway is defined.

## Phase 4: Observed service (rough; Task 1 worked, so this is on)

- Pull both service dates for each study day (for example, 30 + 31 Oct for Halloween), then filter by `plannedDepartureTime.departureDateTime`.
- `isCancelled` is mostly `TIS_ERROR` (data errors). Use `cancellationType` and don't count raw `isCancelled`.
- Run batched Reittiloki pulls for the chosen stops and routes on both dates, with rate limiting and cached raw JSON.
- Join observed departures to planned departures, then build delay and cancellation views.
- Add a coverage view that shows what share of planned departures have an observation, so gaps in the data are visible.
- Optionally, add FMI weather as context.

## Phase 5: Package (rough)

- Publish to Tableau Public.
- Write a short case study covering the question, sources, method, findings and limits, including the All Saints' note, no transfers, and observed-data coverage.
- Add HSL CC BY 4.0 attribution.

---

## Risks

| Risk | Impact | Mitigation |
| --- | --- | --- |
| Reittiloki needs a login or blocks scripted calls | High | Test in Task 1 first. If it fails, fall back to scheduled-only. |
| Reittiloki terms of use forbid bulk scripted pulls | Medium | Check in Task 1. Keep Phase 4 pulls small, rate-limited and cached. |
| Reittiloki retention (about 4 months) runs out before Phase 4 | Medium | Pull and cache the raw JSON for the chosen stops soon after Task 1, before the analysis is finished. |
| GTFS is too big for Tableau | Medium | Aggregate in Postgres and export only small tables or extracts. |
| The comparison shows little difference | Low | The holiday exceptions and observed delays carry the story. |
