import argparse
import io
import zipfile
from pathlib import Path

import psycopg

FILES = ["routes", "trips", "stops", "stop_times", "calendar", "calendar_dates", "shapes"]


def connect():
    env = dict(line.strip().split("=", 1) for line in open(".env") if "=" in line and not line.startswith("#"))
    return psycopg.connect(host="127.0.0.1", user=env["POSTGRES_USER"],
                           password=env["POSTGRES_PASSWORD"], dbname=env["POSTGRES_DB"])


def load_zip(conn, zip_path, schema):
    conn.execute("CREATE EXTENSION IF NOT EXISTS postgis")
    conn.execute(f"DROP SCHEMA IF EXISTS {schema} CASCADE")
    conn.execute(f"CREATE SCHEMA {schema}")
    conn.execute(f"SET search_path = {schema}, public")
    with zipfile.ZipFile(zip_path) as z:
        for name in FILES:
            with z.open(f"{name}.txt") as raw:
                f = io.TextIOWrapper(raw, encoding="utf-8-sig", newline="")
                cols = f.readline().strip().split(",")
                # raw load: every column is text, the SQL steps cast what they need
                conn.execute(f"CREATE TABLE {name} ({', '.join(f'{c} text' for c in cols)})")
                with conn.cursor().copy(f"COPY {name} FROM STDIN WITH (FORMAT csv)") as copy:
                    while chunk := f.read(1 << 20):
                        copy.write(chunk)
            n = conn.execute(f"SELECT count(*) FROM {name}").fetchone()[0]
            print(f"  {schema}.{name}: {n:,} rows")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("zip", type=Path, help="GTFS zip from data/raw/gtfs/")
    p.add_argument("schema", help="schema to load into, e.g. halloween or baseline")
    args = p.parse_args()

    with connect() as conn:
        load_zip(conn, args.zip, args.schema)
        for sql in sorted(Path("sql").glob("*.sql"))[:5]:  # 05+ need public.observed; load_observed.py runs them
            conn.execute(sql.read_text())
            print(f"  {args.schema}: ran {sql.name}")


if __name__ == "__main__":
    main()
