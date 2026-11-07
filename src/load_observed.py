import json
from pathlib import Path

from build_db import connect

RAW = Path("data/raw/reittiloki")

TABLE = """
DROP TABLE IF EXISTS public.observed CASCADE;
CREATE TABLE public.observed (
  feed text NOT NULL,
  terminal_id text NOT NULL,
  service_date date NOT NULL,
  stop_id text NOT NULL,
  route_id text NOT NULL,
  direction int NOT NULL,          -- Reittiloki: 1/2 (GTFS uses 0/1)
  departure_time text NOT NULL,    -- service-day time, can pass 24:00
  planned_ts timestamptz NOT NULL,
  observed_ts timestamptz,         -- null = no observation
  delay_s int,                     -- positive = late
  loc text,                        -- how it was observed (GPS, ODO, ...)
  is_cancelled boolean NOT NULL,   -- raw flag, mostly TIS_ERROR
  cancellation_types text[]        -- null = none; a departure can have 2
);
"""


def rows(feeds):
    for f in sorted(RAW.glob("terminal_*.json")):
        terminal = f.name.split("_")[1]
        for d in json.loads(f.read_text(encoding="utf-8"))["data"]["departures"]:
            obs = d["observedDepartureTime"] or {}
            types = [c["cancellationType"] for c in d["cancellations"] or []]
            yield (feeds[d["departureDate"]], terminal, d["departureDate"], d["stopId"], d["routeId"],
                   d["direction"], d["departureTime"], d["plannedDepartureTime"]["departureDateTime"],
                   obs.get("departureDateTime"), obs.get("departureTimeDifference"), obs.get("loc"),
                   d["isCancelled"], types or None)


def main():
    with connect() as conn:
        feeds = {str(d): f for d, f in conn.execute("SELECT service_date, feed FROM public.study_dates")}
        conn.execute(TABLE)  # drop + recreate, so reruns give the same rows
        with conn.cursor().copy("COPY public.observed FROM STDIN") as copy:
            for r in rows(feeds):
                copy.write_row(r)
        conn.execute("ANALYZE public.observed")  # fresh table has no stats; without them 05 picks a nested loop (5+ min)
        for feed, date, n in conn.execute(
                "SELECT feed, service_date, count(*) FROM public.observed GROUP BY 1, 2 ORDER BY 2"):
            print(f"  observed {feed} {date}: {n:,} rows")
        # 05+ join observed to each feed's departures (build_db runs 00-04)
        for sql in sorted(Path("sql").glob("*.sql"))[5:]:
            for feed in ("halloween", "baseline"):
                conn.execute(f"SET search_path = {feed}, public")
                conn.execute(sql.read_text())
                print(f"  {feed}: ran {sql.name}")


if __name__ == "__main__":
    main()
