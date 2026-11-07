# Data sources

## Reittiloki (observed + planned departures)

Checked 6 Nov 2026. **Public, no login or API key needed.**

- **Endpoint:** `POST https://reittiloki.hsl.fi/server/graphql/`
- **Headers:** only `Content-Type: application/json`. The browser also sends cookies, including `transitlog-session`, but the same request without them returns byte-identical data. The default Python `urllib` User-Agent is accepted.
- **Query:** `departures(stopId: String, terminalId: String, date: Date!)`. Pass either `stopId` (one platform, e.g. `1020119`) or `terminalId` (a group of platforms, e.g. `1000003` Rautatientori). `date` is the **service date** `YYYY-MM-DD`.
- **Client:** [src/reittiloki_probe.py](../src/reittiloki_probe.py). It uses a trimmed version of the UI's query, keeping only the fields we use. Raw responses go to `data/raw/reittiloki/<terminal|stop>_<id>_<date>.json`.

### Response shape (one item of `data.departures`)

| Field | Example | Notes |
| --- | --- | --- |
| `stopId`, `routeId`, `direction` | `1020119`, `4600`, `1` | `routeId` is the internal HSL id (`1064` = line 64, `4600` = 600) |
| `dayType` | `La` | timetable type: seen `Pe` (Fri) and `La` (Sat) |
| `departureDate`, `departureTime`, `isNextDay` | `2026-10-31`, `24:04:00`, `true` | service-day time, which can go past 24:00 |
| `plannedDepartureTime.departureDateTime` | `2026-10-31T04:10:00.000+02:00` | **real local timestamp**, already converted past midnight |
| `observedDepartureTime` | `{departureDateTime, departureTimeDifference: 74, loc: "GPS"}` | `null` = no observation. Difference is in seconds; positive = late |
| `isCancelled`, `cancellations[]` | `true`, `[{cancellationType: "TIS_ERROR", ...}]` | see Findings: most are `TIS_ERROR` |
| `journey.uniqueVehicleId` | `0012/2412` | operator/vehicle |

### Findings

- **The service day runs 04:10 → ~05:00 the next day.** The 31 Oct service day covers 31 Oct 04:10 to 1 Nov 04:59. So 00:00–04:10 on 31 Oct comes from the **30 Oct** service date.
- Rautatientori terminal on 31 Oct: 1,032 departures, 999 observed (97%), 26 flagged `isCancelled` (mostly data errors, see below), 10 platforms, 43 routes. On 30 Oct: 1,325 departures, 1,283 observed, 39 cancelled.
- **Most "cancellations" are data errors.** On 31 Oct, of 26 `isCancelled` departures, 24 are `TIS_ERROR`, 1 is `BLOCK_FIRST_DEPARTURE_LATE` and 1 is `CANCEL_DEPARTURE`. On 30 Oct: 33 / 5 / 1. Don't count `isCancelled` as cancellations. Filter on `cancellationType`, and find out what `TIS_ERROR` means before using it.
- Stop `1020100` (H2019) returns 0 departures. It only serves 97xx regional routes, which Reittiloki doesn't seem to cover.
- Spot-checked 6 rows against the UI (terminal 1000003, 31 Oct): line 611 at 18:26, observed 18:26:14 ✓; line 600 at 18:30, observed 18:30:41 ✓; line 64 at 18:30, observed 18:30:11 ✓; line 78 at 18:30, observed 18:30:39 ✓; line 61 at 18:40 with no observation ✓; line 71 at 18:43 cancelled ✓.
- Retention is about 4 months (per HSL), so 31 Oct data should be cached before about late Feb 2027.

### Terms of use (checked 7 Nov 2026): **unclear**

- No terms page found that covers Reittiloki or the Transitlog server API specifically. The endpoint is public with no key or registration.
- HSL open data is CC BY 4.0 with attribution ([hsl.fi/en/opendata](https://hsl.fi/en/opendata)). The registration and API-key rules on [Digitransit terms](https://digitransit.fi/en/developers/apis/7-terms-of-use/) cover the Digitransit APIs, not Reittiloki.
- The UI is open source ([transitlog-ui](https://github.com/HSLdevcom/transitlog-ui), AGPL-3.0), which says nothing about API use.
- **Decision:** go ahead politely. Requests are sequential with about 1 s sleep between calls, results are cached so nothing is fetched twice, and the batch is one-off (~490 calls). If HSL objects, stop and ask.

### Pilot (7 Nov 2026)

3 terminals × 4 service dates in `data/raw/reittiloki/terminal_<id>_<date>.json`.

| Terminal | 16 Oct | 17 Oct | 30 Oct | 31 Oct | Observed | GTFS planned (16/17/30/31) |
| --- | --- | --- | --- | --- | --- | --- |
| 1000003 Rautatientori (central) | 1,306 | 1,032 | 1,325 | 1,032 | 97–98% | 1,305 / 1,032 / 1,325 / 1,032 |
| 4000006 Myyrmäki (suburban hub) | 1,242 | 1,038 | 1,266 | 1,038 | 92–95% | 1,189 / 997 / 1,213 / 997 |
| 1000111 Itäkeskus metro | 582 | 503 | 579 | 503 | 90–97% | 582 / 503 / 582 / 503 |

- **Night coverage is OK.** Each Friday file runs to about 05:00 Saturday (Rautatientori has ~198 departures after midnight). The metro stops around 00:01, so it adds nothing to the night signal.
- **Myyrmäki's +41/+53 is explained.** Reittiloki lists **arrival-only** terminal stops as departures. Route 4571 ends at stop 4150205, which GTFS has as `pickup_type = 1` (39 rows on 17 Oct). Route 7375 at 4150203 has no GTFS trips (2 rows). When joining to GTFS these rows are expected to be unmatched. Exclude or count them, don't treat them as missing.
- **Request time:** 2–4 s for bus terminals, 6–8 s for the metro (bigger response). Budget ~5 s + 1 s sleep → **~490 calls ≈ 45–50 min**.
- More cancellation types seen: `DEPARTURED_AFTER_NEXT_JOURNEY`, `LATE_DEPARTURE`. `TIS_ERROR` still dominates.
### Batch (7 Nov 2026)

`python src/reittiloki_probe.py batch data/raw/gtfs/mdb-865-202611010130.zip 2026-10-16 2026-10-17 2026-10-30 2026-10-31`, log in `data/raw/reittiloki/batch.log`. Took 19 min (~2.4 s/call incl. 1 s sleep), 0 failures.

| Service date | Departures | Observed | After midnight | Cancellation records (non-`TIS_ERROR`) |
| --- | --- | --- | --- | --- |
| 16 Oct (Fri) | 52,790 | 92.5% | 2,552 | 436 (134) |
| 17 Oct (Sat) | 41,637 | 91.7% | 2,553 | 369 (91) |
| 30 Oct (Fri) | 54,760 | 95.8% | 2,773 | 437 (124) |
| 31 Oct (Sat) | 41,680 | 94.4% | 2,735 | 434 (126) |

- 6 terminals return 0 departures on every date (2000210, 4000002, 4000003, 4000007, 6000201, 9600001). GTFS has 0 for them too.
- `cancellations(date)` needs `cancellationSearch: {}` or the server throws. It is network-wide (`routeId` like `100HA5` includes a variant suffix).

- **Coverage warning:** the 122 GTFS terminals hold only ~8.5% of window departures (bus 19k of 435k, tram 0 of 47k, ferry 0; metro and train almost fully). A terminal-only pull says little about trams or most buses.

## Mobility Database (archived GTFS)

Checked 6 Nov 2026. Free account, refresh token in `.env` as `MDB_REFRESH_TOKEN`.

- **Token:** `POST https://api.mobilitydatabase.org/v1/tokens` with `{"refresh_token": ...}`. This returns a short-lived `access_token`.
- **Snapshots:** `GET /v1/gtfs_feeds/mdb-865/datasets?limit=100` with `Authorization: Bearer <access_token>`, newest first. There's about one snapshot per night. Each covers about 3 days back to 2 months ahead.
- **Fields used:** `id`, `downloaded_at`, `service_date_range_start/end` (UTC, so 22:00Z or 21:00Z = Helsinki midnight), `zipped_folder_size_mb`, `hosted_url` (public, no token), `hash` (sha256).
- **Selection:** for each study date, use the newest snapshot that covers it in Helsinki dates and isn't broken (has a range, ≥ 10 MB; the 27 Oct snapshot is 0.62 MB with no range).
- **Client:** [src/mdb.py](../src/mdb.py). Run `python src/mdb.py <dates...>` or `--check`. The sha256 is checked against MDB, and each run is logged in `data/raw/gtfs/manifest.csv`.

| Study dates | Snapshot | Service range |
| --- | --- | --- |
| 30 Oct – 1 Nov (Halloween) | `mdb-865-202611010130` | 30 Oct – 28 Dec |
| 16–17 Oct (baseline) | `mdb-865-202610180116` | 16 Oct – 14 Dec |

## Licence

HSL data is CC BY 4.0. Attribute "HSL" on the dashboard.
