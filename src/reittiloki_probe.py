import argparse
import csv
import io
import json
import sys
import time
import urllib.request
import zipfile
from pathlib import Path

URL = "https://reittiloki.hsl.fi/server/graphql/"
OUT_DIR = Path("data/raw/reittiloki")

#only need these fields
QUERY = """
query departures($stopId: String, $terminalId: String, $date: Date!) {
  departures(stopId: $stopId, terminalId: $terminalId, date: $date) {
    stopId routeId direction dayType extraDeparture
    departureDate departureTime isNextDay isCancelled
    cancellations { cancellationType cancellationEffect title }
    journey { uniqueVehicleId }
    plannedDepartureTime { departureDateTime }
    observedDepartureTime { departureDateTime departureTimeDifference loc }
  }
}
"""

# server crashes without the empty cancellationSearch object
CANCEL_QUERY = """
query cancellations($date: Date) {
  cancellations(date: $date, cancellationSearch: {}) {
    routeId direction departureDate journeyStartTime title category subCategory
    isCancelled cancellationType cancellationEffect lastModifiedDateTime
  }
}
"""

#put the query value into json
def fetch_departures(date, place_id, is_stop=False):
    return post(QUERY, {"date": date, "stopId" if is_stop else "terminalId": place_id})


def post(query, variables):
    body = json.dumps({"query": query, "variables": variables}).encode()
    req = urllib.request.Request(URL, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as resp:  # raises on HTTP errors
        data = json.load(resp)
    if "errors" in data:  # GraphQL reports query problems with HTTP 200
        raise RuntimeError(data["errors"])
    return data


def save(path, data):
    tmp = path.with_suffix(".tmp")  # write then rename, so a killed run never leaves a half file that gets skipped
    tmp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)


def batch(gtfs_zip, dates):
    with zipfile.ZipFile(gtfs_zip) as z, z.open("stops.txt") as f:
        terminals = [r["stop_id"] for r in csv.DictReader(io.TextIOWrapper(f, "utf-8-sig"))
                     if r["location_type"] == "1"]
    jobs = [(OUT_DIR / f"terminal_{t}_{d}.json", QUERY, {"terminalId": t, "date": d})
            for d in dates for t in terminals]
    jobs += [(OUT_DIR / f"cancellations_{d}.json", CANCEL_QUERY, {"date": d}) for d in dates]
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    todo = [j for j in jobs if not j[0].exists()]  # cached files are never re-fetched
    print(f"{len(terminals)} terminals x {len(dates)} dates + cancellations: "
          f"{len(jobs)} files, {len(todo)} to fetch", flush=True)
    failed = []
    for i, (path, query, variables) in enumerate(todo, 1):
        for attempt in (1, 2):
            try:
                save(path, post(query, variables))
                print(f"[{i}/{len(todo)}] {path.name}", flush=True)
                break
            except Exception as e:
                print(f"[{i}/{len(todo)}] {path.name} attempt {attempt} failed: {e}", flush=True)
                if attempt == 2:
                    failed.append(path.name)
                time.sleep(5)
        time.sleep(1)  # be polite: one request at a time, ~1/s
    print(f"done, {len(failed)} failed (rerun to retry): {failed}")


#just read command line and read out stuff
def main():
    if len(sys.argv) > 1 and sys.argv[1] == "batch":
        return batch(sys.argv[2], sys.argv[3:])  # batch <gtfs zip> <dates...>
    p = argparse.ArgumentParser()
    p.add_argument("date", help="service date, YYYY-MM-DD")
    p.add_argument("id", help="terminal id (e.g. 1000003) or stop id with --stop")
    p.add_argument("--stop", action="store_true", help="id is a single stop, not a terminal")
    args = p.parse_args()

    data = fetch_departures(args.date, args.id, args.stop)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / f"{'stop' if args.stop else 'terminal'}_{args.id}_{args.date}.json"
    save(out, data)

    deps = data["data"]["departures"]
    observed = [d for d in deps if d["observedDepartureTime"]]
    cancelled = [d for d in deps if d["isCancelled"]]
    print(f"saved {out}")
    print(f"{len(deps)} departures, {len(observed)} observed, {len(cancelled)} cancelled")
    for d in deps[:5]:
        obs = d["observedDepartureTime"]
        late = f"{obs['departureTimeDifference']:+d}s" if obs else "no observation"
        print(f"  {d['routeId']}/{d['direction']}  stop {d['stopId']}  "
              f"planned {d['plannedDepartureTime']['departureDateTime'][11:19]}  {late}")


if __name__ == "__main__":
    main()
