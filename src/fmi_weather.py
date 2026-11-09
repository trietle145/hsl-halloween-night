import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path

URL = "https://opendata.fmi.fi/wfs"
OUT_DIR = Path("data/raw/fmi")
STATIONS = {"100971": "Helsinki Kaisaniemi", "100968": "Helsinki-Vantaa airport"}
PARAMS = "TA_PT1H_AVG,TA_PT1H_MIN,PRA_PT1H_ACC,WS_PT1H_AVG,WS_PT1H_MAX,WAWA_PT1H_RANK"
# Sat 18:00 -> Sun 04:00 local, in UTC. Fixed offsets: EEST (+3) on 17 Oct, EET (+2) on 31 Oct
NIGHTS = {"halloween": ("2026-10-31T16:00:00Z", "2026-11-01T02:00:00Z", 2),
          "baseline": ("2026-10-17T15:00:00Z", "2026-10-18T01:00:00Z", 3)}
NS = {"BsWfs": "http://xml.fmi.fi/schema/wfs/2.0"}


def fetch(fmisid, start, end):
    q = dict(service="WFS", version="2.0.0", request="getFeature", fmisid=fmisid, parameters=PARAMS,
             storedquery_id="fmi::observations::weather::hourly::simple", starttime=start, endtime=end)
    with urllib.request.urlopen(f"{URL}?{urllib.parse.urlencode(q)}", timeout=60) as resp:
        return resp.read()


def parse(xml):
    hours = defaultdict(dict)  # utc time -> {param: value}
    for el in ET.fromstring(xml).iterfind(".//BsWfs:BsWfsElement", NS):
        value = el.findtext("BsWfs:ParameterValue", namespaces=NS)
        hours[el.findtext("BsWfs:Time", namespaces=NS)][el.findtext("BsWfs:ParameterName", namespaces=NS)] = \
            None if value == "NaN" else float(value)
    return dict(sorted(hours.items()))


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for fmisid, station in STATIONS.items():
        print(f"\n{station} ({fmisid}), Sat 18:00 -> Sun 04:00 local; each value covers the hour ending at that time")
        for feed, (start, end, offset) in NIGHTS.items():
            path = OUT_DIR / f"{feed}_{fmisid}.xml"
            if not path.exists():  # cached like the Reittiloki pulls
                path.write_bytes(fetch(fmisid, start, end))
            hours = parse(path.read_bytes())
            rain = [h.get("PRA_PT1H_ACC") or 0 for h in hours.values()]  # -1 = no rain
            print(f"  {feed}: rain {sum(r for r in rain if r > 0):.1f} mm in {sum(r > 0 for r in rain)} h, "
                  f"min temp {min(h['TA_PT1H_MIN'] for h in hours.values()):.1f} C, "
                  f"max gust-hour wind {max(h['WS_PT1H_MAX'] for h in hours.values()):.1f} m/s")
            for t, h in hours.items():
                local = (int(t[11:13]) + offset) % 24
                print(f"    {local:02d}:00  {h['TA_PT1H_AVG']:5.1f} C  rain {h['PRA_PT1H_ACC']:5.1f} mm  "
                      f"wind {h['WS_PT1H_AVG']:4.1f} m/s  wawa {h['WAWA_PT1H_RANK']:.0f}")


if __name__ == "__main__":
    main()
