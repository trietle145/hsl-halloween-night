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
Phases 0–2 (done, signed off 6 Nov)

Task 6 terms + pilot ── Task 7 batch pull ── Task 8 load + join ── Task 9 metrics ── Checkpoint 3
                                                                       │                 │
                                                                       └─ Task 11       Task 10 Tableau
                                                                                          │
                                                          Checkpoint 4 ── Task 5 README ── Task 12 publish ── Task 13 case study
```
Start with Task 6 → 7 because of data retention.

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

### Task 3: GTFS to Postgres/PostGIS for the study window (M): done 6 Nov
**Result:** `python src/build_db.py <zip> <halloween|baseline>` loads a feed into its own schema and runs `sql/*.sql` in order. The `departures` table has about 512k rows per feed. GTFS planned departures from the Rautatientori terminal on the 31 Oct service day = 1,032, **exactly matching Reittiloki**. All Saints' Day shows up as 11 `_La` services removed and replaced by date-only `_PY` (holiday) services on routes 13, 13H, 19, 24, 24X, 25, 37, 41, 42, H and the U train. There are no U-line buses in HSL GTFS. Total departures: Halloween 511,897 vs baseline 511,709, almost the same, so the story is in the details.

Run Postgres with PostGIS, either from the Windows installer with Stack Builder or in Docker. Load `stops`, `routes`, `trips`, `stop_times`, `calendar`, `calendar_dates` and `shapes` into Postgres, building stop points and route shapes as PostGIS geometries. Work out which service_ids are active on each study date. Convert GTFS times past 24:00, such as 25:30:00, into real timestamps on 1 Nov. The window spans **three service days**: 30 Oct trips with 24+ hour times cover 00:00–~04:30 on 31 Oct (confirmed in Reittiloki, where the service day runs about 04:10 → 05:00 next day). The 00:00–04:00 tail on 1 Nov can come from two service days: 31 Oct trips with 24+ hour times, and 1 Nov trips with early times. Build departures for both service dates, then filter by real timestamp. The baseline needs the same treatment. Load `stop_times` with `COPY`, not row-by-row inserts.

**Acceptance**
- [x] A `departures` table (date, stop_id, route, mode, trip_id, timestamp) exists, filtered to the study window.
- [x] A trip at 25:30 on 31 Oct shows up as 01:30 on 1 Nov (route 7H at 25:32 → 1 Nov 01:32).
- [x] ~~U-line trips use the Sunday service on 31 Oct.~~ No U-line buses in the feed. Instead, 31 Oct uses `_PY` holiday services for 11 routes (13,906 departures in the window).
- [x] Departures from the 1 Nov service day that fall before 04:00 are included (only 1 does; 30 Oct contributes 33,859 to the early hours of 31 Oct).

**Verify:** ~~The departure count for one stop and hour matches the HSL timetable.~~ Matched Reittiloki instead: 1,032 = 1,032 at terminal 1000003.
**Files:** `src/build_db.py`, `sql/00_study_dates.sql`, `sql/01_geometry.sql`, `sql/02_services.sql`, `sql/03_departures.sql`

### Task 4: First two Tableau views (M): done 6 Nov (saved as `tableau/hsl.twb`; publishing is Task 12)
**Result:** `python src/export.py` writes `data/exports/hsl_hourly.csv`, `hsl_stop_routes.csv` and `hsl_route_lines.geojson`. The dashboard (route map + hourly stacked bars + 3 BANs, Saturday/Routes parameters, click-a-route filter) was built in Tableau Public. Stops layer skipped for now.
**Finding:** planned service is almost identical: Halloween 511,897 vs ordinary Saturday 511,709 (+0.04%), with only 22 of 266 routes changed. Of the 11 `_PY` (All Saints') routes, 8 have identical trip counts. The only real addition is Bus 24X (+270). The biggest differences are ordinary timetable changes (Train K +1,211, Bus 245A→245, Bus 712 gone). **The story moves to observed service (Phase 4).**

Export small CSV or Hyper extracts and build two views:
- a **route and stop map** filtered by mode
- **departures by hour and mode** for 31 Oct

Clicking a route should filter the chart.

**Acceptance**
- [x] The dashboard opens with both views linked.
- [x] Each extract is under about 50 MB (largest 3.4 MB).
- [x] The time axis runs from 00:00 on 31 Oct to 04:00 on 1 Nov, in local time.

**Verify:** Compare the dashboard's hourly totals with a SQL query.
**Files:** `sql/04_exports.sql`, `src/export.py`, `tableau/` (workbook)

### Checkpoint 2: signed off 6 Nov
- [x] Slice works end to end: raw APIs → Postgres → exports → Tableau dashboard. The repeatability proof (README + clean rebuild) moved to Task 5 in Phase 4.
- [x] Review the slice before expanding it. **Decision (6 Nov):** planned service barely differs, so the story is observed reliability. Phase 3 is now observed service. The old "expand the planned analysis" ideas are in the backlog.

---

## Phase 3: Observed service (concrete; the story is here)

**Question:** was Halloween night less reliable than an ordinary Saturday night, beyond the planned timetable?

**Early signal (6 Nov):** at Rautatientori, after-midnight departures on Halloween night were more than 3 min late 14.1% of the time vs 2.6% on 17 Oct (p90 +233 s vs +86 s). Daytime is similar. One origin terminal with n ≈ 200, so this needs checking at scale.

**Data plan (agreed 6 Nov):** Reittiloki `departures(terminalId, date)` for all 122 terminals (GTFS `location_type = 1`) × service dates 30 + 31 Oct and 16 + 17 Oct = about 490 requests. `cancellations(date)` gives the day's cancellations in one call. A full-journey query (`journeys`) exists if terminals turn out to be too origin-heavy.

### Task 6: Terms check and pilot pull (S): done 7 Nov
**Result:** terms unclear (no Reittiloki-specific terms), proceeding politely (1 req/s, cached). Pilot 1000003 / 4000006 / 1000111 × 4 dates: counts match GTFS within 0–3 except arrival-only terminal stops (Myyrmäki +41). ~5 s/call. Terminals cover only ~8.5% of departures (no trams). Details in `docs/sources.md`.
Check HSL's terms for scripted Reittiloki use. Pull 3 terminals (one central, one suburban hub, one metro) × 4 dates with the existing probe, and check that the 30 Oct service date covers Sat 00:00–04:30.

**Acceptance**
- [x] Terms outcome recorded in `docs/sources.md` (allowed / unclear / not allowed) with a link.
- [x] 12 raw files saved. Each returns planned + observed, and 30 Oct contains departures after midnight.
- [x] Request timing noted (seconds per call), to size the batch.

**Verify:** for one pilot terminal, planned count per service date = GTFS planned count (as with Rautatientori: 1,032 = 1,032).
**Files:** `docs/sources.md`
**Dependencies:** none. **Blocks** Task 7 if the terms say no.

### Task 7: Batch pull, cached and rate-limited (S): done 7 Nov
**Result:** `python src/reittiloki_probe.py batch <gtfs zip> <dates...>`. 488 terminal files + 4 cancellation files, 0 failures, rerun fetches 0. ~2.4 s/call (19 min). Observed 92–96% per date. 6 terminals are empty on every date and have 0 GTFS departures too. Spot-check against the UI still to do.
Add a batch mode to `src/reittiloki_probe.py`: read terminal IDs from GTFS, loop over the 4 service dates, skip files that already exist, sleep ~1 s between calls, retry once on errors, and log failures.

**Acceptance**
- [x] About 488 raw files in `data/raw/reittiloki/`. Failures listed, then retried successfully.
- [x] Rerunning makes 0 requests (everything cached).
- [x] `cancellations` saved for the 4 dates.

**Verify:** file count = terminals × dates. Spot-check 2 files against the Reittiloki UI.
**Files:** `src/reittiloki_probe.py`
**Dependencies:** Task 6. **Do this early:** retention is about 4 months, so 16–17 Oct data expires around mid-Feb 2027.

### Task 8: Load observed data and join to planned (M): done 7 Nov
**Result:** `python src/load_observed.py` (2.5 s) loads `public.observed` (190,867 raw rows) and runs `sql/05_observed.sql` per feed. Match rate: Halloween 98.6% (42,256 departures), baseline 96.9% (41,043). Fixes needed: dedupe one row per planned departure (Reittiloki lists each vehicle; ~2–3k multi-vehicle departures), metro route ids `31M1 7` → `31M1`, direction 1/2 → 0/1, timestamptz → local, match on terminal not stop (platform moves), prefer exact stop when a trip passes 2 platforms in one minute, `ANALYZE` after load. Unmatched: U-lines 7xxx (~160/feed, not in GTFS), terminal 9000001 route 9976, Hakaniemi baseline (847: GTFS snapshot has those buses 1 min later at another platform). Delay comes from Reittiloki itself, so unmatched rows still have delay, only mode is missing. Rautatientori after midnight: 15.3% vs 3.0% > 3 min late (n 163 / 166).
Load the raw JSON into `public.observed` (feed, stop_id, route_id, direction, planned_ts, observed_ts, delay_s, cancellation_type). Join it to each feed's `departures` on stop + route + direction + planned timestamp, restricted to the study window.

**Acceptance**
- [x] ≥ 95% of in-window Reittiloki rows match a planned GTFS departure. Unmatched rows are counted and explained.
- [x] `observed_departures` exists per feed, with `is_observed`, `delay_s` and `real_cancel` (cancellationType ≠ `TIS_ERROR`).
- [x] The loader is idempotent (a rerun gives the same row counts).

**Verify:** match rate per terminal. Any terminal below 90% is investigated (route ID mapping, time zones, `isNextDay`).
**Files:** `src/load_observed.py`, `sql/05_observed.sql`
**Dependencies:** Task 7 (can start on the pilot files from Task 6).

### Task 9: Reliability metrics (S): done 7 Nov
**Result:** views `reliability_base` + `reliability` (hour × mode) in `sql/06_reliability.sql`; cross-feed checks in `sql/analysis/checks.sql`. Rautatientori after midnight 15.3% vs 3.0% (earlier 14.1 vs 2.6 was before dedupe). **Network-wide, bus only:** buses after midnight 35.9% vs 13.0% > 3 min late (median +60–100 s), evening 17.0 vs 11.2, day 11.2 vs 8.3, Fri-night early hours 23.0 vs 13.6. 12 of 13 terminals with n ≥ 30 are worse, 11 by > 5 pp; without Rautatientori + Hakaniemi still 23.2% vs 9.2%. Trains about the same (hours 26–27 worse, small n); metro has no night service; trams not covered. **Coverage caveat:** Hakaniemi baseline after midnight only 43% observed (146/337) vs 94% on Halloween; everything else 96–97% on both nights. Weather: both nights dry (FMI), ruled out.
A view with reliability per feed × window hour × mode: n planned, % observed, median and p90 delay, % more than 3 min late, and real cancellations. Plus a Halloween-minus-ordinary comparison.

**Acceptance**
- [x] SQL reproduces the Rautatientori signal (14.1% vs 2.6% after midnight) when filtered to terminal 1000003.
- [x] Every cell carries its n. Cells with n < 30 are flagged.
- [x] One answer: is the after-midnight difference present across terminals, or driven by one or two?

**Verify:** recompute one cell by hand from raw JSON in Python.
**Files:** `sql/06_reliability.sql`
**Dependencies:** Task 8

### Checkpoint 3
- [ ] Is the late-night effect real across the network? Decide the headline with the user.
- [ ] Coverage is good enough (% observed is similar on both dates, so missing data isn't driving the result).
- [x] Check FMI weather for both nights (a possible confounder). **Done 9 Nov:** both nights dry (0.0 mm), Halloween mild and still; not a confounder. `src/fmi_weather.py`.

### Task 10: Reliability views in Tableau (M)
Export the reliability views. Build a second dashboard or a new section: % late per hour, Halloween vs ordinary on one `window_hour` axis (two series, one axis); a terminal map coloured by change in % late (diverging, grey midpoint); and a coverage note.

**Acceptance**
- [ ] The headline from Checkpoint 3 is readable in under 10 seconds.
- [ ] The Saturday/Routes parameters still work, or are deliberately left off this view.
- [ ] Colours validated (diverging pair + grey midpoint), with a legend present.

**Verify:** dashboard numbers = SQL view numbers for 3 cells.
**Files:** `sql/04_exports.sql`, `src/export.py`, `tableau/hsl.twb`
**Dependencies:** Checkpoint 3

### Task 11: Which routes drive it (S, optional)
Top routes by increase in % late after midnight (n ≥ 30 each date), as a ranked bar chart or table.

**Acceptance**
- [ ] A top-10 list with n, both dates' % late and the difference.
- [ ] It shows whether night buses (N-routes) account for most of the effect.

**Files:** `sql/06_reliability.sql`, `tableau/hsl.twb`
**Dependencies:** Task 9

### Checkpoint 4
- [ ] The dashboard tells planned (same) → observed (different) in order.
- [ ] Review with the user before packaging.

---

## Phase 4: Package

### Task 5: README and clean rebuild (S) · moved here from Phase 2 on 6 Nov
Write a short `README.md` covering setup (venv, `.env`, Docker), the pipeline commands in order, and "run `export.py` before opening `tableau/hsl.twb`". Prove it works by rebuilding from an empty database.

**Acceptance**
- [ ] `docker compose down -v`, then following the README from top to bottom, rebuilds both schemas and the exports.
- [ ] The exports give the same totals as before (511,897 / 511,709).
- [ ] `tableau/hsl.twb` opens and shows the same numbers.

**Verify:** compare `hsl_hourly.csv` totals before and after the rebuild.
**Files:** `README.md`

### Task 12: Publish (S)
Publish to Tableau Public, with HSL CC BY 4.0 attribution and the Mobility Database credit in the footer. Add the link to `docs/sources.md` and `README.md`.

**Acceptance**
- [ ] The public URL loads without the local data (extracts embedded).
- [ ] Attribution is visible on every dashboard.

**Files:** `README.md`, `docs/sources.md`, `tableau/hsl.twb`
**Dependencies:** Checkpoint 4, Task 5

### Task 13: Case study write-up (S)
A one-page case study: question, sources, method (three service days, matching, TIS_ERROR handling), findings (planned same, observed different), and limits (terminals only, no transfers, observation coverage, one Saturday each).

**Acceptance**
- [ ] Every number in it traces to a query or file.
- [ ] Limits are stated plainly.

**Files:** `docs/case_study.md`
**Dependencies:** Task 12

### Checkpoint: Complete
- [ ] All acceptance criteria met. Published link works.

---

## Backlog (not planned; add only if the story needs it)
- Planned service gaps / headways per stop. Planned service barely differs, so this is low value.
- Late-night reachability from an origin (direct routes only).
- Stops layer on the route map.

---

## Risks

| Risk | Impact | Mitigation |
| --- | --- | --- |
| Reittiloki needs a login or blocks scripted calls | High | Test in Task 1 first. If it fails, fall back to scheduled-only. |
| Reittiloki terms of use forbid bulk scripted pulls | Medium | Check in Task 1. Keep Phase 4 pulls small, rate-limited and cached. |
| Reittiloki retention (about 4 months) runs out before Phase 4 | Medium | Pull and cache the raw JSON for the chosen stops soon after Task 1, before the analysis is finished. |
| GTFS is too big for Tableau | Medium | Aggregate in Postgres and export only small tables or extracts. |
| The comparison shows little difference | ~~Low~~ Happened (planned) | Planned service is the same. The story moved to observed reliability (Phase 3). |
| Terminal departures are origin-heavy, so delays look small | Medium | Compare like with like (same terminals on both dates). If needed, add `journeys` for a few night routes to see mid-route delay. |
| One Saturday each is a tiny sample; weather or events could explain the difference | Medium | Report n and coverage. Check FMI weather for both nights. Phrase findings as "on this night", not "Halloween causes". |
| Reittiloki retention: 16–17 Oct expires about mid-Feb 2027 | High | Task 7 runs before any analysis. Raw JSON is cached. |
