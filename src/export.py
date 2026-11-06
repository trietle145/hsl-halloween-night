import csv
import json
from pathlib import Path

from build_db import connect

FEEDS = ["halloween", "baseline"]
OUT = Path("data/exports")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    with connect() as conn:
        for view in ["export_hourly", "export_stop_routes"]:
            path = OUT / f"hsl_{view.removeprefix('export_')}.csv"
            with open(path, "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f, quoting=csv.QUOTE_NONNUMERIC)
                for i, feed in enumerate(FEEDS):
                    cur = conn.execute(f"SELECT * FROM {feed}.{view}")
                    if i == 0:
                        w.writerow(["feed"] + [c.name for c in cur.description])
                    w.writerows([feed, *row] for row in cur)
            print(f"{path}: {path.stat().st_size / 1e6:.1f} MB")

        features = []
        for feed in FEEDS:
            cur = conn.execute(f"SELECT route, mode_group, timetable, direction_id, shape_id, departures, geojson FROM {feed}.export_route_lines")
            for route, mode, timetable, direction, shape, deps, geom in cur:
                features.append({"type": "Feature", "geometry": json.loads(geom),
                                 "properties": {"feed": feed, "route": route, "mode_group": mode, "timetable": timetable,
                                                "direction_id": direction, "shape_id": shape, "departures": deps}})
        path = OUT / "hsl_route_lines.geojson"
        path.write_text(json.dumps({"type": "FeatureCollection", "features": features}), encoding="utf-8")
        print(f"{path}: {path.stat().st_size / 1e6:.1f} MB, {len(features)} lines")


if __name__ == "__main__":
    main()
