import argparse
import json
import urllib.request
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

#put the query value into json
def fetch_departures(date, place_id, is_stop=False):
    variables = {"date": date, "stopId" if is_stop else "terminalId": place_id}
    body = json.dumps({"query": QUERY, "variables": variables}).encode()
    req = urllib.request.Request(URL, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as resp:  # raises on HTTP errors
        data = json.load(resp)
    if "errors" in data:  # GraphQL reports query problems with HTTP 200
        raise RuntimeError(data["errors"])
    return data

#just read command line and read out stuff
def main():
    p = argparse.ArgumentParser()
    p.add_argument("date", help="service date, YYYY-MM-DD")
    p.add_argument("id", help="terminal id (e.g. 1000003) or stop id with --stop")
    p.add_argument("--stop", action="store_true", help="id is a single stop, not a terminal")
    args = p.parse_args()

    data = fetch_departures(args.date, args.id, args.stop)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / f"{'stop' if args.stop else 'terminal'}_{args.id}_{args.date}.json"
    out.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

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
