import argparse
import csv
import hashlib
import json
import shutil
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

API = "https://api.mobilitydatabase.org/v1"
FEED = "mdb-865"
OUT_DIR = Path("data/raw/gtfs")
MANIFEST = OUT_DIR / "manifest.csv"
HELSINKI = ZoneInfo("Europe/Helsinki")
MIN_SIZE_MB = 10


def local_date(utc_iso):
    #'2026-10-29T22:00:00Z' -> date(2026, 10, 30), the date in Helsinki
    return datetime.fromisoformat(utc_iso).astimezone(HELSINKI).date()


def pick_snapshot(datasets, study_date):
    #return best snapshot
    good = []
    for ds in datasets:
        if ds["service_date_range_start"] is not None and ds["zipped_folder_size_mb"] >= MIN_SIZE_MB:
            if local_date(ds["service_date_range_start"]) <= study_date <= local_date(ds["service_date_range_end"]):
                good.append(ds)
    if not good:
        return None
    return max(good, key=lambda ds: ds["downloaded_at"])["id"]



def self_check():
    sample = [  # real values from the API, newest first, plus one fake broken snapshot
        {"id": "fake-tiny", "downloaded_at": "2026-11-07T00:00:00Z", "zipped_folder_size_mb": 0.5,
         "service_date_range_start": "2026-10-01T21:00:00Z", "service_date_range_end": "2027-01-01T21:59:00Z"},
        {"id": "mdb-865-202611040147", "downloaded_at": "2026-11-04T01:48:05Z", "zipped_folder_size_mb": 70.88,
         "service_date_range_start": "2026-11-01T22:00:00Z", "service_date_range_end": "2026-12-31T21:59:00Z"},
        {"id": "mdb-865-202611010130", "downloaded_at": "2026-11-01T01:31:28Z", "zipped_folder_size_mb": 72.48,
         "service_date_range_start": "2026-10-29T22:00:00Z", "service_date_range_end": "2026-12-28T21:59:00Z"},
        {"id": "mdb-865-202610310131", "downloaded_at": "2026-10-31T01:31:48Z", "zipped_folder_size_mb": 72.42,
         "service_date_range_start": "2026-10-28T22:00:00Z", "service_date_range_end": "2026-12-27T21:59:00Z"},
        {"id": "mdb-865-202610270118", "downloaded_at": "2026-10-27T01:18:36Z", "zipped_folder_size_mb": 0.62,
         "service_date_range_start": None, "service_date_range_end": None},
        {"id": "mdb-865-202610180116", "downloaded_at": "2026-10-18T01:16:49Z", "zipped_folder_size_mb": 68.83,
         "service_date_range_start": "2026-10-15T21:00:00Z", "service_date_range_end": "2026-12-14T21:59:00Z"},
    ]
    assert local_date("2026-10-29T22:00:00Z") == date(2026, 10, 30)
    assert pick_snapshot(sample, date(2026, 10, 31)) == "mdb-865-202611010130"  # latest that covers it
    assert pick_snapshot(sample, date(2026, 10, 29)) == "mdb-865-202610310131"  # 202611010130 starts 30 Oct in Helsinki
    assert pick_snapshot(sample, date(2026, 10, 17)) == "mdb-865-202610180116"
    assert pick_snapshot(sample, date(2026, 10, 1)) is None                     # only fake-tiny "covers" it
    assert pick_snapshot(sample, date(2027, 6, 1)) is None
    print("self-check ok")


def access_token():
    refresh = next(line.split("=", 1)[1].strip() for line in open(".env") if line.startswith("MDB_REFRESH_TOKEN="))
    req = urllib.request.Request(f"{API}/tokens", data=json.dumps({"refresh_token": refresh}).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)["access_token"]


def list_datasets(token):
    #newest 100 snapshots (~3 months back); add offset paging for older study dates
    req = urllib.request.Request(f"{API}/gtfs_feeds/{FEED}/datasets?limit=100",
                                 headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.load(resp)


def download(ds):
    path = OUT_DIR / f"{ds['id']}.zip"
    if not path.exists():
        print(f"downloading {ds['id']} ({ds['zipped_folder_size_mb']} MB)")
        tmp = path.with_suffix(".part")
        with urllib.request.urlopen(ds["hosted_url"], timeout=300) as resp, open(tmp, "wb") as f:
            shutil.copyfileobj(resp, f)
        tmp.rename(path)
    sha = hashlib.sha256(path.read_bytes()).hexdigest()
    if sha != ds["hash"]:
        raise RuntimeError(f"{path} sha256 doesn't match MDB, delete it and retry")
    return path, sha


def main():
    p = argparse.ArgumentParser()
    p.add_argument("dates", nargs="*", type=date.fromisoformat, help="study dates, YYYY-MM-DD")
    p.add_argument("--check", action="store_true", help="run the self-check only")
    args = p.parse_args()
    if args.check or not args.dates:
        return self_check()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    datasets = list_datasets(access_token())
    new_manifest = not MANIFEST.exists()
    with open(MANIFEST, "a", newline="") as f:
        w = csv.writer(f)
        if new_manifest:
            w.writerow(["date", "dataset_id", "fetched_at", "service_start", "service_end", "size_mb", "sha256"])
        for d in args.dates:
            ds_id = pick_snapshot(datasets, d)
            if ds_id is None:
                raise SystemExit(f"no valid snapshot covers {d}")
            ds = next(x for x in datasets if x["id"] == ds_id)
            path, sha = download(ds)
            w.writerow([d, ds_id, datetime.now(timezone.utc).isoformat(timespec="seconds"),
                        local_date(ds["service_date_range_start"]), local_date(ds["service_date_range_end"]),
                        ds["zipped_folder_size_mb"], sha])
            print(f"{d} -> {path}")


if __name__ == "__main__":
    main()
